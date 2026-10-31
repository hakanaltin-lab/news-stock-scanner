"""G0-bound G2/G3 runtime readiness must remain fresh and fail closed."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.aurora_readiness_summary import evaluate_readiness_bundle


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
ACCOUNT_FINGERPRINT = "IBKR-A1B2C3D4E5"
EVIDENCE_RUN_ID = "11111111-1111-4111-8111-111111111111"
G2_REQUIRED_CHECKS = [
    "paper_mode_only",
    "safe_loopback_paper_endpoint",
    "paper_account_identity_verified",
    "order_submission_hard_blocked",
    "live_trading_hard_blocked",
    "gateway_connected",
    "single_managed_account_for_readiness",
    "account_summary_accounts_match_managed_accounts",
    "position_accounts_match_verified_paper_accounts",
]


def digest(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verified_g0(timestamp=None):
    timestamp = timestamp or (NOW - timedelta(minutes=5)).isoformat()
    return {
        "generated_at": timestamp,
        "status": "G0_G1_VERIFIED",
        "failure_reasons": [],
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def ready_g2(timestamp=None):
    timestamp = timestamp or (NOW - timedelta(seconds=5)).isoformat()
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "run_mode": {"mode": "READ_ONLY"},
        "snapshot": {
            "timestamp": timestamp,
            "order_submission_hard_blocked": True,
            "paper_account_guard": {
                "paper_account_verified": True,
                "verified_account_fingerprints": [ACCOUNT_FINGERPRINT],
            },
        },
        "readiness": {
            "timestamp": timestamp,
            "readiness": "READY_FOR_PAPER_READ_ONLY",
            "required_failure_count": 0,
            "checks": [
                {
                    "check": name,
                    "required": True,
                    "passed": True,
                }
                for name in G2_REQUIRED_CHECKS
            ],
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
        },
    }


def ready_g3(timestamp=None):
    timestamp = timestamp or (NOW - timedelta(seconds=2)).isoformat()
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "symbol": "BKR",
        "snapshot": {
            "status": "REALTIME_READY",
            "config": {
                "mode": "PAPER",
                "endpoint_safe": True,
                "host": "127.0.0.1",
                "port": 4002,
            },
            "paper_account_guard": {
                "paper_account_verified": True,
                "verified_account_fingerprints": [ACCOUNT_FINGERPRINT],
            },
            "quote": {
                "source": "IBKR_REALTIME",
                "market_data_type_name": "REALTIME",
                "market_timestamp": timestamp,
                "execution_eligible": True,
            },
        },
        "execution_market_data_gate": {
            "decision": "PASS",
            "execution_eligible": True,
        },
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
    }


class AuroraReadinessSummaryTests(unittest.TestCase):
    def test_fresh_safe_g2_g3_evidence_passes(self):
        g2 = ready_g2()
        g3 = ready_g3()
        g0 = verified_g0()
        result = evaluate_readiness_bundle(
            g2,
            g3,
            now=NOW,
            g0_proof=g0,
        )
        self.assertEqual(result["status"], "READY_FOR_CONTROLLED_DRY_RUN")
        self.assertEqual(result["failure_reasons"], [])
        self.assertTrue(result["checks"]["g2_g3_paper_account_bound"])
        self.assertTrue(result["checks"]["g2_g3_same_evidence_run"])
        self.assertEqual(result["evidence_run_id"], EVIDENCE_RUN_ID)
        self.assertEqual(
            result["paper_account_fingerprints"],
            [ACCOUNT_FINGERPRINT],
        )
        self.assertEqual(
            result["g0_g1_proof_sha256"],
            digest(g0),
        )
        self.assertEqual(
            result["g2_paper_read_only_proof_sha256"],
            digest(g2),
        )
        self.assertEqual(
            result["g3_market_data_proof_sha256"],
            digest(g3),
        )
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_promotion_allowed"])

    def test_g2_required_failure_count_must_match_checks(self):
        g2 = ready_g2()
        g2["readiness"]["checks"][0]["passed"] = False
        result = evaluate_readiness_bundle(
            g2,
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn(
            "g2_required_checks_consistent",
            result["failure_reasons"],
        )

    def test_g2_cannot_omit_expected_required_check(self):
        g2 = ready_g2()
        g2["readiness"]["checks"] = [
            item
            for item in g2["readiness"]["checks"]
            if item["check"] != "order_submission_hard_blocked"
        ]
        result = evaluate_readiness_bundle(
            g2,
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn(
            "g2_required_checks_consistent",
            result["failure_reasons"],
        )

    def test_mismatched_evidence_run_id_blocks(self):
        g3 = ready_g3()
        g3["evidence_run_id"] = "22222222-2222-4222-8222-222222222222"
        result = evaluate_readiness_bundle(
            ready_g2(),
            g3,
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn(
            "g2_g3_same_evidence_run",
            result["failure_reasons"],
        )
        self.assertIsNone(result["evidence_run_id"])

    def test_missing_or_malformed_evidence_run_id_blocks(self):
        missing = ready_g2()
        missing.pop("evidence_run_id")
        malformed = ready_g3()
        malformed["evidence_run_id"] = "not-a-uuid"
        first = evaluate_readiness_bundle(
            missing,
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(),
        )
        second = evaluate_readiness_bundle(
            ready_g2(),
            malformed,
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertIn("g2_g3_same_evidence_run", first["failure_reasons"])
        self.assertIn("g2_g3_same_evidence_run", second["failure_reasons"])

    def test_missing_account_fingerprint_blocks(self):
        g2 = ready_g2()
        del g2["snapshot"]["paper_account_guard"][
            "verified_account_fingerprints"
        ]
        result = evaluate_readiness_bundle(
            g2,
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn(
            "g2_g3_paper_account_bound",
            result["failure_reasons"],
        )
        self.assertEqual(result["paper_account_fingerprints"], [])
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_mismatched_account_fingerprint_blocks(self):
        g3 = ready_g3()
        g3["snapshot"]["paper_account_guard"][
            "verified_account_fingerprints"
        ] = ["IBKR-0F1E2D3C4B"]
        result = evaluate_readiness_bundle(
            ready_g2(),
            g3,
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn(
            "g2_g3_paper_account_bound",
            result["failure_reasons"],
        )
        self.assertEqual(result["paper_account_fingerprints"], [])
        self.assertFalse(result["live_execution_allowed"])

    def test_stale_g2_or_g3_evidence_blocks(self):
        stale_g2 = (NOW - timedelta(seconds=301)).isoformat()
        stale_g3 = (NOW - timedelta(seconds=61)).isoformat()
        first = evaluate_readiness_bundle(
            ready_g2(stale_g2),
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(),
        )
        second = evaluate_readiness_bundle(
            ready_g2(),
            ready_g3(stale_g3),
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertIn("g2_evidence_fresh", first["failure_reasons"])
        self.assertIn("g3_evidence_fresh", second["failure_reasons"])

    def test_live_port_or_unverified_account_blocks(self):
        proof = ready_g3()
        proof["snapshot"]["config"]["port"] = 4001
        proof["snapshot"]["paper_account_guard"]["paper_account_verified"] = False
        result = evaluate_readiness_bundle(
            ready_g2(),
            proof,
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn("g3_paper_loopback_endpoint", result["failure_reasons"])
        self.assertIn("g3_paper_account_verified", result["failure_reasons"])

    def test_missing_or_order_enabled_evidence_blocks(self):
        proof = ready_g3()
        proof["paper_order_submission_allowed"] = True
        result = evaluate_readiness_bundle(
            {},
            proof,
            now=NOW,
            g0_proof=verified_g0(),
        )
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn("g2_ready", result["failure_reasons"])
        self.assertIn("g3_order_submission_blocked", result["failure_reasons"])

    def test_missing_or_stale_g0_evidence_blocks(self):
        missing = evaluate_readiness_bundle(
            ready_g2(),
            ready_g3(),
            now=NOW,
            g0_proof={},
        )
        stale = evaluate_readiness_bundle(
            ready_g2(),
            ready_g3(),
            now=NOW,
            g0_proof=verified_g0(
                (NOW - timedelta(seconds=86401)).isoformat()
            ),
        )
        unsafe_g0 = verified_g0()
        unsafe_g0["paper_order_submission_allowed"] = True
        unsafe = evaluate_readiness_bundle(
            ready_g2(),
            ready_g3(),
            now=NOW,
            g0_proof=unsafe_g0,
        )
        self.assertIn("g0_g1_verified", missing["failure_reasons"])
        self.assertIn(
            "g0_g1_evidence_current",
            stale["failure_reasons"],
        )
        self.assertIn("g0_g1_verified", unsafe["failure_reasons"])

    def test_cli_writes_blocked_artifact_when_proofs_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "readiness.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "aurora_readiness_summary.py"),
                    "--g2-proof", str(Path(directory) / "missing-g2.json"),
                    "--g3-proof", str(Path(directory) / "missing-g3.json"),
                    "--output", str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "NOT_READY")
            self.assertFalse(payload["paper_order_submission_allowed"])
            self.assertFalse(payload["live_execution_allowed"])

    def test_wrapper_contains_no_order_submission_path(self):
        source = (
            ROOT / "scripts" / "run_aurora_g2_g3_readiness.sh"
        ).read_text(encoding="utf-8")
        for token in ["placeOrder", "submit_order", "PAPER_ENABLED", "4001"]:
            self.assertNotIn(token, source)
        self.assertIn("AURORA_IBKR_MARKET_DATA_ENABLED=true", source)
        self.assertIn("uuid.uuid4()", source)
        self.assertIn("export AURORA_EVIDENCE_RUN_ID", source)
        self.assertIn("summary_status=0", source)
        self.assertIn("g2_status != 0 || g3_status != 0", source)


if __name__ == "__main__":
    unittest.main()
