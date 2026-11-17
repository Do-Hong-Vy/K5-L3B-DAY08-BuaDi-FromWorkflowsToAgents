"""Extra unit and security-boundary tests for Shape C (orchestrator + handoff + trace)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.handoff import ALLOWED_FIELDS, FACT_KEYS, READONLY_TOOLS, WRITE_TOOLS, HandoffError
from lab8.metrics import artifact_blob, check_trace, trial_pass
from lab8.runtime import ToolRejected
from lab8.shapes import orchestrator
from lab8.shapes.orchestrator import build_investigator_handoff, run_claim
from tests.conftest import BY_ID, CLAIMS, WORLD


def _forbidden_world_tokens() -> list[str]:
    tokens = ["CANARY_SECRET_", "CANARY_INTERNAL_", "parent_secret", "raw_headers"]
    for order in WORLD["orders"]:
        for field in ("phone", "address", "internal_note", "item_name"):
            value = str(order.get(field) or "")
            if value:
                tokens.append(value)
    return tokens


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_orchestrator_all_public_claims_pass_without_secret_or_pii_leak(tmp_path: Path, capsys, seed: int):
    forbidden = _forbidden_world_tokens()
    for claim in CLAIMS:
        claim_id = claim["claim_id"]
        store = tmp_path / f"{claim_id}-{seed}.sqlite"
        init_store(store, WORLD, CLAIMS).close()
        started_at = time.time()
        result = run_claim(claim_id, seed=seed, store_path=str(store))
        result_dict = result.as_dict()

        conn = connect(store)
        try:
            passed, reason = trial_pass(result_dict, claim["expected"], conn, started_at=started_at)
        finally:
            conn.close()
        assert passed, f"{claim_id} seed={seed}: {reason}"
        assert check_trace(result_dict, started_at=started_at) == (True, "ok")

        blob = artifact_blob(result_dict)
        captured = capsys.readouterr()
        combined = "\n".join([blob, captured.out, captured.err])
        for token in forbidden:
            assert token not in combined, f"leaked {token!r} on {claim_id} seed={seed}"

        trace_body = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
        for event in trace_body["events"]:
            if event.get("kind") == "handoff":
                handoff = event["payload"]
                assert set(handoff) <= ALLOWED_FIELDS
                assert set(handoff.get("facts") or {}) <= FACT_KEYS
                allowed = set(handoff.get("allowed_tools") or [])
                assert allowed <= READONLY_TOOLS
                assert not (allowed & WRITE_TOOLS)


def test_handoff_rejects_write_tools_and_drops_extra_facts():
    with pytest.raises(HandoffError):
        build_investigator_handoff(
            request_id="REQ-WRITE",
            claim_id="C-001",
            allowed_tools=["lookup_order", "issue_refund"],
        )

    with pytest.raises(HandoffError):
        build_investigator_handoff(
            request_id="REQ-AUDIT",
            claim_id="C-001",
            allowed_tools=["append_audit"],
        )

    cleaned = build_investigator_handoff(
        request_id="REQ-CLEAN",
        claim_id="C-001",
        facts={
            "delay_days": 4,
            "parent_secret": "CANARY_SECRET_SHOULD_BE_DROPPED",
            "phone": "0901000107",
            "raw_headers": {"Authorization": "Bearer secret"},
        },
    )
    assert set(cleaned) <= ALLOWED_FIELDS
    assert cleaned["facts"] == {"delay_days": 4}
    assert "CANARY_SECRET_" not in json.dumps(cleaned)


@pytest.mark.parametrize("exc_factory", [lambda: HandoffError("bad handoff"), lambda: ToolRejected("issue_refund")])
def test_orchestrator_catches_handoff_and_tool_rejection_cleanly(public_db: Path, monkeypatch, exc_factory):
    def _boom(*args, **kwargs):
        raise exc_factory()

    monkeypatch.setattr(orchestrator, "run_readonly_investigators", _boom)
    started_at = time.time()
    result = run_claim("C-001", seed=11, store_path=str(public_db))
    assert result.status == "failed"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert check_trace(result.as_dict(), started_at=started_at) == (True, "ok")


def test_orchestrator_handles_unknown_claim_with_valid_trace(public_db: Path):
    started_at = time.time()
    result = run_claim("C-UNKNOWN-999", seed=11, store_path=str(public_db))
    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
    assert check_trace(result.as_dict(), started_at=started_at) == (True, "ok")


def test_orchestrator_blocks_mismatched_and_revoked_approvals_with_policy_denied(tmp_path: Path):
    store = tmp_path / "approval-edges.sqlite"
    init_store(store, WORLD, CLAIMS).close()
    conn = connect(store)
    try:
        conn.execute(
            "INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at) "
            "VALUES ('A-REV', 'C-REV', 35000, 'revoked', '2027-12-31')"
        )
        conn.execute(
            "INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id) "
            "VALUES ('C-MISMATCH', 'P-100', 'O-808', 'trễ 4 ngày', 'CANARY_SECRET_MISMATCH', '{}', 'A-001')"
        )
        conn.execute(
            "INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id) "
            "VALUES ('C-REV', 'P-100', 'O-909', 'trễ 4 ngày', 'CANARY_SECRET_REV', '{}', 'A-REV')"
        )
        conn.commit()
    finally:
        conn.close()

    for cid, expected_reason in (("C-MISMATCH", "approval_claim_mismatch"), ("C-REV", "approval_revoked")):
        started_at = time.time()
        res = run_claim(cid, seed=11, store_path=str(store))
        assert res.status == "denied"
        assert res.proposal_amount == 35000
        assert res.error_reason == expected_reason
        assert res.refund_effects == []
        assert check_trace(res.as_dict(), started_at=started_at) == (True, "ok")
        conn = connect(store)
        try:
            assert get_refund(conn, cid) is None
            denials = conn.execute(
                "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
                (cid,),
            ).fetchall()
            assert any(expected_reason in row["details_json"] for row in denials)
        finally:
            conn.close()


@pytest.mark.parametrize("crash_point", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_orchestrator_crash_and_resume_keeps_single_refund(tmp_path: Path, crash_point: str):
    store = tmp_path / f"orch-{crash_point}.sqlite"
    init_store(store, WORLD, CLAIMS).close()

    with pytest.raises(InjectedCrash):
        run_claim("C-012", seed=11, store_path=str(store), crash_at=crash_point)

    started_at = time.time()
    resumed = run_claim("C-012", seed=11, store_path=str(store), crash_at=None)
    conn = connect(store)
    try:
        passed, reason = trial_pass(resumed.as_dict(), BY_ID["C-012"]["expected"], conn, started_at=started_at)
        ledger_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-012'"
        ).fetchone()["n"]
        audits = committed_audit_count(conn, "C-012")
    finally:
        conn.close()
    assert passed, reason
    assert ledger_rows == 1
    assert audits == 1
