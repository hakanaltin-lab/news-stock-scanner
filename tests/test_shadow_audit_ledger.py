"""Persistent G4 shadow ledger must prevent restart duplicates."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engines.shadow_audit_ledger import ShadowAuditLedger
from scripts.aurora_g4_shadow import evaluate_runtime_shadow
from tests.test_aurora_g4_shadow import intent, market_proof, readiness


class ShadowAuditLedgerTests(unittest.TestCase):
    def test_record_is_append_only_and_file_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.sqlite3"
            receipt = ShadowAuditLedger(path).record_shadow_order(
                {
                    "shadow_order_id": "shadow-001",
                    "idempotency_key": "intent-001",
                    "symbol": "BKR",
                    "status": "SHADOW_ACCEPTED",
                },
                {"readiness_proof_sha256": "a" * 64},
            )
            self.assertTrue(receipt["recorded"])
            self.assertFalse(receipt["duplicate"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

            connection = sqlite3.connect(str(path))
            try:
                count = connection.execute(
                    "SELECT COUNT(*) FROM shadow_order_receipts"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(count, 1)

    def test_duplicate_key_returns_original_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.sqlite3"
            ledger = ShadowAuditLedger(path)
            first = ledger.record_shadow_order(
                {
                    "shadow_order_id": "shadow-001",
                    "idempotency_key": "intent-001",
                    "symbol": "BKR",
                },
                {},
            )
            second = ledger.record_shadow_order(
                {
                    "shadow_order_id": "shadow-002",
                    "idempotency_key": "intent-001",
                    "symbol": "BKR",
                },
                {},
            )
            self.assertTrue(first["recorded"])
            self.assertFalse(second["recorded"])
            self.assertTrue(second["duplicate"])
            self.assertEqual(
                second["existing_shadow_order_id"],
                "shadow-001",
            )

    def test_runtime_gate_blocks_same_intent_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.sqlite3"
            with patch.dict(os.environ, {"AURORA_RUN_MODE": "DRY_RUN"}):
                first = evaluate_runtime_shadow(
                    readiness(datetime.now(timezone.utc).isoformat()),
                    market_proof(),
                    intent(),
                    ledger_path=path,
                )
                second = evaluate_runtime_shadow(
                    readiness(datetime.now(timezone.utc).isoformat()),
                    market_proof(),
                    intent(),
                    ledger_path=path,
                )
            self.assertEqual(first["status"], "SHADOW_ACCEPTED")
            self.assertTrue(first["ledger_receipt"]["recorded"])
            self.assertEqual(second["status"], "BLOCKED")
            self.assertEqual(
                second["reason"],
                "PERSISTENT_DUPLICATE_ORDER_INTENT",
            )

    def test_unavailable_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            blocked_path = Path(directory) / "as-directory"
            blocked_path.mkdir()
            with patch.dict(os.environ, {"AURORA_RUN_MODE": "DRY_RUN"}):
                result = evaluate_runtime_shadow(
                    readiness(datetime.now(timezone.utc).isoformat()),
                    market_proof(),
                    intent(),
                    ledger_path=blocked_path,
                )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(
                result["reason"],
                "PERSISTENT_SHADOW_LEDGER_UNAVAILABLE",
            )
            self.assertFalse(result["paper_order_submission_allowed"])

    def test_ledger_source_has_no_mutation_or_broker_path(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "engines"
            / "shadow_audit_ledger.py"
        ).read_text(encoding="utf-8")
        for token in ["UPDATE shadow_order_receipts", "DELETE FROM", "ibapi", "placeOrder"]:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
