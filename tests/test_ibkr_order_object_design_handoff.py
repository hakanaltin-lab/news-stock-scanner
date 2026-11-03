"""Offline tests for G8.26 review-only handoff."""
from datetime import datetime,timedelta,timezone
import copy,json,inspect
from pathlib import Path
import unittest
from engines.ibkr_order_object_design_handoff import evaluate_order_object_design_handoff,NEXT_GATE
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
from engines.offline_order_request_materializer_attestation import ENGINE_VERSION as ATTEST_ENGINE,NEXT_GATE as ATTEST_GATE
from scripts import g6_order_object_design_handoff as cli
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,3,9,0,tzinfo=timezone.utc)
def design():
    return json.loads((ROOT/"config/ibkr_order_object_materializer_design_v1.json").read_text())
def upstream():
    return {
        "engine":ATTEST_ENGINE,"status":"VERIFIED","verified":True,
        "offline_materializer_independently_attested":True,
        "reason":"INDEPENDENT_OFFLINE_MATERIALIZER_ATTESTATION_VERIFIED",
        "checks":{"signature_verified":True},"materializer_review_id":"55555555-5555-4555-8555-555555555555",
        "reviewer_id":"independent-reviewer",
        "captured_at_utc":(NOW-timedelta(minutes=2)).isoformat(),
        "expires_at_utc":(NOW+timedelta(minutes=15)).isoformat(),
        "review_request_sha256":"1"*64,"design_sha256":"2"*64,
        "materializer_source_sha256":"3"*64,"cli_source_sha256":"4"*64,
        "materializer_attestation_sha256":"5"*64,"reviewer_evidence_sha256":"6"*64,
        **{k:False for k in PERMISSION_FLAGS},"next_gate":ATTEST_GATE,
    }
class HandoffTests(unittest.TestCase):
    def evaluate(self,d=None,u=None):
        return evaluate_order_object_design_handoff(d if d is not None else design(),u if u is not None else upstream(),now=NOW)
    def assert_closed(self,result):
        for name in PERMISSION_FLAGS:self.assertIs(result[name],False)
    def test_valid_unsigned_review_handoff(self):
        r=self.evaluate()
        self.assertTrue(r["ready_for_independent_review"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        self.assertFalse(r["operator_attests_safe"])
        self.assertEqual(len(r["review_request_sha256"]),64)
        t=r["unsigned_attestation_template"]
        self.assertEqual(t["decision"],"REVIEW_REQUIRED")
        self.assertIsNone(t["signature_b64"])
        self.assertIsNone(t["reviewer_confirms_transmit_false"])
        self.assert_closed(r)
    def test_unsigned_does_not_authorize(self):
        r=self.evaluate()
        self.assertFalse(r["review_request"]["operator_attests_safe"])
        self.assertFalse(r["review_request"]["broker_order_object_allowed"])
        self.assert_closed(r)
    def test_broker_permission_regression_blocked(self):
        a=upstream();a["broker_order_object_allowed"]=True
        r=self.evaluate(u=a)
        self.assertEqual(r["status"],"BLOCKED")
        self.assert_closed(r)
    def test_design_transmit_or_live_blocked(self):
        for field,value in [("broker_mode","LIVE"),("port",4001),("ibkr_import_allowed",True)]:
            with self.subTest(field=field):
                d=design();d[field]=value
                self.assertEqual(self.evaluate(d=d)["status"],"BLOCKED")
        d=design();d["planned_order_mapping"]["transmit"]=True
        self.assertEqual(self.evaluate(d=d)["status"],"BLOCKED")
    def test_expired_upstream_blocked(self):
        a=upstream();a["expires_at_utc"]=(NOW-timedelta(seconds=1)).isoformat()
        self.assertEqual(self.evaluate(u=a)["status"],"BLOCKED")
    def test_extra_fields_and_raw_account_blocked(self):
        d=design();d["raw_account_id"]="DU123456"
        result=self.evaluate(d=d)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertNotIn("DU123456",json.dumps(result))
    def test_deterministic_digest_binding(self):
        a=self.evaluate();b=self.evaluate()
        self.assertEqual(a["review_request_sha256"],b["review_request_sha256"])
        self.assertEqual(a["design_sha256"],b["design_sha256"])
    def test_no_broker_or_signing_code_in_cli(self):
        text=inspect.getsource(cli).lower()
        for token in ("import ibapi","from ibapi","private_key","pkeyutl -sign","placeorder","submit_order("):
            self.assertNotIn(token,text)
if __name__=="__main__":unittest.main()
