"""Read-only regression checks for the published forward-promotion report.

These tests never connect to a broker, write report data, or authorize orders.
"""
import json
from pathlib import Path
import unittest

REPORT = Path(__file__).resolve().parents[1] / "docs" / "fresh_forward_promotion_gate.json"


class ForwardPromotionReportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_no_automatic_execution_authorization(self):
        report = self.report
        for flag in ("automatic_live_promotion", "live_execution_authorized",
                     "paper_order_submission_authorized", "live_policy_changed"):
            with self.subTest(flag=flag):
                self.assertIs(report.get(flag), False)

    def test_insufficient_cohorts_never_promote(self):
        report = self.report
        thresholds = report["thresholds"]
        for horizon in ("20d", "60d"):
            evidence = report["fresh_evidence"][horizon]
            required = thresholds[f"min_{horizon}_independent_cohorts"]
            actual = evidence["independent_cohorts"]
            self.assertGreaterEqual(required, 6)
            if actual < required:
                self.assertEqual(report["verdict"], "PROMOTION_BLOCKED")
                self.assertIs(report["fresh_gate_checks"][horizon]["independent_cohorts"]["passed"], False)

    def test_pending_records_do_not_count_as_evaluated(self):
        for horizon in ("20d", "60d"):
            evidence = self.report["fresh_evidence"][horizon]
            self.assertGreaterEqual(evidence["raw_pending_records"], 0)
            self.assertGreaterEqual(evidence["raw_evaluated_records"], 0)
            self.assertLessEqual(
                evidence["independent_cohorts"], evidence["raw_evaluated_records"]
            )
            if evidence["raw_evaluated_records"] == 0:
                self.assertEqual(evidence["independent_cohorts"], 0)
                self.assertIsNone(evidence["independent_hit_rate_pct"])


if __name__ == "__main__":
    unittest.main()
