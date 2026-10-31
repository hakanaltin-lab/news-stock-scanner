import unittest
from engines.ibkr_snapshot_correlation_bridge import diagnose_snapshot

class TestBridge(unittest.TestCase):
    def test_current_gateway_blocks_without_execution_completion(self):
        snapshot={"status":"CONNECTED","requests_complete":{"managed_accounts":True,"account_summary":True,"positions":True,"open_orders":True},"order_status":[],"executions":[]}
        result=diagnose_snapshot(snapshot,{}, {})
        self.assertEqual(result["reason"],"EXECUTION_COMPLETENESS_UNPROVEN")
        self.assertFalse(result["paper_order_submission_allowed"])
    def test_incomplete_snapshot_blocks(self):
        self.assertEqual(diagnose_snapshot({"status":"CONNECTED","requests_complete":{}}, {}, {})["status"],"BLOCKED")
    def test_missing_rows_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders"),True)}
        self.assertEqual(diagnose_snapshot(s,{}, {})["reason"],"MISSING_BROKER_ROWS")
    def test_invalid_snapshot_blocks(self):
        self.assertEqual(diagnose_snapshot(None,{}, {})["status"],"BLOCKED")
if __name__=="__main__":
    unittest.main()
