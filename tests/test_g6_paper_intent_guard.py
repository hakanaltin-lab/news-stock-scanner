import unittest
from engines.g6_paper_intent_guard import PaperIntentGuard

GOOD = {"client_order_id": "paper-001", "symbol": "SPY", "side": "BUY", "quantity": 1}

class PaperIntentGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = PaperIntentGuard()

    def check(self, intent=None, **kwargs):
        params = dict(broker_connected=True, account_type="PAPER", run_mode="PAPER_ENABLED")
        params.update(kwargs)
        return self.guard.check(GOOD if intent is None else intent, **params)

    def test_valid_intent_is_only_reserved_in_memory(self):
        self.assertTrue(self.check()["allowed"])
        self.assertFalse(self.check()["allowed"])

    def test_disconnected_broker_blocks(self):
        result = self.check(broker_connected=False)
        self.assertIn("BROKER_DISCONNECTED", result["reasons"])

    def test_live_account_blocks(self):
        result = self.check(account_type="LIVE")
        self.assertIn("ACCOUNT_NOT_VERIFIED_PAPER", result["reasons"])

    def test_unarmed_mode_blocks(self):
        result = self.check(run_mode="SAFE_OFF")
        self.assertIn("PAPER_MODE_NOT_ARMED", result["reasons"])

    def test_invalid_intents_block(self):
        for bad in ({}, {**GOOD, "quantity": float("nan")},
                    {**GOOD, "quantity": -1}, {**GOOD, "client_order_id": ""}):
            with self.subTest(bad=bad):
                self.assertFalse(self.check(bad)["allowed"])

    def test_failed_intent_does_not_reserve_id(self):
        self.assertFalse(self.check(broker_connected=False)["allowed"])
        self.assertTrue(self.check()["allowed"])

    def test_reset_is_forbidden(self):
        with self.assertRaises(RuntimeError):
            self.guard.reset()

if __name__ == "__main__":
    unittest.main()
