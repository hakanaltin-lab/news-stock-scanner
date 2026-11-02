"""Fail-closed regression tests for IBKR Paper account identity guard.

Run: python -m unittest discover -s tests -p 'test_ibkr_account_guard_g6.py'
No broker connectivity, credentials, or live orders required.
"""
import os
import unittest
from unittest.mock import patch

from engines.ibkr_account_guard import (
    ENV_NAME,
    account_fingerprint,
    evaluate_paper_account_identity,
)


class PaperAccountGuardG6Tests(unittest.TestCase):
    def evaluate(self, accounts, allowlist=None):
        env = {} if allowlist is None else {ENV_NAME: allowlist}
        with patch.dict(os.environ, env, clear=True):
            return evaluate_paper_account_identity(accounts)

    def test_missing_allowlist_blocks(self):
        result = self.evaluate(["DU123456"])
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_ALLOWLIST_NOT_CONFIGURED")

    def test_no_managed_accounts_blocks(self):
        result = self.evaluate([], "DU123456")
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "NO_MANAGED_ACCOUNT_RECEIVED")

    def test_unlisted_account_blocks(self):
        result = self.evaluate(["DU999999"], "DU123456")
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_NOT_ALLOWLISTED")
        self.assertEqual(result["verified_account_fingerprints"], [])

    def test_mixed_account_set_blocks(self):
        result = self.evaluate(["DU123456", "U999999"], "DU123456")
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["verified_account_fingerprints"], [])

    def test_allowlisted_account_passes_without_raw_identifier(self):
        account = "DU123456"
        result = self.evaluate([account], account)
        self.assertTrue(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_VERIFIED")
        self.assertEqual(result["verified_account_fingerprints"], [account_fingerprint(account)])
        self.assertNotIn(account, repr(result))

    def test_whitespace_normalization(self):
        result = self.evaluate([" DU123456 "], " DU123456 , ")
        self.assertTrue(result["paper_account_verified"])


if __name__ == "__main__":
    unittest.main()
