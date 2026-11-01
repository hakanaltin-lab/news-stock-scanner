"""Invalid IBKR client IDs must be rejected before a network connection."""
import os
import unittest
from unittest.mock import patch

from engines import ibkr_gateway_connector as connector


class ClientIdFailClosedTests(unittest.TestCase):
    def test_invalid_client_id_never_falls_back_to_default(self):
        for raw in ("invalid", "", "82.5", "NaN"):
            with self.subTest(raw=raw), patch.dict(os.environ, {
                "AURORA_IBKR_CLIENT_ID": raw,
                "AURORA_IBKR_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
            }):
                self.assertEqual(connector.load_ibkr_config()["client_id"], -1)

    def test_out_of_range_client_id_is_blocked_before_network(self):
        for raw in ("-1", "2147483648", "invalid"):
            with self.subTest(raw=raw), patch.dict(os.environ, {
                "AURORA_IBKR_CLIENT_ID": raw,
                "AURORA_IBKR_ENABLED": "true",
                "AURORA_IBKR_MODE": "PAPER",
                "AURORA_IBKR_HOST": "127.0.0.1",
                "AURORA_IBKR_PORT": "4002",
            }):
                with patch.object(connector, "_IBKRSnapshotApp", create=True) as app:
                    result = connector.get_ibkr_read_only_snapshot()
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason"], "INVALID_IBKR_CLIENT_ID")
                self.assertEqual(result["connection_status"], "NOT_ATTEMPTED")
                app.assert_not_called()


if __name__ == "__main__":
    unittest.main()
