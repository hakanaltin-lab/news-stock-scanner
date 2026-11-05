"""G8.24 tests for signed independent offline materializer attestation."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from engines.offline_order_request_materializer_attestation import (
    NEXT_GATE,
    canonical_signed_payload,
    evaluate_materializer_attestation,
)
from engines.offline_order_request_materializer_handoff import (
    evaluate_materializer_review_handoff,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from scripts import verify_offline_materializer_attestation as cli


NOW = datetime(2026, 11, 3, 7, 0, tzinfo=timezone.utc)
REVIEW_ID = "44444444-4444-4444-8444-444444444444"
REVIEWER = "aurora-offline-materializer-reviewer"
PUBLIC_KEY = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"TEST-OFFLINE-MATERIALIZER-REVIEW-KEY\n"
    b"-----END PUBLIC KEY-----\n"
)
ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config/offline_order_request_materializer_design_v1.json"
MATERIALIZER_PATH = ROOT / "engines/offline_order_request_materializer.py"
CLI_PATH = ROOT / "scripts/build_offline_order_request_preview.py"


def design():
    return json.loads(DESIGN_PATH.read_text(encoding="utf-8"))


def materializer_source():
    return MATERIALIZER_PATH.read_text(encoding="utf-8")


def cli_source():
    return CLI_PATH.read_text(encoding="utf-8")


def handoff():
    value = evaluate_materializer_review_handoff(
        design(),
        materializer_source(),
        cli_source(),
        now=NOW - timedelta(minutes=2),
    )
    assert (
        value["status"]
        == "READY_FOR_INDEPENDENT_OFFLINE_MATERIALIZER_REVIEW"
    )
    return value


def policy():
    return {
        "policy_version": 1,
        "reviewer_id": REVIEWER,
        "public_key_sha256": hashlib.sha256(PUBLIC_KEY).hexdigest(),
        "expected_design_id": (
            "AURORA_G8_22_OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_V1"
        ),
        "max_attestation_age_seconds": 1800,
        "allowed_clock_skew_seconds": 60,
    }


def artifact():
    template = handoff()["unsigned_attestation_template"]
    return {
        **template,
        "materializer_review_id": REVIEW_ID,
        "decision": "ATTESTED",
        "reviewer_id": REVIEWER,
        "captured_at_utc": (
            NOW - timedelta(seconds=30)
        ).isoformat(),
        "expires_at_utc": (
            NOW + timedelta(minutes=10)
        ).isoformat(),
        "reviewer_confirms_offline_only": True,
        "reviewer_confirms_no_broker_imports": True,
        "reviewer_confirms_no_network_path": True,
        "reviewer_confirms_fail_closed_intent_schema": True,
        "reviewer_evidence_sha256": "9" * 64,
        "signature_b64": base64.b64encode(b"s" * 64).decode("ascii"),
    }


class OfflineMaterializerAttestationTests(unittest.TestCase):
    def evaluate(
        self,
        artifact_value=None,
        policy_value=None,
        public_key=PUBLIC_KEY,
        signature_valid=True,
        handoff_value=None,
        design_value=None,
        materializer_value=None,
        cli_value=None,
        repository_clean=True,
        now=NOW,
    ):
        return evaluate_materializer_attestation(
            artifact_value if artifact_value is not None else artifact(),
            policy_value if policy_value is not None else policy(),
            public_key,
            signature_valid,
            handoff_value if handoff_value is not None else handoff(),
            design_value if design_value is not None else design(),
            (
                materializer_value
                if materializer_value is not None
                else materializer_source()
            ),
            cli_value if cli_value is not None else cli_source(),
            repository_clean,
            now=now,
        )

    def assert_permissions_false(self, result):
        for name in PERMISSION_FLAGS:
            self.assertIs(result[name], False)

    def test_valid_attestation_verifies_without_enabling_execution(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["verified"])
        self.assertTrue(result["offline_materializer_independently_attested"])
        self.assertEqual(result["materializer_review_id"], REVIEW_ID)
        self.assertEqual(result["next_gate"], NEXT_GATE)
        self.assertTrue(all(result["checks"].values()))
        self.assert_permissions_false(result)

    def test_unsigned_template_cannot_verify(self):
        result = self.evaluate(
            artifact_value=handoff()["unsigned_attestation_template"]
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["artifact_identity"])
        self.assertFalse(result["checks"]["materializer_review_id_uuid4"])

    def test_signature_and_key_mismatch_block(self):
        result = self.evaluate(signature_valid=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["ed25519_signature_valid"])

        bad = policy()
        bad["public_key_sha256"] = "f" * 64
        result = self.evaluate(policy_value=bad)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["public_key_matches_policy"])

    def test_reviewer_confirmations_are_required(self):
        for field in (
            "reviewer_confirms_offline_only",
            "reviewer_confirms_no_broker_imports",
            "reviewer_confirms_no_network_path",
            "reviewer_confirms_fail_closed_intent_schema",
        ):
            with self.subTest(field=field):
                value = artifact()
                value[field] = False
                result = self.evaluate(artifact_value=value)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["checks"][field])

    def test_design_tamper_blocks(self):
        value = design()
        value["market_order_allowed"] = True
        result = self.evaluate(design_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["design_policy_and_digest_bound"])

    def test_materializer_or_cli_tamper_blocks(self):
        changed = materializer_source() + "\nimport ibapi\n"
        result = self.evaluate(materializer_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["materializer_source_policy_and_digest_bound"]
        )

        changed_cli = cli_source() + "\nimport requests\n"
        result = self.evaluate(cli_value=changed_cli)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["cli_source_policy_and_digest_bound"])

    def test_unsafe_duplicate_materializer_marker_blocks(self):
        changed = materializer_source().replace(
            '"network_accessed": False',
            '"network_accessed": True',
            1,
        )
        result = self.evaluate(materializer_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["materializer_source_policy_and_digest_bound"]
        )
        self.assert_permissions_false(result)

    def test_duplicate_materializer_entrypoint_blocks(self):
        changed = (
            materializer_source()
            + "\n\ndef materialize_offline_order_request(*args, **kwargs):\n"
            "    return None\n"
        )
        result = self.evaluate(materializer_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(
            result["checks"]["materializer_source_policy_and_digest_bound"]
        )
        self.assert_permissions_false(result)

    def test_handoff_tamper_and_extra_field_block(self):
        changed = handoff()
        changed["review_request_sha256"] = "f" * 64
        result = self.evaluate(handoff_value=changed)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["review_request_digest_bound"])

        value = artifact()
        value["raw_account_id"] = "DU1234567"
        result = self.evaluate(artifact_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["artifact_field_set_exact"])
        self.assertNotIn("DU1234567", json.dumps(result))

    def test_expired_future_dirty_block(self):
        value = artifact()
        value["expires_at_utc"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()
        result = self.evaluate(artifact_value=value)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["attestation_not_expired"])

        result = self.evaluate(repository_clean=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["checks"]["repository_clean"])

    def test_signature_payload_excludes_only_signature(self):
        value = artifact()
        decoded = json.loads(
            canonical_signed_payload(value).decode("utf-8")
        )
        self.assertNotIn("signature_b64", decoded)
        for key, item in value.items():
            if key != "signature_b64":
                self.assertEqual(decoded[key], item)

    def test_paths_are_fixed_and_cli_has_no_signing_path(self):
        self.assertEqual(
            str(cli.DEFAULT_POLICY_PATH),
            "/etc/aurora/offline-materializer-review-policy.json",
        )
        self.assertEqual(
            str(cli.DEFAULT_PUBLIC_KEY_PATH),
            "/etc/aurora/offline-materializer-reviewer-ed25519.pem",
        )
        self.assertEqual(
            str(cli.DEFAULT_ARTIFACT_PATH),
            "/var/lib/aurora/offline-materializer-review-attestation/latest.json",
        )

        text = inspect.getsource(cli).lower()
        for token in (
            "private_key",
            "private-key",
            "pkeyutl -sign",
            "placeorder",
            "submit_order(",
        ):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
