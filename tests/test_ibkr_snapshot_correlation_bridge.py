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
    def test_execution_complete_but_unsafe_endpoint_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[],"executions":[],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"LIVE","endpoint_safe":False,"read_only":True}}
        self.assertEqual(diagnose_snapshot(s,{}, {})["reason"],"UNSAFE_BROKER_ENDPOINT")
    def test_execution_complete_but_order_guard_missing_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[],"executions":[],"order_submission_hard_blocked":False,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True}}
        self.assertEqual(diagnose_snapshot(s,{}, {})["reason"],"ORDER_SAFETY_GUARD_UNPROVEN")

    def test_mapping_without_broker_evidence_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[],"executions":[],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"BROKER_CORRELATION_NOT_OBSERVED")
    def test_matching_broker_perm_id_is_read_only(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","filled":0,"remaining":1,"status":"Submitted"}],"executions":[],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        result=diagnose_snapshot(s,local,mapping)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason"],"BROKER_ACCOUNT_EVIDENCE_UNAVAILABLE")
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_wrong_broker_account_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[{"perm_id":123,"order_id":1,"client_id":82,"account":"OTHER"}],"executions":[],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"BROKER_IDENTITY_MISMATCH")

    def test_duplicate_execution_id_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[],"executions":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","execution_id":"X","shares":2},{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","execution_id":"X","shares":3}],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"INVALID_OR_DUPLICATE_EXECUTION_ID")
    def test_zero_execution_quantity_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[],"executions":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","execution_id":"X","shares":0}],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"INVALID_EXECUTION_QUANTITY")

    def test_executions_exceed_reported_fill_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","filled":1}],"executions":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","execution_id":"X","shares":2}],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"EXECUTIONS_EXCEED_REPORTED_FILL")

    def test_filled_status_with_remaining_quantity_blocks(self):
        s={"status":"CONNECTED","requests_complete":dict.fromkeys(("managed_accounts","account_summary","positions","open_orders","executions"),True),"order_status":[{"perm_id":123,"order_id":1,"client_id":82,"account":"PAPER-REDACTED","filled":2,"remaining":1,"status":"Filled"}],"executions":[],"order_submission_hard_blocked":True,"live_trading_allowed":False,"config":{"mode":"PAPER","endpoint_safe":True,"read_only":True},"paper_account_guard":{"paper_account_verified":True,"verified_account_fingerprints":["PAPER-REDACTED"]}}
        local={"k":{"account":"PAPER-REDACTED","idempotency_key":"k"}}
        mapping={"k":{"account":"PAPER-REDACTED","perm_id":123,"order_id":1,"client_id":82}}
        self.assertEqual(diagnose_snapshot(s,local,mapping)["reason"],"CONFLICTING_FILLED_STATUS")

if __name__=="__main__":
    unittest.main()
