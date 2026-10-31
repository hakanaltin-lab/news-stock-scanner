"""V8.9.22 runtime shadow execution must remain broker-independent."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.aurora_g4_shadow import evaluate_runtime_shadow


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


def readiness(timestamp=None, market=None):
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "generated_at": timestamp or (NOW - timedelta(seconds=2)).isoformat(),
        "status": "READY_FOR_CONTROLLED_DRY_RUN",
        "g3_market_data_proof_sha256": digest(
            market if market is not None else market_proof()
        ),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def market_proof(timestamp=None):
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    return {
        "evidence_run_id": EVIDENCE_RUN_ID,
        "symbol": "BKR",
        "snapshot": {
            "status": "REALTIME_READY",
            "quote": {
                "symbol": "BKR",
                "source": "IBKR_REALTIME",
                "market_data_type_name": "REALTIME",
                "bid": 49.99,
                "ask": 50.01,
                "last_price": 50.0,
                "market_timestamp": stamp,
                "broker_market_timestamp_verified": True,
                "retrieved_at": stamp,
                "execution_eligible": True,
                "data_quality": "AVAILABLE",
                "data_points": 1,
            },
        },
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
    }


def intent():
    return {
        "symbol": "BKR",
        "asset_type": "STK",
        "action": "BUY",
        "quantity": 1,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": 50.0,
        "risk_approval": "APPROVED",
        "idempotency_key": "g4-test-001",
    }


class AuroraG4ShadowTests(unittest.TestCase):
    def evaluate(self, ready=None, market=None, order=None):
        market = market if market is not None else market_proof()
        ready = ready if ready is not None else readiness(market=market)
        with patch.dict(os.environ, {"AURORA_RUN_MODE": "DRY_RUN"}):
            return evaluate_runtime_shadow(
                ready,
                market,
                order if order is not None else intent(),
                now=NOW,
            )

    def test_fresh_evidence_creates_shadow_only(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "SHADOW_ACCEPTED")
        self.assertFalse(result["broker_submission_allowed"])
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_execution_allowed"])
        self.assertEqual(
            result["shadow_order"]["status"],
            "SHADOW_ACCEPTED",
        )
        self.assertEqual(len(result["readiness_proof_sha256"]), 64)
        self.assertEqual(result["evidence_run_id"], EVIDENCE_RUN_ID)

    def test_unbound_or_mismatched_evidence_run_id_blocks(self):
        market = market_proof()
        ready = readiness(market=market)
        ready.pop("evidence_run_id")
        self.assertEqual(
            self.evaluate(ready=ready, market=market)["reason"],
            "READINESS_EVIDENCE_RUN_ID_REQUIRED",
        )

        market = market_proof()
        ready = readiness(market=market)
        market["evidence_run_id"] = (
            "22222222-2222-4222-8222-222222222222"
        )
        ready["g3_market_data_proof_sha256"] = digest(market)
        self.assertEqual(
            self.evaluate(ready=ready, market=market)["reason"],
            "READINESS_MARKET_EVIDENCE_RUN_MISMATCH",
        )

    def test_not_ready_or_stale_evidence_blocks(self):
        blocked = readiness()
        blocked["status"] = "NOT_READY"
        stale = readiness((NOW - timedelta(seconds=31)).isoformat())
        self.assertEqual(
            self.evaluate(ready=blocked)["reason"],
            "G2_G3_READINESS_REQUIRED",
        )
        self.assertEqual(
            self.evaluate(ready=stale)["reason"],
            "G2_G3_READINESS_STALE",
        )

    def test_unsafe_submission_flag_blocks(self):
        ready = readiness()
        ready["paper_order_submission_allowed"] = True
        market = market_proof()
        market["broker_submission_allowed"] = True
        self.assertEqual(
            self.evaluate(ready=ready)["reason"],
            "READINESS_SUBMISSION_FLAGS_NOT_SAFE",
        )
        self.assertEqual(
            self.evaluate(market=market)["reason"],
            "MARKET_PROOF_SUBMISSION_FLAGS_NOT_SAFE",
        )

    def test_symbol_mismatch_and_non_realtime_quote_block(self):
        order = intent()
        order["symbol"] = "NVDA"
        market = market_proof()
        market["snapshot"]["status"] = "NON_EXECUTION_DATA"
        self.assertEqual(
            self.evaluate(order=order)["reason"],
            "INTENT_MARKET_SYMBOL_MISMATCH",
        )
        self.assertEqual(
            self.evaluate(market=market)["reason"],
            "VERIFIED_REALTIME_QUOTE_REQUIRED",
        )

    def test_unbound_or_replayed_market_proof_blocks(self):
        original = market_proof()
        ready = readiness(market=original)

        missing_digest = readiness(market=original)
        del missing_digest["g3_market_data_proof_sha256"]
        self.assertEqual(
            self.evaluate(ready=missing_digest, market=original)["reason"],
            "READINESS_MARKET_PROOF_DIGEST_REQUIRED",
        )

        replayed = market_proof()
        replayed["snapshot"]["quote"]["last_price"] = 51.0
        result = self.evaluate(ready=ready, market=replayed)
        self.assertEqual(
            result["reason"],
            "READINESS_MARKET_PROOF_MISMATCH",
        )
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_read_only_mode_blocks(self):
        market = market_proof()
        with patch.dict(os.environ, {"AURORA_RUN_MODE": "READ_ONLY"}):
            result = evaluate_runtime_shadow(
                readiness(market=market),
                market,
                intent(),
                now=NOW,
            )
        self.assertEqual(result["reason"], "DRY_RUN_MODE_REQUIRED")

    def test_cli_missing_inputs_writes_blocked_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "g4.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "aurora_g4_shadow.py"),
                    "--intent", str(directory / "missing-intent.json"),
                    "--readiness-proof", str(directory / "missing-ready.json"),
                    "--market-data-proof", str(directory / "missing-market.json"),
                    "--output", str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "AURORA_RUN_MODE": "DRY_RUN"},
            )
            self.assertEqual(completed.returncode, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertFalse(payload["paper_order_submission_allowed"])

    def test_runtime_components_contain_no_broker_submission_path(self):
        python_source = (
            ROOT / "scripts" / "aurora_g4_shadow.py"
        ).read_text(encoding="utf-8")
        wrapper_source = (
            ROOT / "scripts" / "run_aurora_g4_shadow.sh"
        ).read_text(encoding="utf-8")
        for token in ["ibapi", "placeOrder", "submit_order", "4001"]:
            self.assertNotIn(token, python_source)
            self.assertNotIn(token, wrapper_source)
        self.assertIn("AURORA_RUN_MODE=DRY_RUN", wrapper_source)
        self.assertIn("run_aurora_g2_g3_readiness.sh", wrapper_source)


if __name__ == "__main__":
    unittest.main()
