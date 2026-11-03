"""Unit tests: no imported candidate or positive human attestation in G8.29."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import unittest
from engines.ibkr_order_object_candidate_review import (
    evaluate_order_object_candidate, PERMISSION_FLAGS,
)
from engines.ibkr_order_object_candidate_handoff import (
    evaluate_order_object_candidate_handoff,
    NEXT_GATE,REQUEST_TYPE,ATTESTATION_TYPE,canonical_digest,
)
from engines.ibkr_order_object_design_attestation import (
    ENGINE_VERSION as DESIGN_ENGINE,NEXT_GATE as DESIGN_NEXT_GATE,
)
NOW=datetime(2026,11,3,10,0,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]
def candidate_source():
    return (ROOT/"broker_engine/ibkr_order_object_materializer_candidate.py").read_text(encoding="utf-8")
def design_attestation():
    return {
        "engine":DESIGN_ENGINE,"status":"VERIFIED","verified":True,
        "order_object_design_independently_attested":True,
        "reason":"INDEPENDENT_IBKR_ORDER_OBJECT_DESIGN_ATTESTATION_VERIFIED",
        "checks":{"signature_valid":True,"design_bound":True},
        "review_id":"77777777-7777-4777-8777-777777777777",
        "reviewer_id":"independent-reviewer",
        "design_sha256":"1"*64,
        "review_request_sha256":"2"*64,
        "upstream_attestation_result_sha256":"3"*64,
        "attestation_sha256":"4"*64,
        **{name:False for name in PERMISSION_FLAGS},
        "next_gate":DESIGN_NEXT_GATE,
    }
def inputs():
    a=design_attestation()
    s=candidate_source()
    c=evaluate_order_object_candidate(a,s,now=NOW)
    assert c["candidate_validated"]
    return c,s,a
class HandoffTests(unittest.TestCase):
    def evaluate(self,c=None,s=None,a=None):
        base_c,base_s,base_a=inputs()
        return evaluate_order_object_candidate_handoff(
            base_c if c is None else c,
            base_s if s is None else s,
            base_a if a is None else a,now=NOW)
    def assert_closed(self,r):
        for flag in PERMISSION_FLAGS:self.assertIs(r[flag],False)
    def test_ready_only_for_independent_review(self):
        r=self.evaluate()
        self.assertTrue(r["ready_for_independent_review"])
        self.assertTrue(r["candidate_revalidated"])
        self.assertFalse(r["operator_attests_candidate_safe"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        self.assertEqual(r["review_request"]["request_type"],REQUEST_TYPE)
        self.assertEqual(r["review_request"]["requested_control"],ATTESTATION_TYPE)
        self.assertFalse(r["review_request"]["candidate_imported"])
        self.assertFalse(r["review_request"]["broker_object_created"])
        self.assertFalse(r["review_request"]["network_accessed"])
        self.assert_closed(r)
    def test_unsigned_review_template(self):
        r=self.evaluate()
        t=r["unsigned_attestation_template"]
        self.assertIsNone(t["signature_b64"])
        self.assertIsNone(t["reviewer_id"])
        self.assertEqual(t["decision"],"REVIEW_REQUIRED")
        self.assertEqual(t["review_request_sha256"],r["review_request_sha256"])
        self.assertEqual(t["candidate_source_sha256"],r["review_request"]["candidate_source_sha256"])
    def test_deterministic_digest_binding(self):
        r=self.evaluate()
        self.assertEqual(r["review_request_sha256"],canonical_digest(r["review_request"]))
        self.assertEqual(r["candidate_review_sha256"],r["review_request"]["candidate_review_sha256"])
        self.assertEqual(r["review_request"]["candidate_source_sha256"],
                         hashlib.sha256(candidate_source().encode()).hexdigest())
    def test_modified_source_rejected(self):
        _,s,_=inputs()
        for mutated in (s+"\nimport ibapi\n",
                        s.replace('"broker_order_object_allowed": False',
                                  '"broker_order_object_allowed": True'),
                        s.replace('raise RuntimeError("G8_28_ORDER_CREATION_DISABLED")',"return True")):
            with self.subTest(change=mutated[-65:]):
                r=self.evaluate(s=mutated)
                self.assertEqual(r["status"],"BLOCKED")
                self.assert_closed(r)
    def test_replaced_candidate_review_rejected(self):
        c,_,_=inputs()
        c["candidate_source_sha256"]="0"*64
        self.assertEqual(self.evaluate(c=c)["status"],"BLOCKED")
    def test_modified_design_attestation_rejected(self):
        _,_,a=inputs()
        a["verified"]=False
        self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
    def test_permission_regression_rejected(self):
        c,_,a=inputs()
        c["broker_order_object_allowed"]=True
        self.assertEqual(self.evaluate(c=c)["status"],"BLOCKED")
        a["real_money_trading_allowed"]=True
        self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
    def test_extra_fields_rejected_and_sanitized(self):
        c,_,a=inputs()
        c["account_id"]="DU123"
        r=self.evaluate(c=c)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertNotIn("DU123",json.dumps(r))
        a["credentials"]="secret"
        self.assertEqual(self.evaluate(a=a)["status"],"BLOCKED")
    def test_empty_or_invalid_clock_rejected(self):
        c,s,a=inputs()
        self.assertEqual(self.evaluate(s="")["status"],"BLOCKED")
        r=evaluate_order_object_candidate_handoff(c,s,a,now=datetime(2026,11,3))
        self.assertEqual(r["status"],"BLOCKED")
if __name__=="__main__":unittest.main()
