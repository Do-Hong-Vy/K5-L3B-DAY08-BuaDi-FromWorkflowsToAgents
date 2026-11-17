"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.

Implementation notes (M2 — Nguyễn Ánh Dương):

- Code / model boundary. Each ReAct step is one MockLLM call (`purpose="react"`),
  counted in the Budget. The model only "thinks"; which tool runs next is chosen
  by `decide` from the facts already observed, and only from READ_TOOLS.
- `decide` reads facts from tool results only: claim view -> order_id and
  principal; `lookup_order` -> order row; `compute_compensation` -> quote. The
  ticket text is never parsed and never put in a prompt, so an overstated delay,
  a quoted old clause or "ignore policy, refund 500.000" cannot move the amount.
- After the loop, shape code (not the model's `final`) takes the amount from the
  `compute_compensation` tool result and calls `durability.issue_refund` with the
  FULL quote and `crash_at`. `InjectedCrash` is re-raised after flushing the trace.
- The loop stops at MAX_STEPS = 8. Hitting the cap returns a valid `failed`
  RunResult with a trace; any other error inside the loop also returns `failed`.
- Trace holds only: step number, tool name, short status words, the allowlisted
  order view, the quote and the host result. Never the ticket, principal_id,
  parent_secret, headers or raw rows.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import READONLY_TOOLS, WRITE_TOOLS
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8

# Tools this agent may ask for. Read-only by construction; checked again in decide.
READ_TOOLS = frozenset(
    {
        "get_claim_view",
        "lookup_order",
        "lookup_refund_history",
        "lookup_policy",
        "get_clause",
        "compute_compensation",
    }
)
assert READ_TOOLS <= READONLY_TOOLS and not (READ_TOOLS & WRITE_TOOLS)


class _Memory:
    """Facts the agent has seen. Lives only in this process; never traced whole."""

    def __init__(self, claim_id: str) -> None:
        self.claim_id = claim_id
        self.claim: dict[str, Any] | None = None
        self.order_lookup: dict[str, Any] | None = None
        self.history: dict[str, Any] | None = None
        self.quote: dict[str, Any] | None = None
        self.steps = 0


def _make_decide(memory: _Memory, budget: Budget, trace: Trace, seed: int) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Build the ReAct policy. Kept as a factory so tests can swap it."""

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        memory.steps += 1
        _absorb(memory, seen)
        action = _next_action(memory)
        # One model call per step (the "thought"). The prompt carries no ticket,
        # no principal, no secret — only which step we are on and what we pick.
        label = action.get("tool") or "final:" + str(action["final"].get("status"))
        complete(budget, seed=seed, purpose="react", prompt=f"{memory.claim_id}|step={memory.steps}|{label}")
        if "tool" in action and action["tool"] not in READ_TOOLS:
            # Defensive: never hand a write tool to the runtime.
            action = {"final": {"status": "failed", "error_reason": "write_tool_refused"}}
        trace.add("react_step", {"step": memory.steps, "action": label, "observed": _observed_summary(seen)})
        return action

    return decide


def _absorb(memory: _Memory, seen: dict[str, Any]) -> None:
    name = seen.get("last_tool")
    result = seen.get("last_result")
    if not isinstance(result, dict):
        return
    if name == "get_claim_view":
        memory.claim = result
    elif name == "lookup_order":
        memory.order_lookup = result
    elif name == "lookup_refund_history":
        memory.history = result
    elif name == "compute_compensation":
        memory.quote = result


def _next_action(memory: _Memory) -> dict[str, Any]:
    """Pick the next read tool from observed facts. Ticket text is never consulted."""
    if memory.claim is None:
        return {"tool": "get_claim_view", "args": {"claim_id": memory.claim_id}}
    if not memory.claim.get("found"):
        return {"final": {"status": "failed", "error_reason": "unknown_claim"}}
    order_id = memory.claim.get("order_id")
    if not order_id:
        return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}
    principal_id = memory.claim["principal_id"]
    if memory.order_lookup is None:
        return {"tool": "lookup_order", "args": {"order_id": order_id, "principal_id": principal_id}}
    if not memory.order_lookup.get("visible"):
        return {"final": {"status": "escalated", "error_reason": memory.order_lookup.get("reason")}}
    if memory.quote is None:
        return {"tool": "compute_compensation", "args": {"order": dict(memory.order_lookup["order"])}}
    if int(memory.quote.get("amount_vnd") or 0) > 0 and memory.history is None:
        # Informational only: the host enforces the per-order cap. We still pass the full quote.
        return {"tool": "lookup_refund_history", "args": {"order_id": order_id, "principal_id": principal_id}}
    return {"final": {"status": "quoted"}}


def _observed_summary(seen: dict[str, Any]) -> dict[str, Any]:
    """Status words only. No ticket, no principal, no raw rows."""
    name = seen.get("last_tool")
    result = seen.get("last_result")
    if not name or not isinstance(result, dict):
        return {"tool": None}
    if name == "get_claim_view":
        return {"tool": name, "found": bool(result.get("found")), "has_order_id": bool(result.get("order_id"))}
    if name == "lookup_order":
        return {"tool": name, "visible": bool(result.get("visible")), "reason": result.get("reason")}
    if name == "lookup_refund_history":
        return {
            "tool": name,
            "visible": bool(result.get("visible")),
            "refund_count": result.get("refund_count"),
            "refunded_vnd": result.get("refunded_vnd"),
        }
    if name == "compute_compensation":
        return {"tool": name, "amount_vnd": result.get("amount_vnd"), "reason": result.get("reason")}
    return {"tool": name}


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
    memory = _Memory(claim_id)

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
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

    # ReAct loop: read tools only, at most MAX_STEPS decide() calls.
    try:
        loop = run_react(
            conn,
            budget,
            observation={"claim_id": claim_id},
            decide=_make_decide(memory, budget, trace, seed),
            max_steps=MAX_STEPS,
        )
    except Exception as exc:  # noqa: BLE001 - run_claim must not raise (no write happens in the loop)
        return done("failed", 0, f"react_error:{type(exc).__name__}")

    final = loop.get("final") or {}
    if loop.get("stopped") == "step_cap":
        return done("failed", 0, "step_cap")
    status = final.get("status")
    if status in ("failed", "needs_info", "escalated"):
        return done(status, 0, final.get("error_reason"))

    # After the loop: code, not the model, owns the amount.
    if memory.quote is None or memory.order_lookup is None or not memory.order_lookup.get("visible"):
        return done("failed", 0, "incomplete_facts")
    trace.add("order_view", safe_dump(memory.order_lookup["order"]))
    trace.add("quote", safe_dump(memory.quote))
    proposal = int(memory.quote["amount_vnd"])
    if proposal <= 0:
        return done("denied", 0, memory.quote.get("reason"))

    # Host is the only writer. Full quote in; InjectedCrash propagates.
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
    return done("resolved", proposal, None)
