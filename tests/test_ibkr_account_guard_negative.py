"""Offline negative tests for IBKR paper-account identity allowlisting."""
import os
import unittest
from unittest.mock import patch

from engines.ibkr_account_guard import (
    account_fingerprint,
    evaluate_paper_account_identity,
)


class PaperAccountGuardNegativeTests(unittest.TestCase):
    def test_missing_allowlist_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            result = evaluate_paper_account_identity(["DU1234567"])
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["reason"], "PAPER_ACCOUNT_ALLOWLIST_NOT_CONFIGURED")

    def test_unknown_account_fails_closed(self):
        with patch.dict(os.environ, {"AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": "DU1234567"}, clear=True):
            result = evaluate_paper_account_identity(["DU7654321"])
        self.assertFalse(result["paper_account_verified"])
        self.assertEqual(result["verified_account_fingerprints"], [])
        self.assertNotIn("DU7654321", str(result))

    def test_mixed_accounts_fail_closed(self):
        with patch.dict(os.environ, {"AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": "DU1234567"}, clear=True):
            result = evaluate_paper_account_identity(["DU1234567", "DU7654321"])
        self.assertFalse(result["paper_account_verified"])

    def test_allowlisted_account_returns_only_fingerprint(self):
        with patch.dict(os.environ, {"AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST": "DU1234567"}, clear=True):
            result = evaluate_paper_account_identity(["DU1234567"])
        self.assertTrue(result["paper_account_verified"])
        self.assertEqual(result["verified_account_fingerprints"], [account_fingerprint("DU1234567")])
        self.assertNotIn("DU1234567", str(result))


if __name__ == "__main__":
    unittest.main()
