"""The final G0-G4 gate must validate only a shadow Paper milestone."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.aurora_completion_status import (
    evaluate_completion_status as _evaluate_completion_status,
)
from engines.shadow_audit_verifier import receipt_binding_sha256


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"


def digest(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verified_gateway_attestation():
    return {
        "engine": "AURORA G7.5 Gateway Read-Only Attestation Verifier",
        "verified": True,
        "status": "VERIFIED",
        "gateway_read_only_configuration_independently_attested": True,
        "failure_reasons": [],
        "attestation_id": "22222222-2222-4222-8222-222222222222",
        "reviewer_id": "aurora-independent-reviewer",
        "captured_at_utc": (NOW - timedelta(minutes=10)).isoformat(),
        "expires_at_utc": (NOW + timedelta(hours=1)).isoformat(),
        "git_sha": "a" * 40,
        "evidence_sha256": "b" * 64,
    }


def evaluate_completion_status(*args, **kwargs):
    kwargs.setdefault(
        "gateway_attestation_verification",
        verified_gateway_attestation(),
    )
    return _evaluate_completion_status(
        *args,
        **kwargs,
    )


def proofs():
    safe = {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }
    g0 = {
        **safe,
        "generated_at": (NOW - timedelta(minutes=5)).isoformat(),
        "status": "G0_G1_VERIFIED",
        "failure_reasons": [],
    }
    g2 = {
        "run_mode": {"mode": "READ_ONLY"},
        "gateway_read_only_attestation": verified_gateway_attestation(),
        "readiness": {
            "readiness": "READY_FOR_PAPER_READ_ONLY",
            "required_failure_count": 0,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
            "gateway_read_only_configuration_independently_attested": True,
        },
        "snapshot": {
            "order_submission_hard_blocked": True,
            "gateway_read_only_configuration_independently_attested": True,
        },
    }
    readiness = {
        **safe,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "generated_at": (NOW - timedelta(seconds=20)).isoformat(),
        "status": "READY_FOR_CONTROLLED_DRY_RUN",
        "failure_reasons": [],
        "g0_g1_proof_sha256": digest(g0),
        "g2_paper_read_only_proof_sha256": digest(g2),
        "gateway_read_only_attestation_sha256": digest(
            verified_gateway_attestation()
        ),
    }
    g4 = {
        **safe,
        "evidence_run_id": EVIDENCE_RUN_ID,
        "generated_at": (NOW - timedelta(seconds=10)).isoformat(),
        "status": "SHADOW_ACCEPTED",
        "readiness_proof_sha256": digest(readiness),
        "ledger_receipt": {
            "recorded": True,
            "duplicate": False,
            "idempotency_key": "intent-001",
            "shadow_order_id": "shadow-001",
            "symbol": "BKR",
            "payload_sha256": "c" * 64,
            "recorded_at": (NOW - timedelta(seconds=10)).isoformat(),
        },
    }
    audit = {
        **safe,
        "generated_at": (NOW - timedelta(seconds=5)).isoformat(),
        "status": "LEDGER_VERIFIED",
        "record_count": 1,
        "failure_reasons": [],
        "expected_receipt_bound": True,
        "expected_receipt_sha256": receipt_binding_sha256(
            g4["ledger_receipt"]
        ),
    }
    return g0, readiness, g4, audit, g2


class AuroraCompletionStatusTests(unittest.TestCase):
    def test_complete_shadow_chain_passes_without_order_permission(self):
        g0, ready, g4, audit, g2 = proofs()
        result = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertEqual(
            result["status"],
            "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        )
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["real_money_trading_allowed"])
        self.assertEqual(
            result["next_gate"],
            "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        )
        self.assertTrue(result["checks"]["g4_readiness_proof_bound"])
        self.assertTrue(result["checks"]["g4_evidence_run_bound"])
        self.assertTrue(result["checks"]["g4_ledger_receipt_bound"])
        self.assertTrue(
            result["checks"]["g0_g1_readiness_proof_bound"]
        )
        self.assertTrue(result["checks"]["g2_readiness_proof_bound"])
        self.assertTrue(
            result["checks"]["gateway_attestation_runtime_verified"]
        )
        self.assertTrue(
            result["checks"]["gateway_attestation_g2_runtime_bound"]
        )
        self.assertTrue(
            result["checks"]["gateway_attestation_readiness_bound"]
        )
        self.assertEqual(
            result["evidence_binding"]["g0_g1_proof_sha256"],
            result["evidence_binding"][
                "readiness_recorded_g0_g1_proof_sha256"
            ],
        )
        self.assertEqual(
            result["evidence_binding"][
                "g2_paper_read_only_proof_sha256"
            ],
            result["evidence_binding"][
                "readiness_recorded_g2_proof_sha256"
            ],
        )
        self.assertEqual(
            result["evidence_binding"]["readiness_proof_sha256"],
            result["evidence_binding"][
                "g4_recorded_readiness_proof_sha256"
            ],
        )
        self.assertEqual(
            result["evidence_binding"]["readiness_evidence_run_id"],
            result["evidence_binding"]["g4_evidence_run_id"],
        )

    def test_completion_reverifies_signed_gateway_attestation(self):
        g0, ready, g4, audit, g2 = proofs()
        blocked = verified_gateway_attestation()
        blocked["status"] = "BLOCKED"
        blocked["verified"] = False
        blocked[
            "gateway_read_only_configuration_independently_attested"
        ] = False
        result = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
            gateway_attestation_verification=blocked,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "gateway_attestation_runtime_verified",
            result["failure_reasons"],
        )
        self.assertIn(
            "gateway_attestation_g2_runtime_bound",
            result["failure_reasons"],
        )
        self.assertIn(
            "gateway_attestation_readiness_bound",
            result["failure_reasons"],
        )

    def test_forged_g2_attestation_is_rejected_even_with_recomputed_hashes(self):
        g0, ready, g4, audit, g2 = proofs()
        g2["gateway_read_only_attestation"]["evidence_sha256"] = "c" * 64
        ready["g2_paper_read_only_proof_sha256"] = digest(g2)
        ready["gateway_read_only_attestation_sha256"] = digest(
            g2["gateway_read_only_attestation"]
        )
        g4["readiness_proof_sha256"] = digest(ready)
        result = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "gateway_attestation_g2_runtime_bound",
            result["failure_reasons"],
        )
        self.assertIn(
            "gateway_attestation_readiness_bound",
            result["failure_reasons"],
        )

    def test_gateway_read_only_attestation_is_required_at_completion(self):
        for location in ("snapshot", "readiness"):
            with self.subTest(location=location):
                g0, ready, g4, audit, g2 = proofs()
                g2[location][
                    "gateway_read_only_configuration_independently_attested"
                ] = False
                ready["g2_paper_read_only_proof_sha256"] = digest(g2)
                g4["readiness_proof_sha256"] = digest(ready)
                result = evaluate_completion_status(
                    g0,
                    ready,
                    g4,
                    audit,
                    now=NOW,
                    g2_proof=g2,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn(
                    "g2_gateway_read_only_independently_attested",
                    result["failure_reasons"],
                )

    def test_missing_or_mismatched_g4_evidence_run_id_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        g4.pop("evidence_run_id")
        missing = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn("g4_evidence_run_bound", missing["failure_reasons"])

        g4["evidence_run_id"] = (
            "22222222-2222-4222-8222-222222222222"
        )
        mismatched = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn(
            "g4_evidence_run_bound",
            mismatched["failure_reasons"],
        )
        self.assertFalse(mismatched["paper_order_submission_allowed"])

    def test_missing_or_stale_stage_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        missing = evaluate_completion_status(
            {}, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn("g0_g1_verified", missing["failure_reasons"])
        ready["generated_at"] = (NOW - timedelta(seconds=121)).isoformat()
        stale = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn("g2_g3_evidence_fresh", stale["failure_reasons"])

    def test_missing_or_mismatched_g0_readiness_binding_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        ready.pop("g0_g1_proof_sha256")
        g4["readiness_proof_sha256"] = digest(ready)
        missing = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn(
            "g0_g1_readiness_proof_bound",
            missing["failure_reasons"],
        )

        ready["g0_g1_proof_sha256"] = "0" * 64
        g4["readiness_proof_sha256"] = digest(ready)
        mismatched = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertIn(
            "g0_g1_readiness_proof_bound",
            mismatched["failure_reasons"],
        )
        self.assertFalse(mismatched["paper_order_submission_allowed"])

    def test_missing_or_mismatched_g2_readiness_binding_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        ready.pop("g2_paper_read_only_proof_sha256")
        g4["readiness_proof_sha256"] = digest(ready)
        missing = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn(
            "g2_readiness_proof_bound",
            missing["failure_reasons"],
        )

        ready["g2_paper_read_only_proof_sha256"] = "0" * 64
        g4["readiness_proof_sha256"] = digest(ready)
        mismatched = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertIn(
            "g2_readiness_proof_bound",
            mismatched["failure_reasons"],
        )
        self.assertFalse(mismatched["paper_order_submission_allowed"])

    def test_unsafe_flag_or_duplicate_receipt_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        g4["paper_order_submission_allowed"] = True
        g4["ledger_receipt"]["duplicate"] = True
        result = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn("g4_shadow_accepted", result["failure_reasons"])

    def test_missing_or_mismatched_readiness_digest_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        g4.pop("readiness_proof_sha256")
        missing = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn(
            "g4_readiness_proof_bound",
            missing["failure_reasons"],
        )

        g4["readiness_proof_sha256"] = "0" * 64
        mismatched = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertIn(
            "g4_readiness_proof_bound",
            mismatched["failure_reasons"],
        )
        self.assertFalse(mismatched["paper_order_submission_allowed"])

    def test_missing_or_mismatched_ledger_receipt_binding_blocks(self):
        g0, ready, g4, audit, g2 = proofs()
        audit.pop("expected_receipt_sha256")
        missing = evaluate_completion_status(
            g0, ready, g4, audit, now=NOW, g2_proof=g2
        )
        self.assertIn(
            "g4_ledger_receipt_bound",
            missing["failure_reasons"],
        )

        audit["expected_receipt_sha256"] = "0" * 64
        mismatched = evaluate_completion_status(
            g0,
            ready,
            g4,
            audit,
            now=NOW,
            g2_proof=g2,
        )
        self.assertIn(
            "g4_ledger_receipt_bound",
            mismatched["failure_reasons"],
        )
        self.assertFalse(mismatched["paper_order_submission_allowed"])

    def test_cli_missing_evidence_writes_blocked_status(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "status.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "aurora_completion_status.py"),
                    "--g0-proof", str(directory / "g0.json"),
                    "--readiness", str(directory / "ready.json"),
                    "--g4-shadow", str(directory / "g4.json"),
                    "--ledger-audit", str(directory / "audit.json"),
                    "--output", str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertFalse(payload["paper_order_submission_allowed"])

    def test_completion_components_have_no_submission_path(self):
        sources = [
            (ROOT / "scripts" / "aurora_completion_status.py").read_text(),
            (ROOT / "scripts" / "run_aurora_completion_gate.sh").read_text(),
        ]
        for source in sources:
            for token in ["placeOrder", "submit_order", "PAPER_ENABLED", "4001"]:
                self.assertNotIn(token, source)
        self.assertIn("Paper order submission: DISABLED", sources[1])


if __name__ == "__main__":
    unittest.main()
