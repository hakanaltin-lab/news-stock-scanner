"""Unified G2/G3 runtime readiness must remain fresh and fail closed."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.aurora_readiness_summary import evaluate_readiness_bundle


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def ready_g2(timestamp=None):
    timestamp = timestamp or (NOW - timedelta(seconds=5)).isoformat()
    return {
        "run_mode": {"mode": "READ_ONLY"},
        "snapshot": {
            "timestamp": timestamp,
            "order_submission_hard_blocked": True,
        },
        "readiness": {
            "timestamp": timestamp,
            "readiness": "READY_FOR_PAPER_READ_ONLY",
            "required_failure_count": 0,
            "paper_order_submission_allowed": False,
            "live_execution_allowed": False,
        },
    }


def ready_g3(timestamp=None):
    timestamp = timestamp or (NOW - timedelta(seconds=2)).isoformat()
    return {
        "symbol": "BKR",
        "snapshot": {
            "status": "REALTIME_READY",
            "config": {
                "mode": "PAPER",
                "endpoint_safe": True,
                "host": "127.0.0.1",
                "port": 4002,
            },
            "paper_account_guard": {"paper_account_verified": True},
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
        result = evaluate_readiness_bundle(ready_g2(), ready_g3(), now=NOW)
        self.assertEqual(result["status"], "READY_FOR_CONTROLLED_DRY_RUN")
        self.assertEqual(result["failure_reasons"], [])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertFalse(result["automatic_promotion_allowed"])

    def test_stale_g2_or_g3_evidence_blocks(self):
        stale_g2 = (NOW - timedelta(seconds=301)).isoformat()
        stale_g3 = (NOW - timedelta(seconds=61)).isoformat()
        first = evaluate_readiness_bundle(ready_g2(stale_g2), ready_g3(), now=NOW)
        second = evaluate_readiness_bundle(ready_g2(), ready_g3(stale_g3), now=NOW)
        self.assertIn("g2_evidence_fresh", first["failure_reasons"])
        self.assertIn("g3_evidence_fresh", second["failure_reasons"])

    def test_live_port_or_unverified_account_blocks(self):
        proof = ready_g3()
        proof["snapshot"]["config"]["port"] = 4001
        proof["snapshot"]["paper_account_guard"]["paper_account_verified"] = False
        result = evaluate_readiness_bundle(ready_g2(), proof, now=NOW)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn("g3_paper_loopback_endpoint", result["failure_reasons"])
        self.assertIn("g3_paper_account_verified", result["failure_reasons"])

    def test_missing_or_order_enabled_evidence_blocks(self):
        proof = ready_g3()
        proof["paper_order_submission_allowed"] = True
        result = evaluate_readiness_bundle({}, proof, now=NOW)
        self.assertEqual(result["status"], "NOT_READY")
        self.assertIn("g2_ready", result["failure_reasons"])
        self.assertIn("g3_order_submission_blocked", result["failure_reasons"])

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
        self.assertIn("summary_status=0", source)
        self.assertIn("g2_status != 0 || g3_status != 0", source)


if __name__ == "__main__":
    unittest.main()
