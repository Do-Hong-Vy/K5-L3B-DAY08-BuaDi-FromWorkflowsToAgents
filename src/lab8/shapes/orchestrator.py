"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import HandoffError, make_handoff
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace

INVESTIGATOR_TOOLS: tuple[str, ...] = (
    "lookup_order",
    "lookup_policy",
    "lookup_refund_history",
)


def build_investigator_handoff(
    *,
    request_id: str,
    claim_id: str,
    task: str = "investigate_order_policy_and_refund_history",
    facts: dict[str, Any] | None = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Create a sanitized handoff.v1 payload restricted to read-only tools."""
    tools = list(INVESTIGATOR_TOOLS if allowed_tools is None else allowed_tools)
    return make_handoff(
        request_id=request_id,
        claim_id=claim_id,
        task=task,
        facts=facts or {},
        allowed_tools=tools,
    )


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    """Execute Shape C (orchestrator + read-only investigators) for a single claim."""
    run_id = make_run_id("orchestrator", claim_id, seed)
    budget = Budget()
    trace = Trace(run_id)
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at, budget=budget, trace=trace)
    except InjectedCrash:
        raise
    except Exception as exc:  # noqa: BLE001 — grader requires RunResult + trace instead of uncaught exceptions
        trace.add("error", {"kind": type(exc).__name__, "reason": "unexpected_error"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=type(exc).__name__,
        )
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
    budget: Budget,
    trace: Trace,
) -> RunResult:
    budget.add_tool(tool_cost())
    claim_view = get_claim_view(conn, claim_id)
    if not claim_view.get("found"):
        trace.add("claim_view", {"claim_id": claim_id, "found": False})
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    order_id = claim_view.get("order_id")
    trace.add("claim_view", {"claim_id": claim_view["claim_id"], "has_order_id": bool(order_id)})

    # Plan using structured metadata only; never trust ticket text or log raw claim rows.
    complete(
        budget,
        seed=seed,
        purpose="plan",
        prompt=f"claim={claim_id};has_order={bool(order_id)}",
    )
    if not order_id:
        trace.add("plan", {"action": "request_order_id", "reason": "missing_order_id"})
        complete(budget, seed=seed, purpose="draft", prompt="status=needs_info")
        trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="needs_info",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="missing_order_id",
        )

    trace.add("plan", {"action": "delegate_readonly_investigator", "allowed_tools": list(INVESTIGATOR_TOOLS)})
    try:
        handoff = build_investigator_handoff(
            request_id=f"REQ-{trace.run_id}",
            claim_id=claim_id,
        )
        trace.add("handoff", safe_dump(handoff))
        investigated = run_readonly_investigators(
            conn,
            budget,
            handoff,
            principal_id=claim_view["principal_id"],
        )
    except (HandoffError, ToolRejected) as exc:
        err_kind = type(exc).__name__
        trace.add("error", {"kind": err_kind, "reason": "handoff_or_tool_rejected"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=err_kind,
        )

    tools_out = investigated.get("tools") or {}
    order_view = tools_out.get("lookup_order") or {}
    policy_view = tools_out.get("lookup_policy") or {}
    history_view = tools_out.get("lookup_refund_history") or {}
    trace.add(
        "investigator",
        {
            "lookup_order": safe_dump(order_view),
            "policy_count": len(policy_view.get("policies") or []),
            "refund_history": safe_dump(history_view),
        },
    )

    if not order_view.get("visible"):
        reason = str(order_view.get("reason") or "order_not_visible")
        complete(budget, seed=seed, purpose="draft", prompt=f"status=escalated;reason={reason}")
        trace.add("decision", {"status": "escalated", "reason": reason})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="escalated",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    # Orchestrator computes the deterministic full quote from structured order fields.
    order = dict(order_view["order"])
    budget.add_tool(tool_cost())
    quote_payload = compute_compensation(conn, order)
    proposal = int(quote_payload["amount_vnd"])
    trace.add("quote", safe_dump(quote_payload))

    if proposal <= 0:
        reason = str(quote_payload.get("reason") or "no_entitlement")
        complete(budget, seed=seed, purpose="draft", prompt=f"status=denied;proposal=0;reason={reason}")
        trace.add("decision", {"status": "denied", "proposal_amount": 0, "reason": reason})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    # Pass the full quote and crash_at directly to the host; let InjectedCrash propagate.
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    trace.add(
        "host_refund",
        {
            "ok": bool(outcome["ok"]),
            "conflict": bool(outcome["conflict"]),
            "reason": outcome["reason"],
            "committed_vnd": (outcome.get("effect") or {}).get("amount_vnd"),
        },
    )

    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        reason = str(outcome["reason"])
        complete(budget, seed=seed, purpose="draft", prompt=f"status={status};proposal={proposal};reason={reason}")
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    complete(budget, seed=seed, purpose="draft", prompt=f"status=resolved;proposal={proposal}")
    trace.add("decision", {"status": "resolved", "proposal_amount": proposal, "reason": outcome["reason"]})
    return finish(
        conn,
        shape="orchestrator",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
