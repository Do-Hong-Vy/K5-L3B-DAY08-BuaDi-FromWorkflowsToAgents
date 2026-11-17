"""Bonus B3 — swarm + code verifier before the write.

Same peers, same model calls and the same REFERENCE_WEAKNESS as
`lab8.shapes.swarm_reference` (on seed % 5 == 0 a peer trusts the delay written
in the ticket). The only change: before `issue_refund`, a verifier written in
code re-reads the order through `lookup_order` and checks every fact the quote
used (`delay_days`, `status`, `damage_verified`). If any fact disagrees, it
replaces the fact with the structured value, re-quotes once with
`compute_compensation`, and logs `verifier_override` in the trace.

Run next to the official shapes (from src/):
    python -m lab8.benchmark --shapes workflow,swarm,swarm_verified \
        --extra-shape swarm_verified=bonus.swarm_verified:run_claim \
        --seeds 11,22,33,44,55 --out reports/bonus_benchmark.json
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete, parse_delay_days
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "swarm_verified"
# Facts the quote depends on. The verifier trusts only the structured order row.
VERIFIED_FIELDS = ("delay_days", "status", "damage_verified")
MAX_REPAIR_ROUNDS = 1


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


def verify_quote(
    conn: sqlite3.Connection,
    budget: Budget,
    *,
    order_id: str,
    principal_id: str,
    used_order: dict[str, Any],
    quote_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Check the facts behind a quote against the structured order.

    Returns (quote_payload, override). `override` is None when every fact matched;
    otherwise it lists the corrected fields and the old/new amount. At most
    MAX_REPAIR_ROUNDS re-quote. Only fact names and numbers go into the override
    (no ticket text, no PII).
    """
    budget.add_tool(tool_cost())
    truth_view = lookup_order(conn, order_id, principal_id)
    if not truth_view.get("visible"):
        # The investigator saw the order a moment ago; losing it now is unsafe.
        return {"amount_vnd": 0, "reason": "verifier_order_unavailable", "clause_ids": [], "parts": {}}, {
            "fields": [],
            "reason": truth_view.get("reason"),
            "old_amount_vnd": int(quote_payload["amount_vnd"]),
            "new_amount_vnd": 0,
        }
    truth = truth_view["order"]
    mismatched = [f for f in VERIFIED_FIELDS if used_order.get(f) != truth.get(f)]
    if not mismatched:
        return quote_payload, None
    repaired = dict(used_order)
    for field in mismatched:
        repaired[field] = truth[field]
    new_quote = quote_payload
    for _ in range(MAX_REPAIR_ROUNDS):
        budget.add_tool(tool_cost())
        new_quote = compute_compensation(conn, repaired)
    override = {
        "fields": [
            {"field": f, "used": used_order.get(f), "structured": truth[f]} for f in mismatched
        ],
        "old_amount_vnd": int(quote_payload["amount_vnd"]),
        "new_amount_vnd": int(new_quote["amount_vnd"]),
    }
    return new_quote, override


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    budget.add_tool(tool_cost())
    claim_row = conn.execute(
        "SELECT claim_id, principal_id, order_id, ticket FROM claims WHERE claim_id = ?",
        (claim_id,),
    ).fetchone()
    if claim_row is None:
        trace.add("error", {"reason": "unknown_claim"})
        return _finish(conn, claim_id, seed, "failed", 0, budget, trace, "unknown_claim")

    ticket = claim_row["ticket"]
    complete(budget, seed=seed, purpose="peer", prompt=ticket)
    parsed_delay = parse_delay_days(ticket)
    complete(budget, seed=seed, purpose="parse", prompt=ticket)

    if not claim_row["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        trace.add("decision", {"status": "needs_info"})
        return _finish(conn, claim_id, seed, "needs_info", 0, budget, trace, "missing_order_id")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
    )
    trace.add("handoff", safe_dump(handoff))
    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim_row["principal_id"])
    order_view = investigated["tools"].get("lookup_order", {})
    trace.add(
        "investigator",
        {
            "lookup_order": order_view,
            "policy_count": len((investigated["tools"].get("lookup_policy") or {}).get("policies") or []),
        },
    )
    if not order_view.get("visible"):
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        trace.add("decision", {"status": "escalated"})
        return _finish(conn, claim_id, seed, "escalated", 0, budget, trace, order_view.get("reason"))

    order = dict(order_view["order"])
    # Kept on purpose from swarm_reference (REFERENCE_WEAKNESS): the verifier must catch it.
    if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:
        order["delay_days"] = parsed_delay
        trace.add("model_override", {"delay_days": parsed_delay})

    quote_payload = investigated["tools"]["compute_compensation"]
    if order["delay_days"] != order_view["order"]["delay_days"]:
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)
    trace.add("quote", quote_payload)

    # --- B3 verifier: code checks the facts before anything is written. ---
    quote_payload, override = verify_quote(
        conn,
        budget,
        order_id=claim_row["order_id"],
        principal_id=claim_row["principal_id"],
        used_order=order,
        quote_payload=quote_payload,
    )
    if override is not None:
        trace.add("verifier_override", override)
        trace.add("quote", quote_payload)
    else:
        trace.add("verifier_ok", {"fields": list(VERIFIED_FIELDS)})

    proposal = int(quote_payload["amount_vnd"])
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")

    if proposal <= 0:
        trace.add("decision", {"status": "denied", "proposal_amount": 0})
        return _finish(conn, claim_id, seed, "denied", 0, budget, trace, quote_payload.get("reason"))

    trace.add("issue_refund", {"proposed_vnd": proposal})
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("host_result", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        trace.add("decision", {"status": status, "proposal_amount": proposal})
        return _finish(conn, claim_id, seed, status, proposal, budget, trace, outcome["reason"])
    trace.add("decision", {"status": "resolved", "proposal_amount": proposal})
    return _finish(conn, claim_id, seed, "resolved", proposal, budget, trace, None)


def _finish(conn, claim_id, seed, status, proposal, budget, trace, error_reason) -> RunResult:
    return finish(
        conn,
        shape=SHAPE,
        claim_id=claim_id,
        seed=seed,
        status=status,
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=error_reason,
    )
