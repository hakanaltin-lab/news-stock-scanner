"""G8.27 fail-closed independent signed design verifier tests."""
from datetime import datetime,timedelta,timezone
import base64
import hashlib
import json
import unittest
from pathlib import Path
from engines.ibkr_order_object_design_attestation import (
    NEXT_GATE,canonical_signed_payload,evaluate_signed_order_object_design_attestation,
)
from engines.ibkr_order_object_design_handoff import evaluate_order_object_design_handoff
from engines.offline_order_request_materializer_attestation import (
    ENGINE_VERSION as UPSTREAM_ENGINE,NEXT_GATE as UPSTREAM_GATE,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from scripts import verify_order_object_design_attestation as cli
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,3,9,0,tzinfo=timezone.utc)
PUBKEY=b"-----BEGIN PUBLIC KEY-----\nTEST-REVIEW-PUBLIC-KEY\n-----END PUBLIC KEY-----\n"
REVIEWER="aurora-order-object-design-reviewer"

def design():
    return json.loads((ROOT/"config/ibkr_order_object_materializer_design_v1.json").read_text())
def upstream():
    return {
        "engine":UPSTREAM_ENGINE,"status":"VERIFIED","verified":True,
        "offline_materializer_independently_attested":True,
        "reason":"INDEPENDENT_OFFLINE_MATERIALIZER_ATTESTATION_VERIFIED",
        "checks":{"signature":True},
        "materializer_review_id":"55555555-5555-4555-8555-555555555555",
        "reviewer_id":"independent-reviewer",
        "captured_at_utc":(NOW-timedelta(minutes=2)).isoformat(),
        "expires_at_utc":(NOW+timedelta(minutes=15)).isoformat(),
        "review_request_sha256":"1"*64,"design_sha256":"2"*64,
        "materializer_source_sha256":"3"*64,"cli_source_sha256":"4"*64,
        "materializer_attestation_sha256":"5"*64,"reviewer_evidence_sha256":"6"*64,
        **{k:False for k in PERMISSION_FLAGS},"next_gate":UPSTREAM_GATE,
    }
def handoff():
    result=evaluate_order_object_design_handoff(design(),upstream(),now=NOW-timedelta(minutes=1))
    assert result["ready_for_independent_review"]
    return result
def policy():
    return {"policy_version":1,"reviewer_id":REVIEWER,
        "public_key_sha256":hashlib.sha256(PUBKEY).hexdigest(),
        "expected_design_id":"AURORA_G8_25_IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_V1",
        "max_attestation_age_seconds":1800,"allowed_clock_skew_seconds":60}
def artifact():
    template=handoff()["unsigned_attestation_template"]
    return {**template,
        "decision":"ATTESTED","review_id":"77777777-7777-4777-8777-777777777777",
        "reviewer_id":REVIEWER,
        "captured_at_utc":(NOW-timedelta(seconds=30)).isoformat(),
        "expires_at_utc":(NOW+timedelta(minutes=10)).isoformat(),
        "reviewer_confirms_design_only":True,
        "reviewer_confirms_no_broker_objects":True,
        "reviewer_confirms_paper_only":True,
        "reviewer_confirms_transmit_false":True,
        "reviewer_evidence_sha256":"9"*64,
        "signature_b64":base64.b64encode(b"s"*64).decode("ascii")}
class SignedDesignAttestationTests(unittest.TestCase):
    def evaluate(self,a=None,p=None,h=None,d=None,u=None,signature_valid=True,clean=True):
        return evaluate_signed_order_object_design_attestation(
            a if a is not None else artifact(),
            p if p is not None else policy(),PUBKEY,signature_valid,
            h if h is not None else handoff(),d if d is not None else design(),
            u if u is not None else upstream(),clean,now=NOW)
    def test_valid_signed_evidence_only_enables_review(self):
        r=self.evaluate()
        self.assertEqual(r["status"],"VERIFIED",r["checks"])
        self.assertTrue(r["order_object_design_independently_attested"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        for k in PERMISSION_FLAGS:self.assertIs(r[k],False)
    def test_unsigned_template_denied(self):
        r=self.evaluate(a=handoff()["unsigned_attestation_template"])
        self.assertEqual(r["status"],"BLOCKED")
    def test_bad_signature_and_key_denied(self):
        self.assertEqual(self.evaluate(signature_valid=False)["status"],"BLOCKED")
        p=policy();p["public_key_sha256"]="f"*64
        self.assertEqual(self.evaluate(p=p)["status"],"BLOCKED")
    def test_missing_review_confirmations_denied(self):
        for key in ("reviewer_confirms_design_only","reviewer_confirms_no_broker_objects",
                    "reviewer_confirms_paper_only","reviewer_confirms_transmit_false"):
            with self.subTest(key=key):
                a=artifact();a[key]=False
                self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
    def test_expired_or_future_review_denied(self):
        a=artifact();a["expires_at_utc"]=(NOW-timedelta(seconds=1)).isoformat()
        self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
        a=artifact();a["captured_at_utc"]=(NOW+timedelta(minutes=5)).isoformat()
        self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
    def test_design_and_upstream_tamper_denied(self):
        d=design();d["broker_mode"]="LIVE"
        self.assertEqual(self.evaluate(d=d)["status"],"BLOCKED")
        u=upstream();u["broker_order_object_allowed"]=True
        self.assertEqual(self.evaluate(u=u)["status"],"BLOCKED")
    def test_handoff_digest_tamper_denied(self):
        h=handoff();h["review_request_sha256"]="f"*64
        self.assertEqual(self.evaluate(h=h)["status"],"BLOCKED")
    def test_schema_expansion_and_dirty_repo_denied(self):
        a=artifact();a["raw_account_id"]="DU123456"
        r=self.evaluate(a=a)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertNotIn("DU123456",json.dumps(r))
        self.assertEqual(self.evaluate(clean=False)["status"],"BLOCKED")
    def test_canonical_signature_excludes_only_signature(self):
        a=artifact();data=json.loads(canonical_signed_payload(a))
        self.assertNotIn("signature_b64",data)
        self.assertEqual(data["review_request_sha256"],a["review_request_sha256"])
    def test_fixed_trust_paths(self):
        self.assertEqual(str(cli.POLICY),"/etc/aurora/order-object-design-review-policy.json")
        self.assertEqual(str(cli.PUBKEY),"/etc/aurora/order-object-design-reviewer-ed25519.pem")
        self.assertEqual(str(cli.ARTIFACT),"/var/lib/aurora/order-object-design-attestation/latest.json")
if __name__=="__main__":unittest.main()
