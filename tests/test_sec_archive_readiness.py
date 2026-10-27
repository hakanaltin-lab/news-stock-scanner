"""Offline SEC collection failures and coverage must not look like fresh data."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engines.sec_archive_quality_engine import curate_sec_record, inspect_sec_record
from engines.sec_edgar_point_in_time_engine import (
    CANONICAL_METRICS, US_GAAP_METRIC_CONCEPTS, build_snapshot_as_of, fetch_ticker_facts,
)
from scripts import run_sec_edgar_pit_archive as archive


def example_record(ticker="AAA", *, all_metrics=False):
    metrics = CANONICAL_METRICS if all_metrics else ["revenue"]
    return {
        "ticker": ticker, "cik": "0000000001", "status": "COMPLETE",
        "facts": [{
            "metric": metric, "namespace": "us-gaap",
            "concept": US_GAAP_METRIC_CONCEPTS[metric][0],
            "unit": "USD", "value": 100,
            "start": "2020-01-01", "end": "2020-03-31",
            "filed": "2020-05-01", "available_date": "2020-05-02",
            "accession": "0000000001-20-000001", "form": "10-Q",
            "accepted_at": "2020-05-01T16:00:00Z",
        } for metric in metrics],
    }


class ArchiveRunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        original_directory = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, original_directory)
        self.contact = "AURORA Offline Test private-contact@example.invalid"
        environment = patch.dict(os.environ, {
            "SEC_USER_AGENT": self.contact,
            "GITHUB_ACTIONS": "false",
            "GITHUB_OUTPUT": str(Path.cwd() / "outputs.txt"),
            "GITHUB_STEP_SUMMARY": str(Path.cwd() / "summary.md"),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.universe = patch.object(archive, "load_current_evidence_universe",
                                     return_value=(["AAA"], "TEST_FORWARD_UNIVERSE"))
        self.universe.start()
        self.addCleanup(self.universe.stop)
        client_patch = patch.object(archive, "SECClient", autospec=True)
        self.client = client_patch.start()
        self.addCleanup(client_patch.stop)
        mapping_patch = patch.object(archive, "load_sec_ticker_map", return_value={
            "AAA": {"cik": "0000000001"}
        })
        self.mapping = mapping_patch.start()
        self.addCleanup(mapping_patch.stop)
        fetch_patch = patch.object(archive, "fetch_ticker_facts", return_value=example_record())
        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)

    def run_archive(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = archive.main()
        summary = json.loads(Path(archive.SUMMARY_FILE).read_text())
        dashboard = json.loads(Path("docs/sec_archive_readiness.json").read_text())
        self.assertEqual(summary["status"], dashboard["status"])
        self.assertNotIn("records", dashboard)
        self.assertIn("status=" + summary["status"], Path("outputs.txt").read_text())
        # The private User-Agent must never appear in public files or stdout.
        for content in [output.getvalue(), Path("summary.md").read_text(),
                        Path(archive.SUMMARY_FILE).read_text(),
                        Path("docs/sec_archive_readiness.json").read_text()]:
            self.assertNotIn(self.contact, content)
        for key in ["research_use_authorized", "paper_order_submission_authorized",
                    "live_execution_authorized", "live_decisions_changed"]:
            self.assertIs(summary[key], False)
        return code, summary

    def save_previous(self):
        path = Path(archive.OUTPUT_DIR) / "AAA.json"
        archive.write_if_changed(str(path), example_record())
        return path, path.read_bytes()

    def test_missing_user_agent_reports_blocker_without_network(self):
        os.environ["SEC_USER_AGENT"] = ""
        code, summary = self.run_archive()
        self.assertEqual(code, 2)
        self.assertEqual(summary["status"], "DISABLED_MISSING_SEC_USER_AGENT")
        self.assertFalse(summary["collection_ready"])
        self.assertEqual(summary["attempted_ticker_count"], 0)
        self.assertFalse(summary["cik_coverage"]["assessed"])
        self.assertIsNone(summary["cik_coverage"]["matched_ticker_count"])
        self.client.assert_not_called()
        self.fetch.assert_not_called()

    def test_empty_universe_is_not_success(self):
        archive.load_current_evidence_universe.return_value = ([], "EMPTY")
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "BLOCKED_EMPTY_UNIVERSE")
        self.client.assert_not_called()

    def test_bootstrap_error_is_reported_without_contact_leak(self):
        path, previous = self.save_previous()
        self.mapping.side_effect = RuntimeError("Rejected " + self.contact)
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "ERROR_SEC_TICKER_MAP")
        self.assertEqual(summary["error_type"], "RuntimeError")
        self.assertEqual(path.read_bytes(), previous)

    def test_empty_ticker_map_is_a_blocker(self):
        self.mapping.return_value = {}
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "BLOCKED_EMPTY_SEC_TICKER_MAP")
        self.fetch.assert_not_called()

    def test_failed_fetch_preserves_previous_facts_without_counting_them(self):
        path, previous = self.save_previous()
        self.fetch.side_effect = RuntimeError("Contact=" + self.contact)
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "NO_USABLE_FACTS")
        self.assertEqual(summary["usable_ticker_count"], 0)
        self.assertEqual(summary["valid_fact_count"], 0)
        self.assertTrue(summary["records"][0]["retained_previous_evidence"])
        self.assertEqual(path.read_bytes(), previous)

    def test_empty_fetch_preserves_previous_facts(self):
        path, previous = self.save_previous()
        self.fetch.return_value = {"ticker": "AAA", "cik": "1",
                                   "status": "NO_MATCHED_FACTS", "facts": []}
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["status_counts"], {"NO_MATCHED_FACTS": 1})
        self.assertEqual(path.read_bytes(), previous)

    def test_lookahead_candidate_does_not_replace_good_archive(self):
        path, previous = self.save_previous()
        candidate = example_record()
        candidate["facts"][0]["available_date"] = "2020-05-01"
        self.fetch.return_value = candidate
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["quality_issues"], {
            "availability_before_filing_plus_one_day": 1
        })
        self.assertEqual(summary["quality_summary"]["fact_ticker_count"], 0)
        self.assertEqual(summary["quality_summary"]["total_fact_count"], 0)
        self.assertEqual(path.read_bytes(), previous)

    def test_partial_cik_coverage_remains_a_visible_gap(self):
        archive.load_current_evidence_universe.return_value = (["AAA", "BBB"], "TEST")
        self.fetch.side_effect = [example_record(), {
            "ticker": "BBB", "status": "CIK_NOT_FOUND", "facts": []
        }]
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["status"], "COMPLETE_WITH_GAPS")
        self.assertEqual(summary["usable_ticker_count"], 1)
        self.assertEqual(summary["cik_coverage"]["matched_ticker_count"], 1)
        self.assertEqual(summary["cik_coverage"]["missing_tickers"], ["BBB"])
        self.assertEqual(summary["metric_coverage"]["revenue"], {
            "ticker_count": 1, "universe_count": 2
        })
        self.assertEqual(summary["metric_coverage"]["capex"]["ticker_count"], 0)

    def test_all_metrics_present_reports_complete_but_never_authorizes_research(self):
        self.fetch.return_value = example_record(all_metrics=True)
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["status"], "COMPLETE")
        self.assertTrue(summary["collection_ready"])
        self.assertEqual(summary["valid_fact_count"], 12)
        self.assertEqual(summary["acceptance_fact_count"], 12)
        self.assertEqual(summary["changed_fact_files"], 1)

    def test_missing_metrics_reported_without_requiring_them_for_all_issuers(self):
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["status"], "COMPLETE_WITH_GAPS")
        self.assertIn("capex", summary["records"][0]["missing_metrics"])
        self.assertTrue(summary["collection_ready"])

    def test_historical_submission_telemetry_survives_readiness_inspection(self):
        record = example_record()
        record["submissions_metadata"] = {
            "status": "PARTIAL", "historical_files_loaded": 3,
            "historical_files_failed": 1, "historical_acceptance_count": 25,
        }
        self.fetch.return_value = record
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["quality_summary"]["historical_submission_files_loaded"], 3)
        self.assertEqual(summary["quality_summary"]["historical_submission_files_failed"], 1)
        self.assertEqual(summary["quality_summary"]["submissions_status_counts"], {"PARTIAL": 1})

    def test_mixed_record_recovers_good_facts_and_preserves_rejected_source(self):
        candidate = example_record()
        bad = deepcopy(candidate["facts"][0])
        bad.update(end="2021-03-31", value=999)
        candidate["facts"].append(bad)
        before = deepcopy(candidate)
        self.fetch.return_value = candidate
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["usable_ticker_count"], 1)
        self.assertEqual(summary["valid_fact_count"], 1)
        self.assertEqual(summary["quarantined_fact_count"], 1)
        self.assertEqual(summary["quality_issues"], {})
        self.assertEqual(summary["source_quality_issues"], {"period_end_after_filing": 1})
        self.assertTrue(summary["point_in_time_validation_passed"])
        curated = json.loads((Path(archive.OUTPUT_DIR) / "AAA.json").read_text())
        rejected = json.loads((Path(archive.QUARANTINE_DIR) / "AAA.json").read_text())
        self.assertEqual(curated["fact_count"], 1)
        self.assertEqual(curated["quality_curation"]["source_fact_count"], 2)
        self.assertEqual(rejected["facts"][0]["fact"], bad)
        self.assertEqual(build_snapshot_as_of(curated, "2020-05-01")["metric_count"], 0)
        self.assertEqual(build_snapshot_as_of(curated, "2020-05-02")["metrics"]["revenue"]["value"], 100)
        self.assertEqual(candidate, before)

    def test_non_finite_source_value_is_audit_only_and_json_safe(self):
        candidate = example_record()
        bad = deepcopy(candidate["facts"][0])
        bad["value"] = float("nan")
        candidate["facts"].append(bad)
        self.fetch.return_value = candidate
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["quarantined_fact_count"], 1)
        rejected = json.loads((Path(archive.QUARANTINE_DIR) / "AAA.json").read_text())
        self.assertEqual(rejected["facts"][0]["fact"]["value"], {"non_finite_number_repr": "nan"})
        curated = json.loads((Path(archive.OUTPUT_DIR) / "AAA.json").read_text())
        self.assertEqual(curated["facts"][0]["value"], 100)

    def test_quarantine_does_not_remove_legitimate_amendment_versions(self):
        candidate = example_record()
        amendment = deepcopy(candidate["facts"][0])
        amendment.update(value=110, filed="2020-05-20", available_date="2020-05-21",
                         accepted_at="2020-05-20T16:00:00Z", form="10-Q/A",
                         accession="0000000001-20-000002")
        unsafe = deepcopy(amendment)
        unsafe.update(value=999, available_date="2020-05-20")
        candidate["facts"].extend([amendment, unsafe])
        self.fetch.return_value = candidate
        code, summary = self.run_archive()
        self.assertEqual(code, 0)
        self.assertEqual(summary["valid_fact_count"], 2)
        self.assertEqual(summary["quarantined_fact_count"], 1)
        curated = json.loads((Path(archive.OUTPUT_DIR) / "AAA.json").read_text())
        self.assertEqual(build_snapshot_as_of(curated, "2020-05-20")["metrics"]["revenue"]["value"], 100)
        self.assertEqual(build_snapshot_as_of(curated, "2020-05-21")["metrics"]["revenue"]["value"], 110)

    def test_row_isolation_cannot_repair_a_missing_issuer_identity(self):
        path, previous = self.save_previous()
        candidate = example_record()
        candidate["cik"] = "0"
        bad = deepcopy(candidate["facts"][0])
        bad["end"] = "2021-03-31"
        candidate["facts"].append(bad)
        self.fetch.return_value = candidate
        code, summary = self.run_archive()
        self.assertEqual(code, 1)
        self.assertEqual(summary["usable_ticker_count"], 0)
        self.assertEqual(path.read_bytes(), previous)


class RecordQualityTests(unittest.TestCase):
    def test_does_not_trust_declared_fact_counts(self):
        record = example_record()
        record["fact_count"] = 99999
        self.assertEqual(inspect_sec_record(record)["fact_count"], 1)

    def test_invalid_dates_and_values_are_quarantined(self):
        for field, value in [("value", float("nan")), ("value", float("inf")),
                             ("value", True), ("value", "100"),
                             ("available_date", ""), ("filed", "not-a-date"),
                             ("end", "2020-06-30"), ("start", "2021-01-01")]:
            with self.subTest(field=field, value=value):
                record = example_record()
                record["facts"][0][field] = value
                quality = inspect_sec_record(record)
                self.assertFalse(quality["quality_valid"])
                self.assertEqual(quality["invalid_fact_count"], 1)

    def test_ifrs_currency_and_amendment_are_preserved_in_coverage(self):
        record = example_record()
        fact = record["facts"][0]
        fact.update(namespace="ifrs-full", concept="Revenue", unit="EUR", form="20-F/A")
        quality = inspect_sec_record(record)
        self.assertTrue(quality["quality_valid"])
        self.assertEqual(quality["taxonomy_counts"], {"ifrs-full": 1})
        self.assertEqual(quality["unit_counts"], {"EUR": 1})
        self.assertEqual(quality["amended_fact_count"], 1)

    def test_missing_acceptance_does_not_advance_availability(self):
        record = example_record()
        record["facts"][0]["accepted_at"] = None
        before = deepcopy(record)
        quality = inspect_sec_record(record)
        self.assertTrue(quality["quality_valid"])
        self.assertEqual(quality["acceptance_fact_count"], 0)
        self.assertEqual(record, before)

    def test_malformed_facts_container_is_not_usable(self):
        record = example_record()
        record["facts"] = {"unexpected": "format"}
        self.assertFalse(inspect_sec_record(record)["quality_valid"])

    def test_missing_or_mismatched_provenance_is_not_usable(self):
        for field, value in [("concept", "Assets"), ("namespace", "custom-taxonomy"),
                             ("unit", ""), ("accession", ""), ("form", "8-K")]:
            with self.subTest(field=field):
                record = example_record()
                record["facts"][0][field] = value
                self.assertFalse(inspect_sec_record(record)["quality_valid"])

    def test_invalid_issuer_identifier_is_not_usable(self):
        record = example_record()
        record["cik"] = "0"
        quality = inspect_sec_record(record)
        self.assertFalse(quality["quality_valid"])
        self.assertEqual(quality["quality_issues"], {"invalid_cik": 1})

    def test_date_issue_retains_bounded_filing_provenance_for_review(self):
        record = example_record()
        record["facts"][0]["end"] = "2021-03-31"
        record["facts"] *= 25
        quality = inspect_sec_record(record)
        self.assertFalse(quality["quality_valid"])
        self.assertEqual(quality["quality_issues"], {"period_end_after_filing": 25})
        self.assertEqual(len(quality["quality_issue_examples"]), 20)
        self.assertEqual(quality["quality_issue_examples"][0]["end"], "2021-03-31")
        self.assertEqual(quality["quality_issue_examples"][0]["accession"],
                         "0000000001-20-000001")

    def test_curation_is_idempotent_without_imputing_source_values(self):
        record = example_record()
        bad = deepcopy(record["facts"][0])
        bad.update(value=777, end="2021-03-31")
        record["facts"].append(bad)
        curated, quarantine = curate_sec_record(record)
        again, repeated = curate_sec_record(curated)
        self.assertEqual(again, curated)
        self.assertIsNone(repeated)
        self.assertEqual(len(curated["facts"]) + len(quarantine["facts"]), 2)
        self.assertEqual(quarantine["facts"][0]["fact"]["value"], 777)

    def test_unsupported_financial_taxonomy_is_explicitly_unavailable(self):
        class Client:
            def __init__(self):
                self.replies = iter([
                    {"filings": {"recent": {}, "files": []}},
                    {"entityName": "New issuer", "facts": {"ffd": {"Other": {"units": {}}}}},
                ])
            def get_json(self, url):
                return next(self.replies)
        record = fetch_ticker_facts(Client(), "NEW", {"NEW": {"cik": "0000000001"}})
        self.assertEqual(record["status"], "NO_MATCHED_FACTS")
        self.assertEqual(record["no_matched_facts_reason"], "NO_SUPPORTED_FINANCIAL_TAXONOMY")
        self.assertEqual(record["source_taxonomy_concept_counts"], {"ffd": 1})
        self.assertFalse(inspect_sec_record(record)["quality_valid"])


if __name__ == "__main__":
    unittest.main()
