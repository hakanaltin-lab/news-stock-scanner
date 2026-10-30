"""The G4 shadow ledger audit must be read-only and tamper-evident."""

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from engines.shadow_audit_ledger import ShadowAuditLedger
from engines.shadow_audit_verifier import (
    receipt_binding_sha256,
    verify_shadow_ledger,
)


def safe_shadow():
    return {
        "shadow_order_id": "shadow-001",
        "idempotency_key": "intent-001",
        "symbol": "BKR",
        "status": "SHADOW_ACCEPTED",
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
    }


def evidence():
    return {
        "readiness_proof_sha256": "a" * 64,
        "market_data_proof_sha256": "b" * 64,
    }


class ShadowAuditVerifierTests(unittest.TestCase):
    def create_ledger(self, directory):
        path = Path(directory) / "shadow.sqlite3"
        receipt = ShadowAuditLedger(path).record_shadow_order(
            safe_shadow(),
            evidence(),
        )
        return path, receipt

    def test_valid_ledger_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = self.create_ledger(directory)
            result = verify_shadow_ledger(path, receipt)
        self.assertEqual(result["status"], "LEDGER_VERIFIED")
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["failure_reasons"], [])
        self.assertTrue(result["expected_receipt_bound"])
        self.assertEqual(
            result["expected_receipt_sha256"],
            receipt_binding_sha256(receipt),
        )
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_missing_expected_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.create_ledger(directory)
            result = verify_shadow_ledger(path)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["failure_reasons"],
            ["EXPECTED_LEDGER_RECEIPT_REQUIRED"],
        )

    def test_unrelated_expected_receipt_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = self.create_ledger(directory)
            receipt["shadow_order_id"] = "shadow-unrelated"
            result = verify_shadow_ledger(path, receipt)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["expected_receipt_bound"])
        self.assertIn(
            "EXPECTED_LEDGER_RECEIPT_NOT_FOUND",
            result["failure_reasons"],
        )

    def test_missing_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = verify_shadow_ledger(
                Path(directory) / "missing.sqlite3",
                {
                    "recorded": True,
                    "duplicate": False,
                    "idempotency_key": "intent-001",
                    "shadow_order_id": "shadow-001",
                    "symbol": "BKR",
                    "payload_sha256": "a" * 64,
                    "recorded_at": "2026-10-30T12:00:00+00:00",
                },
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["failure_reasons"], ["LEDGER_NOT_FOUND"])

    def test_payload_hash_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = self.create_ledger(directory)
            connection = sqlite3.connect(str(path))
            try:
                connection.execute(
                    "UPDATE shadow_order_receipts SET payload_json = ?",
                    ("{}",),
                )
                connection.commit()
            finally:
                connection.close()
            result = verify_shadow_ledger(path, receipt)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "ROW_1_PAYLOAD_HASH_MISMATCH",
            result["failure_reasons"],
        )

    def test_unsafe_flags_are_detected_even_with_recomputed_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = self.create_ledger(directory)
            connection = sqlite3.connect(str(path))
            try:
                payload_json = connection.execute(
                    "SELECT payload_json FROM shadow_order_receipts"
                ).fetchone()[0]
                payload = json.loads(payload_json)
                payload["shadow_order"][
                    "paper_order_submission_allowed"
                ] = True
                altered = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                digest = hashlib.sha256(
                    altered.encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    UPDATE shadow_order_receipts
                    SET payload_json = ?, payload_sha256 = ?
                    """,
                    (altered, digest),
                )
                connection.commit()
            finally:
                connection.close()
            result = verify_shadow_ledger(path, receipt)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "ROW_1_SUBMISSION_FLAGS_NOT_SAFE",
            result["failure_reasons"],
        )

    def test_verifier_contains_no_write_or_broker_path(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "engines"
            / "shadow_audit_verifier.py"
        ).read_text(encoding="utf-8")
        for token in ["INSERT INTO", "UPDATE ", "DELETE FROM", "ibapi", "placeOrder"]:
            self.assertNotIn(token, source)
        self.assertIn("mode=ro", source)


if __name__ == "__main__":
    unittest.main()
