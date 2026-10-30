"""AURORA Google Cloud budget verification must fail closed."""

from decimal import Decimal
import unittest

from scripts.gcp_budget_guard import (
    _sanitize_error,
    evaluate_budget_guard,
)


PROJECT_ID = "project-ce9773ef-6814-469c-92b"
PROJECT_NUMBER = "123456789"


def budget(
    amount="750",
    currency="TRY",
    projects=None,
    thresholds=(0.5, 0.9, 1.0),
):
    return {
        "displayName": "AURORA TRY 750",
        "budgetFilter": {
            "projects": projects or [],
            "calendarPeriod": "MONTH",
        },
        "amount": {
            "specifiedAmount": {
                "currencyCode": currency,
                "units": amount,
            },
        },
        "thresholdRules": [
            {"thresholdPercent": value}
            for value in thresholds
        ],
    }


def evaluate(items):
    return evaluate_budget_guard(
        items,
        project_id=PROJECT_ID,
        project_number=PROJECT_NUMBER,
        expected_currency="TRY",
        expected_amount=Decimal("750"),
    )


class GCPBudgetGuardTests(unittest.TestCase):
    def test_account_wide_exact_budget_passes(self):
        result = evaluate([budget()])
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["paid_resource_creation_allowed"])
        self.assertFalse(result["budget_alert_is_spend_cap"])

    def test_project_number_scope_passes(self):
        result = evaluate([
            budget(projects=[f"projects/{PROJECT_NUMBER}"])
        ])
        self.assertEqual(result["status"], "PASS")

    def test_unrelated_project_scope_blocks(self):
        result = evaluate([
            budget(projects=["projects/999999999"])
        ])
        self.assertEqual(result["status"], "BLOCK")

    def test_wrong_currency_or_amount_blocks(self):
        self.assertEqual(evaluate([budget(currency="USD")])["status"], "BLOCK")
        self.assertEqual(evaluate([budget(amount="751")])["status"], "BLOCK")

    def test_missing_full_budget_threshold_blocks(self):
        result = evaluate([budget(thresholds=(0.5, 0.9))])
        self.assertEqual(result["status"], "BLOCK")

    def test_last_period_budget_or_malformed_payload_blocks(self):
        last_period = {
            "displayName": "Previous period",
            "amount": {"lastPeriodAmount": {}},
            "thresholdRules": [{"thresholdPercent": 1.0}],
        }
        self.assertEqual(evaluate([last_period])["status"], "BLOCK")
        self.assertEqual(evaluate(None)["status"], "BLOCK")

    def test_billing_account_identifier_is_masked_in_errors(self):
        sanitized = _sanitize_error(
            "permission denied for billingAccounts/ABC123-DEF456-GHI789"
        )
        self.assertNotIn("ABC123-DEF456-GHI789", sanitized)
        self.assertIn("billingAccounts/[MASKED]", sanitized)


if __name__ == "__main__":
    unittest.main()
