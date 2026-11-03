"""G8.32 offline mapping handoff tests; fixtures are not independent approvals."""
import json
from pathlib import Path
from datetime import datetime, timezone
import unittest
from engines.ibkr_offline_order_object_mapping import _digest,research_offline_ibkr_mapping
from engines.ibkr_offline_mapping_review_handoff import create_offline_mapping_review_handoff,NEXT_GATE
from engines.ibkr_order_object_candidate_attestation import ENGINE_VERSION,NEXT_GATE as UPSTREAM_NEXT_GATE
from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,3,10,0,tzinfo=timezone.utc)
def design(): return json.loads((ROOT/"config/ibkr_order_object_materializer_design_v1.json").read_text())
def upstream():
    return {
        "engine":ENGINE_VERSION,"status":"VERIFIED","verified":True,
        "order_object_candidate_independently_attested":True,
        "reason":"INDEPENDENT_ORDER_OBJECT_CANDIDATE_ATTESTATION_VERIFIED",
        "checks":{"signature":True,"bindings":True},
        "review_id":"88888888-8888-4888-8888-888888888888","reviewer_id":"reviewer",
        "candidate_source_sha256":"1"*64,"review_request_sha256":"2"*64,
        "candidate_review_sha256":"3"*64,"design_sha256":_digest(design()),
        "design_attestation_sha256":"4"*64,"attestation_sha256":"5"*64,
        **{f:False for f in PERMISSION_FLAGS},"next_gate":UPSTREAM_NEXT_GATE,
    }
def preview():
    return {
        "request_schema_version":1,
        "intent_id":"11111111-1111-4111-8111-111111111111",
        "symbol":"NVDA","side":"BUY","quantity":12,
        "position_quantity_at_validation":0,
        "limit_price":"101.25","order_type":"LMT",
        "time_in_force":"DAY","outside_rth":False,
        "reduce_only":False,"paper_only":True,
        "transmit":False,"broker_request_materialized":False,
        "broker_order_object_created":False,
        "candidate_attestation_sha256":"5"*64,
    }
def records():
    d=design();u=upstream();p=preview()
    m=research_offline_ibkr_mapping(d,u,p)
    assert m["mapping_preview_validated"]
    return d,u,p,m
class MappingHandoffTests(unittest.TestCase):
    def evaluate(self,d=None,u=None,p=None,m=None):
        D,U,P,M=records()
        return create_offline_mapping_review_handoff(
            D if d is None else d,U if u is None else u,
            P if p is None else p,M if m is None else m,now=NOW)
    def blocked(self,result):
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIsNone(result["review_request"])
        for key in PERMISSION_FLAGS:self.assertIs(result[key],False)
    def test_unsigned_review_request_only(self):
        r=self.evaluate()
        self.assertTrue(r["ready_for_independent_review"])
        self.assertEqual(r["next_gate"],NEXT_GATE)
        self.assertFalse(r["operator_approves_execution"])
        self.assertEqual(r["review_request_sha256"],_digest(r["review_request"]))
        self.assertIsNone(r["unsigned_attestation_template"]["signature_b64"])
        self.assertEqual(r["unsigned_attestation_template"]["decision"],"REVIEW_REQUIRED")
        self.assertIs(r["review_request"]["transmit"],False)
        self.assertIs(r["review_request"]["broker_order_created"],False)
    def test_preview_attestation_must_match_signature_result(self):
        p=preview();p["candidate_attestation_sha256"]="6"*64
        # G8.31 alone permits syntactic digest. Handoff must reject.
        d,u,_,_=records()
        m=research_offline_ibkr_mapping(d,u,p)
        self.assertTrue(m["mapping_preview_validated"])
        self.blocked(self.evaluate(p=p,m=m))
    def test_modified_mapping_blocked(self):
        _,_,_,m=records()
        m["mapping"]["order_fields"]["transmit"]=True
        self.blocked(self.evaluate(m=m))
    def test_unbound_mapping_digest_blocked(self):
        _,_,_,m=records()
        m["mapping_sha256"]="f"*64
        self.blocked(self.evaluate(m=m))
    def test_unverified_upstream_blocked(self):
        u=upstream();u["verified"]=False
        self.blocked(self.evaluate(u=u))
    def test_request_secret_field_blocked(self):
        p=preview();p["account_id"]="DUSECRET"
        r=self.evaluate(p=p)
        self.blocked(r)
        self.assertNotIn("DUSECRET",json.dumps(r))
    def test_live_design_blocked(self):
        d=design();d["broker_mode"]="LIVE"
        self.blocked(self.evaluate(d=d))
    def test_permissions_escalation_blocked(self):
        _,_,_,m=records()
        m["real_money_trading_allowed"]=True
        self.blocked(self.evaluate(m=m))
    def test_sell_reduce_only(self):
        d,u,p,_=records()
        p.update(side="SELL",quantity=5,position_quantity_at_validation=5,reduce_only=True)
        m=research_offline_ibkr_mapping(d,u,p)
        r=self.evaluate(p=p,m=m)
        self.assertTrue(r["ready_for_independent_review"])
    def test_non_timezone_clock_blocked(self):
        d,u,p,m=records()
        r=create_offline_mapping_review_handoff(d,u,p,m,now=datetime(2026,11,3))
        self.blocked(r)
if __name__=="__main__":unittest.main()
