"""G8.30 negative safety tests. Mock signature_valid=True is NOT real approval."""
import base64
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import unittest
from engines.ibkr_order_object_candidate_review import (
    evaluate_order_object_candidate,PERMISSION_FLAGS,
)
from engines.ibkr_order_object_candidate_handoff import evaluate_order_object_candidate_handoff
from engines.ibkr_order_object_candidate_attestation import (
    evaluate_signed_order_object_candidate_attestation,
    canonical_signed_payload,NEXT_GATE,
)
from engines.ibkr_order_object_design_attestation import (
    ENGINE_VERSION as DESIGN_ENGINE,NEXT_GATE as DESIGN_NEXT_GATE,
)
NOW=datetime(2026,11,3,10,0,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]
KEY=b"-----BEGIN PUBLIC KEY-----\nMOCK-KEY-NOT-FOR-REAL-CRYPTO\n-----END PUBLIC KEY-----\n"
REVIEWER="independent-g8-30-reviewer"
def source():return (ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py").read_text()
def upstream():
    return {
        "engine":DESIGN_ENGINE,"status":"VERIFIED","verified":True,
        "order_object_design_independently_attested":True,
        "reason":"INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_VERIFIED",
        "checks":{"signature_valid":True},
        "review_id":"77777777-7777-4777-8777-777777777777",
        "reviewer_id":"prior-reviewer","design_sha256":"1"*64,
        "review_request_sha256":"2"*64,
        "upstream_attestation_result_sha256":"3"*64,
        "attestation_sha256":"4"*64,
        **{k:False for k in PERMISSION_FLAGS},
        "next_gate":DESIGN_NEXT_GATE,
    }
def evidence():
    d=upstream();s=source()
    c=evaluate_order_object_candidate(d,s,now=NOW)
    assert c["candidate_validated"]
    h=evaluate_order_object_candidate_handoff(c,s,d,now=NOW-timedelta(minutes=2))
    assert h["ready_for_independent_review"]
    return c,h,s,d
def policy():
    return {
        "policy_version":1,"reviewer_id":REVIEWER,
        "public_key_sha256":hashlib.sha256(KEY).hexdigest(),
        "expected_candidate_version":"AURORA_G8_28_ORDER_OBJECT_CANDIDATE_V1",
        "max_attestation_age_seconds":1800,"allowed_clock_skew_seconds":60,
    }
def artifact():
    _,h,_,_=evidence()
    return {
        **h["unsigned_attestation_template"],"decision":"ATTESTED",
        "review_id":"88888888-8888-4888-8888-888888888888",
        "reviewer_id":REVIEWER,
        "captured_at_utc":(NOW-timedelta(minutes=1)).isoformat(),
        "expires_at_utc":(NOW+timedelta(minutes=10)).isoformat(),
        "reviewer_confirms_non_executable":True,
        "reviewer_confirms_hard_disabled_methods":True,
        "reviewer_confirms_no_broker_imports":True,
        "reviewer_confirms_transmit_false":True,
        "reviewer_evidence_sha256":"f"*64,
        "signature_b64":base64.b64encode(b"s"*64).decode("ascii"),
    }
class CandidateSignedReviewTests(unittest.TestCase):
    def check(self,a=None,p=None,h=None,c=None,s=None,d=None,signature_valid=True,clean=True):
        base_c,base_h,base_s,base_d=evidence()
        return evaluate_signed_order_object_candidate_attestation(
            artifact() if a is None else a,
            policy() if p is None else p,KEY,signature_valid,
            base_h if h is None else h,base_s if s is None else s,
            base_c if c is None else c,base_d if d is None else d,
            clean,now=NOW,
        )
    def test_valid_test_fixture_only_verifies_review(self):
        r=self.check()
        self.assertEqual(r["status"],"VERIFIED",r["checks"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        for flag in PERMISSION_FLAGS:self.assertIs(r[flag],False)
    def test_unsigned_never_accepted(self):
        _,h,_,_=evidence()
        self.assertEqual(self.check(a=h["unsigned_attestation_template"])["status"],"BLOCKED")
    def test_signature_failure_blocks(self):
        self.assertEqual(self.check(signature_valid=False)["status"],"BLOCKED")
    def test_key_mismatch_and_identity_block(self):
        p=policy();p["public_key_sha256"]="0"*64
        self.assertEqual(self.check(p=p)["status"],"BLOCKED")
        a=artifact();a["reviewer_id"]="wrong-reviewer"
        self.assertEqual(self.check(a=a)["status"],"BLOCKED")
    def test_expiry_and_future_clock_block(self):
        a=artifact();a["expires_at_utc"]=(NOW-timedelta(minutes=1)).isoformat()
        self.assertEqual(self.check(a=a)["status"],"BLOCKED")
        a=artifact();a["captured_at_utc"]=(NOW+timedelta(minutes=5)).isoformat()
        self.assertEqual(self.check(a=a)["status"],"BLOCKED")
    def test_candidate_mutation_blocks(self):
        s=source().replace('raise RuntimeError("G8_28_ORDER_CREATION_DISABLED")',"return True")
        self.assertEqual(self.check(s=s)["status"],"BLOCKED")
    def test_request_tamper_blocks(self):
        _,h,_,_=evidence()
        h["review_request"]["candidate_source_sha256"]="0"*64
        self.assertEqual(self.check(h=h)["status"],"BLOCKED")
    def test_candidate_review_and_prior_attestation_tamper_blocks(self):
        c,_,_,d=evidence()
        c["candidate_source_sha256"]="0"*64
        self.assertEqual(self.check(c=c)["status"],"BLOCKED")
        d["real_money_trading_allowed"]=True
        self.assertEqual(self.check(d=d)["status"],"BLOCKED")
    def test_permissions_and_dirty_repository_block(self):
        a=artifact();a["reviewer_confirms_hard_disabled_methods"]=False
        self.assertEqual(self.check(a=a)["status"],"BLOCKED")
        self.assertEqual(self.check(clean=False)["status"],"BLOCKED")
    def test_extra_field_sanitized(self):
        a=artifact();a["credentials"]="PRIVATE"
        r=self.check(a=a)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertNotIn("PRIVATE",json.dumps(r))
    def test_signed_payload_excludes_only_signature(self):
        a=artifact();payload=json.loads(canonical_signed_payload(a))
        self.assertNotIn("signature_b64",payload)
        self.assertEqual(payload["candidate_source_sha256"],a["candidate_source_sha256"])
if __name__=="__main__":unittest.main()
