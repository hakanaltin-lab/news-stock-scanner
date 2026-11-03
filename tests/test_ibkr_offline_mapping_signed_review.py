"""G8.33 fail-closed signed review tests. Mock signatures are not human reviews."""
import base64
from datetime import datetime,timedelta,timezone
import hashlib
import json
import unittest
from engines.ibkr_offline_mapping_signed_review import (
    evaluate_signed_offline_mapping_review, canonical_signed_payload, NEXT_GATE,
)
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from tests.test_ibkr_offline_mapping_review_handoff import records
from engines.ibkr_offline_mapping_review_handoff import create_offline_mapping_review_handoff
NOW=datetime(2026,11,3,10,0,tzinfo=timezone.utc)
KEY=b"-----BEGIN PUBLIC KEY-----\nNOT-A-REAL-TEST-KEY\n-----END PUBLIC KEY-----\n"
REVIEWER="external-g8-33-reviewer"
def evidence():
    design,candidate,preview,mapping=records()
    handoff=create_offline_mapping_review_handoff(
        design,candidate,preview,mapping,now=NOW-timedelta(minutes=3))
    assert handoff["ready_for_independent_review"]
    return design,candidate,preview,mapping,handoff
def policy():
    return {
        "policy_version":1,"reviewer_id":REVIEWER,
        "public_key_sha256":hashlib.sha256(KEY).hexdigest(),
        "expected_request_type":"AURORA_IBKR_OFFLINE_MAPPING_REVIEW_REQUEST_V1",
        "max_attestation_age_seconds":1800,"allowed_clock_skew_seconds":60,
    }
def signed():
    _,_,_,_,h=evidence()
    return {
        **h["unsigned_attestation_template"],"decision":"ATTESTED",
        "review_id":"99999999-9999-4999-8999-999999999999",
        "reviewer_id":REVIEWER,
        "captured_at_utc":(NOW-timedelta(minutes=1)).isoformat(),
        "expires_at_utc":(NOW+timedelta(minutes=10)).isoformat(),
        "reviewer_confirms_paper_only":True,
        "reviewer_confirms_no_broker_objects":True,
        "reviewer_confirms_no_network_or_submission":True,
        "reviewer_confirms_transmit_false":True,
        "reviewer_confirms_preview_attestation_bound":True,
        "reviewer_evidence_sha256":"a"*64,
        "signature_b64":base64.b64encode(b"x"*64).decode(),
    }
class SignedMappingReviewTests(unittest.TestCase):
    def evaluate(self,artifact=None,policy_obj=None,handoff=None,design=None,
                 candidate=None,preview=None,mapping=None,signature_valid=True,clean=True):
        d,c,p,m,h=evidence()
        return evaluate_signed_offline_mapping_review(
            signed() if artifact is None else artifact,
            policy() if policy_obj is None else policy_obj,KEY,signature_valid,
            h if handoff is None else handoff,
            d if design is None else design,
            c if candidate is None else candidate,
            p if preview is None else preview,
            m if mapping is None else mapping,clean,now=NOW)
    def assert_blocked(self, r):
        self.assertEqual(r["status"],"BLOCKED",r.get("checks"))
        self.assertIs(r["verified"],False)
        for flag in PERMISSION_FLAGS:self.assertIs(r[flag],False)
    def test_mock_positive_does_not_enable_execution(self):
        r=self.evaluate()
        self.assertEqual(r["status"],"VERIFIED",r["checks"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        for flag in PERMISSION_FLAGS:self.assertIs(r[flag],False)
    def test_unsigned_template_denied(self):
        *_,h=evidence()
        self.assert_blocked(self.evaluate(artifact=h["unsigned_attestation_template"]))
    def test_signature_failure_and_key_identity_denied(self):
        self.assert_blocked(self.evaluate(signature_valid=False))
        p=policy();p["public_key_sha256"]="0"*64
        self.assert_blocked(self.evaluate(policy_obj=p))
        a=signed();a["reviewer_id"]="untrusted-reviewer"
        self.assert_blocked(self.evaluate(artifact=a))
    def test_expired_and_future_and_old_request_denied(self):
        a=signed();a["expires_at_utc"]=(NOW-timedelta(seconds=1)).isoformat()
        self.assert_blocked(self.evaluate(artifact=a))
        a=signed();a["captured_at_utc"]=(NOW+timedelta(minutes=5)).isoformat()
        self.assert_blocked(self.evaluate(artifact=a))
        d,c,p,m,_=evidence()
        h=create_offline_mapping_review_handoff(d,c,p,m,now=NOW-timedelta(hours=2))
        self.assert_blocked(self.evaluate(handoff=h))
    def test_all_human_confirms_required(self):
        from engines.ibkr_offline_mapping_signed_review import CONFIRM_FIELDS
        for field in CONFIRM_FIELDS:
            with self.subTest(field=field):
                a=signed();a[field]=False
                self.assert_blocked(self.evaluate(artifact=a))
    def test_changed_request_mapping_and_preview_denied(self):
        *_,h=evidence()
        h["review_request"]["mapping_sha256"]="0"*64
        self.assert_blocked(self.evaluate(handoff=h))
        d,c,p,m,_=evidence()
        m["mapping"]["order_fields"]["transmit"]=True
        self.assert_blocked(self.evaluate(mapping=m))
        d,c,p,m,_=evidence()
        p["quantity"]=14
        self.assert_blocked(self.evaluate(preview=p))
    def test_prior_candidate_attestation_tamper_denied(self):
        d,c,p,m,_=evidence()
        c["real_money_trading_allowed"]=True
        self.assert_blocked(self.evaluate(candidate=c))
        d,c,p,m,_=evidence()
        p["candidate_attestation_sha256"]="0"*64
        self.assert_blocked(self.evaluate(preview=p))
    def test_extra_keys_dirty_repository_and_secrets_denied(self):
        a=signed();a["account_id"]="DU-PRIVATE"
        r=self.evaluate(artifact=a)
        self.assert_blocked(r)
        self.assertNotIn("DU-PRIVATE",json.dumps(r))
        self.assert_blocked(self.evaluate(clean=False))
    def test_canonical_payload_omits_signature_only(self):
        a=signed()
        payload=json.loads(canonical_signed_payload(a))
        self.assertEqual(payload["mapping_sha256"],a["mapping_sha256"])
        self.assertNotIn("signature_b64",payload)
if __name__=="__main__":unittest.main()
