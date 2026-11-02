"""G8.10 tests for trusted G5 manual Paper authorization artifacts."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from engines.paper_order_authorization_gate import (
    AUTH_VERSION,
)
from scripts.g5_manual_authorization_preflight import (
    evaluate_trusted_g5_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)


def digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def safe_flags():
    return {
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def shadow_order():
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order_id": "shadow-g8-10-001",
        "idempotency_key": "intent-g8-10-001",
        "symbol": "BKR",
        "action": "BUY",
        "quantity": 1,
        "limit_price": 50.0,
        **safe_flags(),
    }


def g4_shadow(order=None):
    order = order or shadow_order()
    return {
        "status": "SHADOW_ACCEPTED",
        "shadow_order": order,
        **safe_flags(),
    }


def completion(order=None):
    order = order or shadow_order()
    return {
        "status": "PAPER_RUNTIME_VALIDATED_SHADOW_ONLY",
        "next_gate": "MANUAL_PAPER_ORDER_AUTHORIZATION_NOT_GRANTED",
        "checks": {
            "g4_shadow_order_payload_valid": True,
            "g4_shadow_order_ledger_payload_bound": True,
        },
        "evidence_binding": {
            "g4_shadow_order_sha256": digest(order),
        },
        "failure_reasons": [],
        **safe_flags(),
    }


def authorization(comp=None, order=None, now=NOW):
    order = order or shadow_order()
    comp = comp or completion(order)
    return {
        "version": AUTH_VERSION,
        "authorization_id": (
            "11111111-1111-4111-8111-111111111111"
        ),
        "approved": True,
        "mode": "PAPER",
        "scope": "ONE_PAPER_ORDER",
        "issued_at": (
            now - timedelta(seconds=10)
        ).isoformat(),
        "expires_at": (
            now + timedelta(minutes=5)
        ).isoformat(),
        "completion_status_sha256": digest(comp),
        "shadow_order_sha256": digest(order),
        **safe_flags(),
    }


def write_trusted(path, payload, mode=0o600):
    Path(path).write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    Path(path).chmod(mode)


class TrustedG5AuthorizationTests(unittest.TestCase):
    def test_trusted_authorization_is_preflight_only(self):
        order = shadow_order()
        comp = completion(order)

        result = evaluate_trusted_g5_preflight(
            comp,
            g4_shadow(order),
            authorization(comp, order),
            now=NOW,
        )

        self.assertEqual(
            result["status"],
            "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
        )
        self.assertTrue(
            result["authorization_is_pre_execution_only"]
        )
        self.assertEqual(
            result["next_gate"],
            "PAPER_EXECUTION_CONNECTOR_REVIEW_REQUIRED",
        )
        for name, value in safe_flags().items():
            self.assertIs(result[name], value)

    def test_g4_top_level_permission_regression_blocks(self):
        order = shadow_order()
        comp = completion(order)
        g4 = g4_shadow(order)
        g4["paper_order_submission_allowed"] = True

        result = evaluate_trusted_g5_preflight(
            comp,
            g4,
            authorization(comp, order),
            now=NOW,
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "G4_SHADOW_PROOF_NOT_SAFE",
        )
        self.assertFalse(
            result["paper_order_submission_allowed"]
        )

    def test_cli_accepts_only_trusted_files_and_writes_0600_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            order = shadow_order()
            comp = completion(order)
            now = datetime.now(timezone.utc)
            auth = authorization(comp, order, now=now)

            completion_path = root / "completion.json"
            g4_path = root / "g4.json"
            auth_path = root / "authorization.json"
            output = root / "validated.json"

            write_trusted(completion_path, comp)
            write_trusted(g4_path, g4_shadow(order))
            write_trusted(auth_path, auth)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "g5_manual_authorization_preflight.py"
                    ),
                    "--authorization",
                    str(auth_path),
                    "--completion-status",
                    str(completion_path),
                    "--g4-shadow",
                    str(g4_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=completed.stdout + completed.stderr,
            )
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                payload["status"],
                "MANUAL_PAPER_AUTHORIZATION_VALIDATED",
            )
            metadata = output.stat()
            self.assertTrue(
                stat.S_ISREG(metadata.st_mode)
            )
            self.assertEqual(
                stat.S_IMODE(metadata.st_mode),
                0o600,
            )
            self.assertEqual(metadata.st_nlink, 1)
            self.assertFalse(
                payload["paper_order_submission_allowed"]
            )
            self.assertFalse(
                payload["real_money_trading_allowed"]
            )

    def test_cli_rejects_broad_or_symlink_authorization_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            order = shadow_order()
            comp = completion(order)
            now = datetime.now(timezone.utc)

            completion_path = root / "completion.json"
            g4_path = root / "g4.json"
            auth_path = root / "authorization.json"
            output = root / "validated.json"

            write_trusted(completion_path, comp)
            write_trusted(g4_path, g4_shadow(order))
            write_trusted(
                auth_path,
                authorization(comp, order, now=now),
                mode=0o644,
            )

            broad = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "g5_manual_authorization_preflight.py"
                    ),
                    "--authorization",
                    str(auth_path),
                    "--completion-status",
                    str(completion_path),
                    "--g4-shadow",
                    str(g4_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(broad.returncode, 2)
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertFalse(
                payload["paper_order_submission_allowed"]
            )

            target = root / "human-auth-target.json"
            write_trusted(
                target,
                authorization(comp, order, now=now),
            )
            auth_path.unlink()
            auth_path.symlink_to(target)
            output.unlink()

            symlinked = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "g5_manual_authorization_preflight.py"
                    ),
                    "--authorization",
                    str(auth_path),
                    "--completion-status",
                    str(completion_path),
                    "--g4-shadow",
                    str(g4_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(symlinked.returncode, 2)
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertFalse(
                payload["real_money_trading_allowed"]
            )

    def test_cli_rejects_authorization_permission_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            order = shadow_order()
            comp = completion(order)
            now = datetime.now(timezone.utc)
            auth = authorization(comp, order, now=now)
            auth["paper_order_submission_allowed"] = True

            completion_path = root / "completion.json"
            g4_path = root / "g4.json"
            auth_path = root / "authorization.json"
            output = root / "validated.json"

            write_trusted(completion_path, comp)
            write_trusted(g4_path, g4_shadow(order))
            write_trusted(auth_path, auth)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "g5_manual_authorization_preflight.py"
                    ),
                    "--authorization",
                    str(auth_path),
                    "--completion-status",
                    str(completion_path),
                    "--g4-shadow",
                    str(g4_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            payload = json.loads(
                output.read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["status"], "BLOCKED")
            self.assertFalse(
                payload["paper_order_submission_allowed"]
            )


if __name__ == "__main__":
    unittest.main()
