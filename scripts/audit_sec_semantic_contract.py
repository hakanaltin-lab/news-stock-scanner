"""Audit the published SEC archive against the unit, period and PIT contract."""

import argparse
from collections import Counter, defaultdict
import glob
import json
import os

from engines.sec_archive_quality_engine import SAFETY_STATE, fact_issues
from engines.sec_edgar_point_in_time_engine import (
    build_snapshot_as_of,
    fact_period_type,
)


FACT_GLOB = "data/sec_edgar_pit/facts/*.json"
SUMMARY_FILE = "data/sec_edgar_pit/latest_summary.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def fact_identity_without_concept(fact):
    return (
        fact.get("metric"),
        fact.get("unit"),
        fact.get("start"),
        fact.get("end"),
        fact.get("filed"),
        fact.get("form"),
        fact.get("accession"),
    )


def profile_primary_archive(as_of_date):
    result = {
        "ticker_count": 0,
        "fact_count": 0,
        "invalid_fact_count": 0,
        "invalid_tickers": set(),
        "issue_counts": Counter(),
        "metric_issue_counts": Counter(),
        "metric_unit_counts": defaultdict(Counter),
        "period_type_counts": Counter(),
        "multi_concept_group_count": 0,
        "multi_concept_conflicting_value_group_count": 0,
        "multi_concept_tickers": set(),
        "snapshot_selection": defaultdict(Counter),
    }

    for path in sorted(glob.glob(FACT_GLOB)):
        record = load_json(path)
        ticker = record.get("ticker") or os.path.basename(path)[:-5]
        facts = record.get("facts") or []
        result["ticker_count"] += 1
        concept_groups = defaultdict(list)

        for fact in facts:
            result["fact_count"] += 1
            issues = fact_issues(fact)
            if issues:
                result["invalid_fact_count"] += 1
                result["invalid_tickers"].add(ticker)
                result["issue_counts"].update(issues)
                for issue in issues:
                    result["metric_issue_counts"][(fact.get("metric"), issue)] += 1
                continue
            result["metric_unit_counts"][fact["metric"]][fact["unit"]] += 1
            result["period_type_counts"][fact_period_type(fact)] += 1
            concept_groups[fact_identity_without_concept(fact)].append(fact)

        for group in concept_groups.values():
            concepts = {(fact.get("namespace"), fact.get("concept")) for fact in group}
            if len(concepts) <= 1:
                continue
            result["multi_concept_group_count"] += 1
            result["multi_concept_tickers"].add(ticker)
            if len({json.dumps(fact.get("value"), sort_keys=True) for fact in group}) > 1:
                result["multi_concept_conflicting_value_group_count"] += 1

        for period in ("quarter", "annual"):
            snapshot = build_snapshot_as_of(
                record,
                as_of_date,
                duration_period=period,
            )
            period_counts = result["snapshot_selection"][period]
            period_counts["ticker_count"] += 1
            period_counts["selected_metric_count"] += snapshot["metric_count"]
            period_counts["duration_context_aligned_ticker_count"] += int(
                snapshot["duration_context_aligned"]
            )
            period_counts["selected_metrics_comparable_ticker_count"] += int(
                snapshot["comparability_passed"]
            )
            period_counts["ambiguous_metric_count"] += sum(
                issue == "ambiguous_reporting_currency"
                for issue in snapshot["selection_issues"].values()
            )

    return result


def profile_referenced_quarantine(summary):
    issue_counts = Counter()
    metric_issue_counts = Counter()
    metric_unit_counts = Counter()
    fact_count = 0
    tickers = []
    missing_files = []
    for row in summary.get("records", []):
        expected = row.get("quarantined_fact_count", 0) or 0
        path = row.get("quarantine_file")
        if not expected:
            continue
        tickers.append(row.get("ticker"))
        if not isinstance(path, str) or not os.path.isfile(path):
            missing_files.append(path or row.get("ticker"))
            continue
        ledger = load_json(path)
        facts = ledger.get("facts") or []
        fact_count += len(facts)
        for entry in facts:
            fact = entry.get("fact") or {}
            reasons = entry.get("issues") or []
            issue_counts.update(reasons)
            for issue in reasons:
                metric_issue_counts[(fact.get("metric"), issue)] += 1
            metric_unit_counts[(fact.get("metric"), fact.get("unit"))] += 1
    return {
        "ticker_count": len(tickers),
        "tickers": sorted(ticker for ticker in tickers if ticker),
        "fact_count": fact_count,
        "issue_counts": dict(sorted(issue_counts.items())),
        "metric_issue_counts": {
            str(metric) + ":" + issue: count
            for (metric, issue), count in sorted(
                metric_issue_counts.items(),
                key=lambda item: (str(item[0][0]), item[0][1]),
            )
        },
        "metric_unit_counts": {
            str(metric) + ":" + str(unit): count
            for (metric, unit), count in sorted(
                metric_unit_counts.items(),
                key=lambda item: (str(item[0][0]), str(item[0][1])),
            )
        },
        "missing_files": sorted(str(path) for path in missing_files),
    }


def serializable_primary(profile):
    return {
        "ticker_count": profile["ticker_count"],
        "fact_count": profile["fact_count"],
        "invalid_fact_count": profile["invalid_fact_count"],
        "invalid_ticker_count": len(profile["invalid_tickers"]),
        "invalid_tickers": sorted(profile["invalid_tickers"]),
        "issue_counts": dict(sorted(profile["issue_counts"].items())),
        "metric_issue_counts": {
            str(metric) + ":" + issue: count
            for (metric, issue), count in sorted(
                profile["metric_issue_counts"].items(),
                key=lambda item: (str(item[0][0]), item[0][1]),
            )
        },
        "metric_unit_counts": {
            metric: dict(sorted(counts.items()))
            for metric, counts in sorted(profile["metric_unit_counts"].items())
        },
        "period_type_counts": dict(sorted(profile["period_type_counts"].items())),
        "multi_concept_group_count": profile["multi_concept_group_count"],
        "multi_concept_conflicting_value_group_count": (
            profile["multi_concept_conflicting_value_group_count"]
        ),
        "multi_concept_ticker_count": len(profile["multi_concept_tickers"]),
        "snapshot_selection": {
            period: dict(sorted(counts.items()))
            for period, counts in sorted(profile["snapshot_selection"].items())
        },
    }


def audit(as_of_date):
    primary_internal = profile_primary_archive(as_of_date)
    primary = serializable_primary(primary_internal)
    summary = load_json(SUMMARY_FILE)
    quarantine = profile_referenced_quarantine(summary)
    failures = []

    if primary["invalid_fact_count"]:
        failures.append("PRIMARY_ARCHIVE_CONTAINS_SEMANTIC_CONTRACT_FAILURES")
    if primary["ticker_count"] != summary.get("usable_ticker_count"):
        failures.append("PRIMARY_TICKER_COUNT_MISMATCH")
    if primary["fact_count"] != summary.get("valid_fact_count"):
        failures.append("PRIMARY_FACT_COUNT_MISMATCH")
    if quarantine["fact_count"] != summary.get("quarantined_fact_count"):
        failures.append("QUARANTINE_FACT_COUNT_MISMATCH")
    if quarantine["tickers"] != sorted(summary.get("tickers_with_quarantined_facts", [])):
        failures.append("QUARANTINE_TICKER_SET_MISMATCH")
    if quarantine["issue_counts"] != summary.get("source_quality_issues", {}):
        failures.append("QUARANTINE_ISSUE_COUNT_MISMATCH")
    if quarantine["missing_files"]:
        failures.append("REFERENCED_QUARANTINE_FILE_MISSING")
    if summary.get("point_in_time_validation_passed") is not True:
        failures.append("POINT_IN_TIME_VALIDATION_NOT_PASSED")
    for field, expected in SAFETY_STATE.items():
        if summary.get(field) is not expected:
            failures.append("UNSAFE_SUMMARY_FLAG:" + field)

    return {
        "status": "PASS" if not failures else "FAIL",
        "as_of_date": as_of_date,
        "primary_archive": primary,
        "referenced_quarantine": quarantine,
        "summary_reconciliation": {
            "summary_engine": summary.get("engine"),
            "summary_status": summary.get("status"),
            "summary_usable_ticker_count": summary.get("usable_ticker_count"),
            "summary_valid_fact_count": summary.get("valid_fact_count"),
            "summary_quarantined_fact_count": summary.get("quarantined_fact_count"),
            "summary_source_quality_issues": summary.get("source_quality_issues"),
            "point_in_time_validation_passed": summary.get(
                "point_in_time_validation_passed"
            ),
        },
        "failures": failures,
        **SAFETY_STATE,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", default="9999-12-31")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    result = audit(args.as_of_date)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 1 if args.require_clean and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
