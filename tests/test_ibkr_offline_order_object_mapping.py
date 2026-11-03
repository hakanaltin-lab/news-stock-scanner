"""G8.31 rejects unsafe or stale/unreviewed data; no broker imports."""
import copy
import json
from pathlib import Path
import unittest
from engines.ibkr_offline_order_object_mapping import research_offline_ibkr_mapping,_digest
from engines.ibkr_order_object_candidate_attestation import ENGINE_VERSION,NEXT_GATE
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
ROOT=Path(__file__).resolve().parents[1]
def design():return json.loads((ROOT/"config/ibkr_order_object_materializer_design_v1.json").read_text())
def attestation():
    return {
        "engine":ENGINE_VERSION,"status":"VERIFIED","verified":True,
        "order_object_candidate_independently_attested":True,
        "reason":"INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_VERIFIED",
        "checks":{"signature":True,"bindings":True},
        "review_id":"88888888-8888-4888-8888-888888888888",
        "reviewer_id":"independent-reviewer","candidate_source_sha256":"1"*64,
        "review_request_sha256":"2"*64,"candidate_review_sha256":"3"*64,
        "design_sha256":_digest(design()),
        "design_attestation_sha256":"4"*64,"attestation_sha256":"5"*64,
        **{f:False for f in PERMISSION_FLAGS},"next_gate":NEXT_GATE,
    }
def request():
    return {
        "request_schema_version":1,"intent_id":"11111111-1111-4111-8111-111111111111",
        "symbol":"NVDA","side":"BUY","quantity":12,
        "position_quantity_at_validation":0,
        "limit_price":"101.25","order_type":"LMT","time_in_force":"DAY",
        "outside_rth":False,"reduce_only":False,"paper_only":True,
        "transmit":False,"broker_request_materialized":False,
        "broker_order_object_created":False,"candidate_attestation_sha256":"6"*64,
    }
class MappingTests(unittest.TestCase):
    def run_case(self,d=None,a=None,r=None):
        return research_offline_ibkr_mapping(design() if d is None else d,
                                             attestation() if a is None else a,
                                             request() if r is None else r)
    def assert_blocked(self,value):
        self.assertEqual(value["status"],"BLOCKED")
        self.assertIsNone(value["mapping"])
        for flag in PERMISSION_FLAGS:self.assertIs(value[flag],False)
    def test_valid_buy_mapping_is_plain_research(self):
        result=self.run_case()
        self.assertTrue(result["mapping_preview_validated"])
        self.assertFalse(result["broker_order_object_created"])
        self.assertFalse(result["transmit"])
        mapping=result["mapping"]
        self.assertEqual(mapping["contract_fields"],
                         {"symbol":"NVDA","secType":"STK","exchange":"SMART","currency":"USD"})
        self.assertEqual(mapping["order_fields"]["lmtPrice"],"101.25")
        self.assertIs(mapping["order_fields"]["transmit"],False)
        self.assertIs(mapping["broker_order_submitted"],False)
        for flag in PERMISSION_FLAGS:self.assertIs(result[flag],False)
    def test_sell_reduction_only(self):
        r=request();r.update(side="SELL",quantity=10,position_quantity_at_validation=10,reduce_only=True)
        self.assertTrue(self.run_case(r=r)["mapping_preview_validated"])
        r["position_quantity_at_validation"]=9
        self.assert_blocked(self.run_case(r=r))
        r["position_quantity_at_validation"]=10;r["reduce_only"]=False
        self.assert_blocked(self.run_case(r=r))
    def test_unverified_attestation(self):
        a=attestation();a["verified"]=False
        self.assert_blocked(self.run_case(a=a))
    def test_digest_mismatch(self):
        a=attestation();a["design_sha256"]="f"*64
        self.assert_blocked(self.run_case(a=a))
    def test_wrong_design_and_live_mode(self):
        d=design();d["port"]=4001
        self.assert_blocked(self.run_case(d=d))
        d=design();d["broker_mode"]="LIVE"
        self.assert_blocked(self.run_case(d=d))
    def test_request_unsafe(self):
        for field,value in (
            ("transmit",True),("paper_only",False),("broker_order_object_created",True),
            ("order_type","MKT"),("outside_rth",True),("quantity",2.5),
            ("side","SHORT"),("symbol","nvda"),("limit_price","0"),
            ("limit_price","NaN"),("limit_price","101.2500"),("limit_price","1000000000"),
        ):
            with self.subTest(field=field,value=value):
                r=request();r[field]=value
                self.assert_blocked(self.run_case(r=r))
    def test_unexpected_secrets_rejected(self):
        r=request();r["account_id"]="DU12345"
        blocked=self.run_case(r=r)
        self.assert_blocked(blocked)
        self.assertNotIn("DU12345",json.dumps(blocked))
    def test_broker_permission_escalation_rejected(self):
        a=attestation();a["paper_order_submission_allowed"]=True
        self.assert_blocked(self.run_case(a=a))
    def test_deterministic_mapping_hash(self):
        one=self.run_case();two=self.run_case()
        self.assertEqual(one["mapping_sha256"],two["mapping_sha256"])
if __name__=="__main__":unittest.main()
