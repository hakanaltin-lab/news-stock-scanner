"""Read-only regression checks for the published forward-promotion report.

These tests never connect to a broker, write report data, or authorize orders.
"""
import copy
import json
from pathlib import Path
import unittest

REPORT = Path(__file__).resolve().parents[1] / "docs" / "fresh_forward_promotion_gate.json"


def validate_fail_closed(report):
    """Reject inconsistent or prematurely promoted report snapshots."""
    if any(report.get(flag) is not False for flag in (
        "automatic_live_promotion", "live_execution_authorized",
        "paper_order_submission_authorized", "live_policy_changed",
    )):
        return False
    failed = False
    for horizon in ("20d", "60d"):
        evidence = report["fresh_evidence"][horizon]
        gate = report["fresh_gate_checks"][horizon]["independent_cohorts"]
        required = report["thresholds"][f"min_{horizon}_independent_cohorts"]
        count = evidence["independent_cohorts"]
        if required < 6 or count < 0 or count > evidence["raw_evaluated_records"]:
            return False
        if gate["actual"] != count or gate["required"] != required:
            return False
        if gate["passed"] is not (count >= required):
            return False
        if count < required:
            failed = True
        if evidence["raw_evaluated_records"] == 0 and (
            count != 0 or evidence["independent_hit_rate_pct"] is not None
        ):
            return False
        if any(check["passed"] is False for check in
               report["fresh_gate_checks"][horizon].values()):
            failed = True
    if any(check["passed"] is False for check in
           report["historical_guardrails"].values()):
        failed = True
    return not failed or report["verdict"] == "PROMOTION_BLOCKED"


class ForwardPromotionReportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_current_report_is_fail_closed(self):
        self.assertTrue(validate_fail_closed(self.report))

    def test_synthetic_premature_promotion_is_rejected(self):
        fake = copy.deepcopy(self.report)
        fake["verdict"] = "REVIEW_ELIGIBLE"
        self.assertFalse(validate_fail_closed(fake))

    def test_synthetic_injected_cohort_is_rejected(self):
        fake = copy.deepcopy(self.report)
        fake["fresh_evidence"]["20d"]["independent_cohorts"] = 6
        self.assertFalse(validate_fail_closed(fake))

    def test_synthetic_order_authorization_is_rejected(self):
        fake = copy.deepcopy(self.report)
        fake["paper_order_submission_authorized"] = True
        self.assertFalse(validate_fail_closed(fake))

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

    def test_failed_gate_cannot_claim_review_eligibility(self):
        report = self.report
        failed_checks = [
            (section, horizon, name)
            for section, groups in (
                ("fresh_gate_checks", report["fresh_gate_checks"]),
                ("historical_guardrails", {"historical": report["historical_guardrails"]}),
            )
            for horizon, checks in groups.items()
            for name, check in checks.items()
            if check["passed"] is False
        ]
        if failed_checks:
            self.assertEqual(report["verdict"], "PROMOTION_BLOCKED")

    def test_cohort_count_matches_reported_gate(self):
        for horizon in ("20d", "60d"):
            evidence = self.report["fresh_evidence"][horizon]
            gate = self.report["fresh_gate_checks"][horizon]["independent_cohorts"]
            required = self.report["thresholds"][f"min_{horizon}_independent_cohorts"]
            self.assertEqual(gate["actual"], evidence["independent_cohorts"])
            self.assertEqual(gate["required"], required)
            self.assertIs(gate["passed"], evidence["independent_cohorts"] >= required)

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
