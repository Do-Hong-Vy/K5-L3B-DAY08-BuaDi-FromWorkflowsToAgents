"""Shape A — deterministic workflow. Student work.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Suggested steps. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> status `needs_info`. Do not write the ledger.
3. `lookup_order`. If not visible -> `escalated`. Do not copy phone, address, item, internal note.
4. Quote from the order row. Ignore delay numbers written in the ticket.
5. Quote amount 0 -> `denied`. Do not call issue_refund.
6. Quote amount > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`.
   Pass the FULL quote. The host checks the claim's own approval and subtracts
   what earlier claims already got for the same order (T13, T14). Do not
   subtract it yourself or the host subtracts twice.
   Auth failure or order already refunded -> `denied` (the host writes `policy_denied`).
   `proposal_amount` stays the full quote. Amount conflict -> `failed`.
7. Success -> `resolved`. One ledger row, one `refund_committed` audit.
8. Use MockLLM only to draft the reply text, if you want a model call at all.

The model must not choose the refund amount and must not commit the refund.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.

Implementation notes (group):

- Only the claim id, principal-free status words, the allowlisted order view
  (`lookup_order` -> ORDER_FIELDS) and the quote go into the trace. The ticket
  text, principal_id, parent_secret and raw claim/order rows are never traced.
- The ticket is user data. It is never parsed for delay days or order ids.
- MockLLM is called once, at the end, to draft the customer reply. Its output
  is not used for any decision.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        # The model only drafts wording; the status and amount are already fixed.
        complete(budget, seed=seed, purpose="draft", prompt=f"{status}:{proposal}")
        trace.add("decision", {"status": status, "proposal_amount": int(proposal), "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    # Step 1: claim view (allowlisted columns only).
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("tool", {"name": "get_claim_view", "found": claim["found"]})
    if not claim["found"]:
        return done("failed", 0, "unknown_claim")

    # Step 2: no order id on the claim row -> ask for it. Never mine the ticket for one.
    if not claim["order_id"]:
        return done("needs_info", 0, "missing_order_id")

    # Step 3: order scoped to the claim's principal.
    budget.add_tool(tool_cost())
    looked = lookup_order(conn, claim["order_id"], claim["principal_id"])
    trace.add("tool", {"name": "lookup_order", "visible": looked["visible"], "reason": looked["reason"]})
    if not looked["visible"]:
        return done("escalated", 0, looked["reason"])
    order: dict[str, Any] = looked["order"]
    trace.add("order_view", safe_dump(order))

    # Step 4: quote in code, from the order row and current policies only.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    trace.add("quote", safe_dump(quote))
    proposal = int(quote["amount_vnd"])

    # Step 5: nothing owed -> deny without touching the host.
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Step 6: the host is the only writer. Full quote in; InjectedCrash propagates.
    trace.add("issue_refund", {"proposed_vnd": proposal})
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    effect = outcome.get("effect") or {}
    trace.add(
        "host_result",
        {
            "ok": outcome["ok"],
            "reason": outcome["reason"],
            "conflict": outcome["conflict"],
            "amount_vnd": effect.get("amount_vnd"),
        },
    )

    if outcome["conflict"]:
        return done("failed", proposal, outcome["reason"])
    if not outcome["ok"]:
        return done("denied", proposal, outcome["reason"])
    # Step 7: committed (or idempotent replay of the same amount).
    return done("resolved", proposal, None)
