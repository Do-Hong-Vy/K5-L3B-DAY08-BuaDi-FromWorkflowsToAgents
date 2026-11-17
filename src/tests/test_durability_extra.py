"""Extra durability and policy enforcement checks for Lab 8.

Owner: Phạm Văn Chiêu (M4 — Ledger/durability/crash + evaluation).
Covers idempotency guarantees, SQLite ACID durability across crash injection points,
and strict approval binding under docs/business_rules.md & docs/contracts.md.
Runs in the host gate (`python -m pytest -q`).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lab8.db import connect
from lab8.durability import (
    InjectedCrash,
    committed_audit_count,
    get_refund,
    idempotency_key,
    issue_refund,
)
from lab8.shapes.workflow import run_claim


def _count_rows(conn: sqlite3.Connection, table: str, claim_id: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM {table} WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def _count_audits(conn: sqlite3.Connection, claim_id: str, event_type: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM audit_events WHERE claim_id = ? AND event_type = ?",
        (claim_id, event_type),
    ).fetchone()
    return int(row["n"]) if row else 0


def test_idempotent_replays_never_duplicate_ledger_entry(public_db):
    """Calling issue_refund 3 times with identical quote preserves exactly 1 ledger row and 1 audit."""
    conn = connect(public_db)
    r1 = issue_refund(conn, "C-001", 35000)
    r2 = issue_refund(conn, "C-001", 35000)
    r3 = issue_refund(conn, "C-001", 35000)

    ledger_count = _count_rows(conn, "refund_ledger", "C-001")
    audits = committed_audit_count(conn, "C-001")
    conn.close()

    assert r1["ok"] is True and r1["reason"] == "committed"
    assert r2["ok"] is True and r2["reason"] == "idempotent_replay"
    assert r3["ok"] is True and r3["reason"] == "idempotent_replay"
    assert ledger_count == 1
    assert audits == 1


def test_idempotency_key_strictly_matches_contract(public_db):
    """The idempotency key must be deterministic and strictly formatted as refund:{claim_id}."""
    assert idempotency_key("C-001") == "refund:C-001"
    assert idempotency_key("C-XYZ-999") == "refund:C-XYZ-999"

    conn = connect(public_db)
    issue_refund(conn, "C-001", 35000)
    record = get_refund(conn, "C-001")
    conn.close()

    assert record is not None
    assert record["idempotency_key"] == "refund:C-001"


def test_different_amount_replay_triggers_conflict_and_leaves_ledger_intact(public_db):
    """A replay attempting a different amount triggers amount_conflict and does not mutate the ledger."""
    conn = connect(public_db)
    r1 = issue_refund(conn, "C-001", 35000)
    r2 = issue_refund(conn, "C-001", 10000)
    record = get_refund(conn, "C-001")
    conflict_audits = _count_audits(conn, "C-001", "amount_conflict")
    conn.close()

    assert r1["ok"] is True
    assert r2["ok"] is False
    assert r2["conflict"] is True
    assert r2["reason"] == "amount_conflict"
    assert record is not None
    assert int(record["amount_vnd"]) == 35000
    assert conflict_audits >= 1


@pytest.mark.parametrize("crash_point", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_issue_refund_crash_and_resume_durability(public_db, crash_point):
    """Direct durability test: InjectedCrash at any of the 3 points always recovers to exactly 1 refund."""
    conn = connect(public_db)
    with pytest.raises(InjectedCrash):
        issue_refund(conn, "C-011", 35000, crash_at=crash_point)

    # Resume on same connection / database
    resumed = issue_refund(conn, "C-011", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-011")
    audits = committed_audit_count(conn, "C-011")
    conn.close()

    assert resumed["ok"] is True
    assert ledger_count == 1
    assert audits == 1


def test_crash_after_effect_before_checkpoint_resumes_via_ledger(public_db):
    """Even if the checkpoint is missing, the committed ledger entry guarantees idempotency."""
    conn = connect(public_db)
    with pytest.raises(InjectedCrash):
        issue_refund(conn, "C-011", 35000, crash_at="after_effect_before_checkpoint")

    # Checkpoint was not written yet
    checkpoint = conn.execute("SELECT 1 FROM checkpoints WHERE claim_id = 'C-011'").fetchone()
    assert checkpoint is None

    # But ledger already committed the row in the write transaction
    ledger_row = get_refund(conn, "C-011")
    assert ledger_row is not None
    assert int(ledger_row["amount_vnd"]) == 35000

    # Resume works without duplicating
    resumed = issue_refund(conn, "C-011", 35000)
    assert resumed["reason"] == "idempotent_replay"
    conn.close()


def test_workflow_shape_never_swallows_injected_crash(public_db):
    """The shape must let InjectedCrash propagate so fault-injection tests observe the crash."""
    with pytest.raises(InjectedCrash):
        run_claim("C-011", seed=11, store_path=str(public_db), crash_at="before_effect")

    with pytest.raises(InjectedCrash):
        run_claim("C-011", seed=11, store_path=str(public_db), crash_at="after_effect_before_checkpoint")


def test_expired_approval_is_rejected_without_refund(public_db):
    """Claim with expired approval must be rejected by host policy and write policy_denied audit."""
    conn = connect(public_db)
    # Manually expire approval for C-001 to test policy boundary
    conn.execute(
        "UPDATE approvals SET expires_at = '2026-11-01T00:00:00' WHERE claim_id = 'C-001'"
    )
    conn.commit()

    decision = issue_refund(conn, "C-001", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-001")
    denied_audits = _count_audits(conn, "C-001", "policy_denied")
    conn.close()

    assert decision["ok"] is False
    assert decision["reason"] == "approval_expired"
    assert ledger_count == 0
    assert denied_audits >= 1


def test_revoked_approval_is_rejected_without_refund(public_db):
    """Revoked approval must be blocked; no refund committed."""
    conn = connect(public_db)
    conn.execute(
        "UPDATE approvals SET status = 'revoked' WHERE claim_id = 'C-001'"
    )
    conn.commit()

    decision = issue_refund(conn, "C-001", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-001")
    denied_audits = _count_audits(conn, "C-001", "policy_denied")
    conn.close()

    assert decision["ok"] is False
    assert decision["reason"] == "approval_revoked"
    assert ledger_count == 0
    assert denied_audits >= 1


def test_mismatched_claim_approval_is_rejected(public_db):
    """Approval belonging to another claim cannot authorize this claim."""
    conn = connect(public_db)
    # Point approval to another claim
    conn.execute(
        "UPDATE approvals SET claim_id = 'C-999' WHERE claim_id = 'C-001'"
    )
    conn.commit()

    decision = issue_refund(conn, "C-001", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-001")
    conn.close()

    assert decision["ok"] is False
    assert decision["reason"] in ("approval_claim_mismatch", "approval_missing")
    assert ledger_count == 0


def test_outside_principal_scope_rejected(public_db):
    """Claim on an order that belongs to a different principal is rejected."""
    conn = connect(public_db)
    # Tamper claim principal
    conn.execute(
        "UPDATE claims SET principal_id = 'P-OTHER' WHERE claim_id = 'C-001'"
    )
    conn.commit()

    decision = issue_refund(conn, "C-001", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-001")
    conn.close()

    assert decision["ok"] is False
    assert decision["reason"] == "outside_principal_scope"
    assert ledger_count == 0


def test_order_cap_enforced_against_prior_refunds(public_db):
    """When an order has already been fully refunded, further refund attempts must be denied."""
    conn = connect(public_db)
    # C-013: order already refunded
    decision = issue_refund(conn, "C-013", 35000)
    ledger_count = _count_rows(conn, "refund_ledger", "C-013")
    denied_audits = _count_audits(conn, "C-013", "policy_denied")
    conn.close()

    assert decision["ok"] is False
    assert decision["reason"] == "order_already_refunded"
    assert ledger_count == 0
    assert denied_audits >= 1


def test_partial_order_refund_caps_amount_correctly(public_db):
    """Host allows refund only up to the remaining unrefunded ceiling of the order."""
    conn = connect(public_db)
    # C-014: order paid 150k, prior refund 30k, quote is 150k -> remaining paid is 120k
    decision = issue_refund(conn, "C-014", 150000)
    record = get_refund(conn, "C-014")
    conn.close()

    assert decision["ok"] is True
    assert record is not None
    assert int(record["amount_vnd"]) == 120000
