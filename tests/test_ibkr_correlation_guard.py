import unittest
from engines.ibkr_correlation_guard import verify_correlations

def fixture():
    local={"key1":{"account":"PAPER-REDACTED","idempotency_key":"key1"}}
    snapshot={"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
    mapping={"key1":{"account":"PAPER-REDACTED","perm_id":1234,"order_id":1,"client_id":82}}
    return local,snapshot,mapping

class TestCorrelationGuard(unittest.TestCase):
    def test_verified_but_never_tradable(self):
        result=verify_correlations(*fixture())
        self.assertEqual(result["status"],"CORRELATIONS_VERIFIED")
        self.assertFalse(result["paper_order_submission_allowed"])
        self.assertFalse(result["live_trading_allowed"])
    def test_missing_mapping(self):
        a,b,c=fixture();c.clear()
        self.assertEqual(verify_correlations(a,b,c)["status"],"BLOCKED")
    def test_unverified_account(self):
        a,b,c=fixture();b["paper_account_guard"]["paper_account_verified"]=False
        self.assertEqual(verify_correlations(a,b,c)["status"],"BLOCKED")
    def test_invalid_permanent_id(self):
        a,b,c=fixture();c["key1"]["perm_id"]=0
        self.assertEqual(verify_correlations(a,b,c)["status"],"BLOCKED")
    def test_idempotency_mismatch(self):
        a,b,c=fixture();a["key1"]["idempotency_key"]="other"
        self.assertEqual(verify_correlations(a,b,c)["status"],"BLOCKED")
    def test_duplicate_permanent_id(self):
        a,b,c=fixture();a["key2"]={"account":"PAPER-REDACTED","idempotency_key":"key2"}
        c["key2"]={**c["key1"]}
        self.assertEqual(verify_correlations(a,b,c)["reason"],"DUPLICATE_PERM_ID")
    def test_duplicate_client_order_id(self):
        a,b,c=fixture();a["key2"]={"account":"PAPER-REDACTED","idempotency_key":"key2"}
        c["key2"]={**c["key1"],"perm_id":5678}
        self.assertEqual(verify_correlations(a,b,c)["reason"],"DUPLICATE_CLIENT_ORDER_ID")
    def test_live_account_mismatch(self):
        a,b,c=fixture();c["key1"]["account"]="LIVE"
        self.assertEqual(verify_correlations(a,b,c)["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
