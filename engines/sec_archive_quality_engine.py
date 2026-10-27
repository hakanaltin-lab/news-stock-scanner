"""Data-source readiness and coverage, without strategy or promotion decisions."""

from collections import Counter
from datetime import date, datetime, timezone
import math

from engines.sec_edgar_point_in_time_engine import (
    ALLOWED_FORMS,
    CANONICAL_METRICS,
    METRIC_CONCEPTS_BY_NAMESPACE,
    cik10,
)


QUALITY_VERSION = "V8.9.2 SEC Fact Quarantine"
SAFETY_STATE = {
    "live_decisions_changed": False,
    "research_use_authorized": False,
    "paper_order_submission_authorized": False,
    "live_execution_authorized": False,
}


def parse_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def fact_issues(fact):
    """The same strict row rules govern profiling and admission."""
    if not isinstance(fact, dict):
        return {"invalid_fact_row"}
    issues = set()
    filed = parse_date(fact.get("filed"))
    available = parse_date(fact.get("available_date"))
    end = parse_date(fact.get("end"))
    start = parse_date(fact.get("start"))
    if filed is None or available is None or end is None:
        issues.add("missing_or_invalid_date")
    else:
        if available.toordinal() < filed.toordinal() + 1:
            issues.add("availability_before_filing_plus_one_day")
        if end > filed:
            issues.add("period_end_after_filing")
    if fact.get("start") is not None:
        if start is None or (end is not None and start > end):
            issues.add("invalid_period_start")
    value = fact.get("value")
    try:
        finite_number = (not isinstance(value, bool)
                         and isinstance(value, (int, float)) and math.isfinite(value))
    except OverflowError:
        finite_number = False
    if not finite_number:
        issues.add("non_finite_or_non_numeric_value")
    metric = fact.get("metric")
    namespace = fact.get("namespace")
    if not isinstance(metric, str) or metric not in CANONICAL_METRICS:
        issues.add("unknown_metric")
    if not isinstance(namespace, str) or namespace not in METRIC_CONCEPTS_BY_NAMESPACE:
        issues.add("unknown_taxonomy")
    concepts = METRIC_CONCEPTS_BY_NAMESPACE.get(
        namespace if isinstance(namespace, str) else None, {}
    ).get(metric if isinstance(metric, str) else None, [])
    if fact.get("concept") not in concepts:
        issues.add("unmapped_metric_concept")
    if not isinstance(fact.get("form"), str) or fact["form"] not in ALLOWED_FORMS:
        issues.add("unsupported_filing_form")
    if any(not isinstance(fact.get(key), str) or not fact[key].strip()
           for key in ["unit", "accession"]):
        issues.add("missing_unit_or_accession")
    return issues


def inspect_sec_record(record):
    """Inspect actual rows; do not trust declared fact_count or PIT flags."""
    facts = record.get("facts") or []
    issues = Counter()
    metric_counts = Counter()
    taxonomy_counts = Counter()
    unit_counts = Counter()
    accessions = set()
    acceptance_accessions = set()
    available_dates = []
    period_ends = []
    accepted_fact_count = 0
    amended_fact_count = 0
    valid_fact_count = 0
    issue_examples = []

    if not isinstance(facts, list):
        facts = []
        issues["invalid_facts_container"] += 1

    for fact in facts:
        if not isinstance(fact, dict):
            issues["invalid_fact_row"] += 1
            continue

        row_issues = fact_issues(fact)
        available = parse_date(fact.get("available_date"))
        end = parse_date(fact.get("end"))

        issues.update(row_issues)
        if row_issues:
            if len(issue_examples) < 20:
                issue_examples.append({
                    "issues": sorted(row_issues),
                    **{
                        key: str(fact[key]) if fact.get(key) is not None else None
                        for key in ["metric", "namespace", "concept", "accession",
                                    "filed", "available_date", "start", "end"]
                    },
                })
            continue

        valid_fact_count += 1
        metric_counts[fact["metric"]] += 1
        taxonomy_counts[fact["namespace"]] += 1
        unit_counts[fact["unit"]] += 1
        accessions.add(fact["accession"])
        available_dates.append(available.isoformat())
        period_ends.append(end.isoformat())
        if str(fact.get("form", "")).endswith("/A"):
            amended_fact_count += 1
        if fact.get("accepted_at"):
            # Exact timestamps remain audit metadata, never an earlier cutoff.
            try:
                accepted = datetime.fromisoformat(
                    str(fact["accepted_at"]).replace("Z", "+00:00")
                )
                if accepted.tzinfo is not None:
                    accepted_fact_count += 1
                    acceptance_accessions.add(fact["accession"])
            except ValueError:
                pass

    cik = cik10(record.get("cik"))
    if cik is None or not cik.isdigit() or int(cik) <= 0 or len(cik) != 10:
        cik = None
        if record.get("status") == "COMPLETE":
            issues["invalid_cik"] += 1
    valid = (record.get("status") == "COMPLETE" and cik is not None
             and valid_fact_count > 0 and not issues)
    curation = record.get("quality_curation") or {}
    return {
        "ticker": record.get("ticker"),
        "cik": cik,
        "status": record.get("status", "UNKNOWN"),
        "quality_valid": valid,
        "quality_issues": dict(sorted(issues.items())),
        "quality_issue_examples": issue_examples,
        "source_quality_issues": curation.get("source_quality_issues", dict(sorted(issues.items()))),
        "source_fact_count": curation.get("source_fact_count", len(facts)),
        "quarantined_fact_count": curation.get("quarantined_fact_count", 0),
        "quarantine_file": curation.get("quarantine_file"),
        "fact_count": len(facts),
        "valid_fact_count": valid_fact_count,
        "invalid_fact_count": len(facts) - valid_fact_count,
        "accession_count": len(accessions),
        "acceptance_accession_count": len(acceptance_accessions),
        "acceptance_fact_count": accepted_fact_count,
        "exact_acceptance_fact_count": accepted_fact_count,
        "amended_fact_count": amended_fact_count,
        "amendment_fact_count": amended_fact_count,
        "metric_counts": dict(sorted(metric_counts.items())),
        "metric_coverage": {
            "present_metrics": sorted(metric_counts),
            "missing_metrics": sorted(set(CANONICAL_METRICS) - set(metric_counts)),
            "metric_fact_counts": dict(sorted(metric_counts.items())),
        },
        "missing_metrics": sorted(set(CANONICAL_METRICS) - set(metric_counts)),
        "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
        "taxonomy_fact_counts": dict(sorted(taxonomy_counts.items())),
        "submissions_metadata": {
            key: (record.get("submissions_metadata") or {}).get(key)
            for key in [
                "status", "historical_cutoff_date", "recent_acceptance_count",
                "historical_acceptance_count", "total_acceptance_count",
                "historical_files_discovered", "historical_files_loaded",
                "historical_files_failed",
            ]
        },
        "unit_counts": dict(sorted(unit_counts.items())),
        "latest_available_date": max(available_dates, default=None),
        "earliest_period_end": min(period_ends, default=None),
        "latest_period_end": max(period_ends, default=None),
        "source_taxonomy_concept_counts": record.get("source_taxonomy_concept_counts", {}),
        "no_matched_facts_reason": record.get("no_matched_facts_reason"),
    }


def quarantine_json_safe(value):
    """Encode non-JSON numbers as explicit audit markers, never as data values."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite_number_repr": repr(value)}
    if isinstance(value, dict):
        return {key: quarantine_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [quarantine_json_safe(item) for item in value]
    return value


def curate_sec_record(record):
    """Isolate invalid facts without re-dating, imputing or relaxing any rule."""
    source_quality = inspect_sec_record(record)
    facts = record.get("facts")
    if not isinstance(facts, list) or not facts:
        return record, None
    accepted = []
    rejected = []
    for fact in facts:
        issues = fact_issues(fact)
        if issues:
            rejected.append({"issues": sorted(issues), "fact": quarantine_json_safe(fact)})
        else:
            accepted.append(fact)
    if not rejected:
        return record, None

    quarantine = {
        "engine": QUALITY_VERSION,
        "ticker": record.get("ticker"), "cik": record.get("cik"),
        "status": "QUARANTINED_FACTS",
        "source": record.get("source"),
        "source_fact_count": len(facts),
        "quarantined_fact_count": len(rejected),
        "quality_issues": source_quality["quality_issues"],
        "facts": rejected,
        "dates_and_values_corrected": False,
        **SAFETY_STATE,
    }
    # Row isolation cannot repair missing issuer identity or an unsuccessful fetch.
    if (not accepted or record.get("status") != "COMPLETE"
            or source_quality["cik"] is None):
        return record, quarantine

    curated = {**record, "facts": accepted}
    quality = inspect_sec_record(curated)
    if not quality["quality_valid"]:
        return record, quarantine
    matched = {}
    for fact in accepted:
        matched.setdefault(fact["metric"], set()).add(
            fact["namespace"] + ":" + fact["concept"]
        )
    curated.update({
        "fact_count": len(accepted),
        "accession_count": quality["accession_count"],
        "latest_available_date": quality["latest_available_date"],
        "matched_concepts": {key: sorted(value) for key, value in sorted(matched.items())},
        "metric_coverage": {
            **quality["metric_coverage"],
            "canonical_metric_count": len(CANONICAL_METRICS),
            "present_metric_count": len(quality["metric_counts"]),
        },
        "taxonomy_fact_counts": quality["taxonomy_counts"],
        "exact_acceptance_fact_count": quality["acceptance_fact_count"],
        "exact_acceptance_coverage_pct": round(100 * quality["acceptance_fact_count"] / len(accepted), 2),
        "amendment_fact_count": quality["amended_fact_count"],
        "quality_curation": {
            "engine": QUALITY_VERSION, "source_fact_count": len(facts),
            "quarantined_fact_count": len(rejected),
            "source_quality_issues": source_quality["quality_issues"],
            "admission_rules_changed": False,
        },
    })
    return curated, quarantine


def build_archive_summary(tickers, universe_source, records, *, status=None,
                          ticker_map=None, changed_fact_files=0, error_type=None):
    """Describe this attempt separately from any retained older fact files."""
    rows = sorted(records, key=lambda row: row["ticker"])
    expected = len(tickers)
    valid_rows = [row for row in rows if row["quality_valid"]]
    valid_count = len(valid_rows)
    attempted = len(rows)
    assessed = ticker_map is not None
    matched = sum(ticker in ticker_map for ticker in tickers) if assessed else None
    missing = [ticker for ticker in tickers if ticker not in ticker_map] if assessed else []

    if status is None:
        if not expected:
            status = "BLOCKED_EMPTY_UNIVERSE"
        elif not valid_count:
            status = "NO_USABLE_FACTS"
        elif valid_count < expected or any(row["missing_metrics"] for row in valid_rows):
            status = "COMPLETE_WITH_GAPS"
        else:
            status = "COMPLETE"

    metric_coverage = {
        metric: {
            "ticker_count": sum(metric in row["metric_counts"] for row in valid_rows),
            "universe_count": expected,
        }
        for metric in CANONICAL_METRICS
    }
    taxonomy_counts = Counter()
    quality_issues = Counter()
    source_quality_issues = Counter()
    for row in rows:
        quality_issues.update(row["quality_issues"])
        source_quality_issues.update(row.get("source_quality_issues", {}))
    for row in valid_rows:
        taxonomy_counts.update(row["taxonomy_counts"])

    summary = {
        "engine": QUALITY_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "collection_ready": status in {"COMPLETE", "COMPLETE_WITH_GAPS"},
        "universe_source": universe_source,
        "ticker_count": expected,
        "attempted_ticker_count": attempted,
        "usable_ticker_count": valid_count,
        "unusable_tickers": sorted(row["ticker"] for row in rows if not row["quality_valid"]),
        "unattempted_tickers": sorted(set(tickers) - {row["ticker"] for row in rows}),
        "changed_fact_files": changed_fact_files,
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "cik_coverage": {
            "assessed": assessed,
            "matched_ticker_count": matched,
            "universe_count": expected,
            "missing_tickers": missing,
        },
        "metric_coverage": metric_coverage,
        "taxonomy_fact_counts": dict(sorted(taxonomy_counts.items())),
        "valid_fact_count": sum(row["valid_fact_count"] for row in valid_rows),
        "acceptance_fact_count": sum(row["acceptance_fact_count"] for row in valid_rows),
        "amended_fact_count": sum(row["amended_fact_count"] for row in valid_rows),
        "quality_issues": dict(sorted(quality_issues.items())),
        "source_quality_issues": dict(sorted(source_quality_issues.items())),
        "quarantined_fact_count": sum(row.get("quarantined_fact_count", 0) for row in rows),
        "tickers_with_quarantined_facts": sorted(row["ticker"] for row in rows if row.get("quarantined_fact_count")),
        "records": rows,
        "availability_rule": "SEC filed date + 1 calendar day; acceptance timestamps are audit-only",
        "point_in_time_validation_passed": bool(valid_rows) and not quality_issues,
        "limitations": [
            "Current index constituents are a forward universe, not historical membership.",
            "Coverage is measured for this run; retained older facts are not counted as fresh success.",
            "Missing concepts may reflect issuer reporting or taxonomy differences.",
            "No fundamental research hypothesis or live promotion is authorized by this report.",
        ],
        **SAFETY_STATE,
    }
    if status == "DISABLED_MISSING_SEC_USER_AGENT":
        summary["required_environment_variable"] = "SEC_USER_AGENT"
    if error_type:
        summary["error_type"] = error_type
    return summary
