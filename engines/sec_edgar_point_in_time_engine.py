"""
AURORA SEC EDGAR / XBRL Point-in-Time Evidence Foundation

Purpose:
- Fetch public SEC ticker/CIK mappings and Company Facts data.
- Normalize a bounded set of fundamental concepts into filing-dated evidence.
- Preserve all reported versions/amendments; never overwrite history in-memory.
- Use a conservative availability date of filed_date + 1 calendar day to avoid
  same-day look-ahead when exact historical acceptance timestamps are absent.
- Research/data foundation only. No live portfolio action changes.

SEC fair-access requirements:
- A declared SEC_USER_AGENT is mandatory.
- Requests are throttled below the SEC 10 requests/second ceiling.
"""

from collections import Counter
from datetime import date, timedelta
import json
import os
import time

import requests


ENGINE_VERSION = "V8.8.3 SEC EDGAR Point-in-Time Fundamental Foundation"
SIGNATURE = "V8.8.3"

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
)

SEC_SUBMISSIONS_URL = (
    "https://data.sec.gov/submissions/CIK{cik10}.json"
)

SEC_SUBMISSIONS_FILE_URL = (
    "https://data.sec.gov/submissions/{name}"
)

# XBRL reporting became mandatory in phases beginning in 2009. Historical
# submission shards ending before this date cannot enrich Company Facts data
# and are intentionally skipped to keep SEC traffic bounded.
HISTORICAL_SUBMISSIONS_CUTOFF_DATE = "2009-01-01"

DEFAULT_TIMEOUT_SECONDS = 30
MIN_REQUEST_INTERVAL_SECONDS = 0.22

ALLOWED_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A"
}

US_GAAP_METRIC_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet"
    ],

    "operating_income": [
        "OperatingIncomeLoss"
    ],

    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss"
    ],

    "eps_diluted": [
        "EarningsPerShareDiluted"
    ],

    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities"
    ],

    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment"
    ],

    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ],

    "total_assets": [
        "Assets"
    ],

    "total_liabilities": [
        "Liabilities"
    ],

    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
    ],

    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent"
    ],

    "current_debt": [
        "ShortTermBorrowings",
        "LongTermDebtCurrent"
    ]
}


IFRS_METRIC_CONCEPTS = {
    "revenue": [
        "Revenue",
        "RevenueFromContractsWithCustomers"
    ],

    "operating_income": [
        "ProfitLossFromOperatingActivities"
    ],

    "net_income": [
        "ProfitLoss"
    ],

    "eps_diluted": [
        "DilutedEarningsLossPerShare"
    ],

    "operating_cash_flow": [
        "CashFlowsFromUsedInOperatingActivities"
    ],

    "capex": [
        "PurchaseOfPropertyPlantAndEquipment"
    ],

    "cash": [
        "CashAndCashEquivalents"
    ],

    "total_assets": [
        "Assets"
    ],

    "total_liabilities": [
        "Liabilities"
    ],

    "stockholders_equity": [
        "Equity"
    ],

    "long_term_debt": [
        "NoncurrentBorrowings"
    ],

    "current_debt": [
        "CurrentBorrowings"
    ]
}


METRIC_CONCEPTS_BY_NAMESPACE = {
    "us-gaap":
    US_GAAP_METRIC_CONCEPTS,

    "ifrs-full":
    IFRS_METRIC_CONCEPTS
}


CANONICAL_METRICS = sorted(
    set(
        metric
        for concepts in METRIC_CONCEPTS_BY_NAMESPACE.values()
        for metric in concepts
    )
)


UNIT_PREFERENCES = {
    "eps_diluted": [
        "USD/shares",
        "USD / shares"
    ]
}


class SECClient:
    def __init__(
        self,
        user_agent=None,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS
    ):
        self.user_agent = (
            user_agent
            or
            os.getenv(
                "SEC_USER_AGENT",
                ""
            )
        ).strip()

        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required for SEC fair-access compliance."
            )

        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent":
            self.user_agent,

            "Accept-Encoding":
            "gzip, deflate",

            "Accept":
            "application/json"
        })

        self._last_request_monotonic = 0.0


    def get_json(
        self,
        url
    ):
        elapsed = (
            time.monotonic()
            -
            self._last_request_monotonic
        )

        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(
                MIN_REQUEST_INTERVAL_SECONDS
                -
                elapsed
            )

        response = self.session.get(
            url,
            timeout=self.timeout_seconds
        )

        self._last_request_monotonic = (
            time.monotonic()
        )

        response.raise_for_status()

        return response.json()


def normalize_ticker(
    value
):
    return (
        str(
            value
            or
            ""
        )
        .strip()
        .upper()
        .replace(
            ".",
            "-"
        )
    )


def cik10(
    value
):
    try:
        return str(
            int(
                value
            )
        ).zfill(
            10
        )

    except Exception:
        return None


def load_sec_ticker_map(
    client
):
    raw = client.get_json(
        SEC_TICKER_MAP_URL
    )

    mapping = {}

    if not isinstance(
        raw,
        dict
    ):
        return mapping

    for item in raw.values():
        if not isinstance(
            item,
            dict
        ):
            continue

        ticker = normalize_ticker(
            item.get(
                "ticker"
            )
        )

        cik_value = cik10(
            item.get(
                "cik_str"
            )
        )

        if (
            not ticker
            or
            not cik_value
        ):
            continue

        mapping[
            ticker
        ] = {
            "cik":
            cik_value,

            "title":
            item.get(
                "title"
            )
        }

    return mapping


def conservative_available_date(
    filed
):
    try:
        filed_date = date.fromisoformat(
            str(
                filed
            )[:10]
        )

        return (
            filed_date
            +
            timedelta(
                days=1
            )
        ).isoformat()

    except Exception:
        return None


def unit_priority(
    metric,
    units
):
    if not isinstance(
        units,
        dict
    ):
        return []

    preferred = UNIT_PREFERENCES.get(
        metric,
        []
    )

    ordered = []

    for unit in preferred:
        if unit in units:
            ordered.append(
                unit
            )

    for unit in units:
        if unit not in ordered:
            ordered.append(
                unit
            )

    return ordered


def normalize_accession(
    value
):
    return str(
        value
        or
        ""
    ).strip()


def build_acceptance_map(
    submissions_payload
):
    payload = submissions_payload or {}

    # The primary CIK payload nests its compact columnar arrays under
    # filings.recent. Historical shard files expose the same arrays at their
    # root. Supporting both shapes is necessary for exact acceptance metadata
    # across the full XBRL history.
    recent = (
        (
            payload.get(
                "filings",
                {}
            )
            or
            {}
        ).get(
            "recent",
            {}
        )
        or
        payload.get(
            "recent",
            {}
        )
        or
        payload
    )

    if not isinstance(
        recent,
        dict
    ):
        return {}

    accessions = recent.get(
        "accessionNumber",
        []
    ) or []

    acceptance_values = recent.get(
        "acceptanceDateTime",
        []
    ) or []

    filed_values = recent.get(
        "filingDate",
        []
    ) or []

    form_values = recent.get(
        "form",
        []
    ) or []

    result = {}

    for index, accession in enumerate(
        accessions
    ):
        key = normalize_accession(
            accession
        )

        if not key:
            continue

        result[
            key
        ] = {
            "accepted_at":
            (
                acceptance_values[
                    index
                ]
                if index
                <
                len(
                    acceptance_values
                )
                else None
            ),

            "filing_date":
            (
                filed_values[
                    index
                ]
                if index
                <
                len(
                    filed_values
                )
                else None
            ),

            "form":
            (
                form_values[
                    index
                ]
                if index
                <
                len(
                    form_values
                )
                else None
            )
        }

    return result


def historical_submission_files(
    submissions_payload,
    cutoff_date=HISTORICAL_SUBMISSIONS_CUTOFF_DATE
):
    files = (
        (
            (
                submissions_payload
                or
                {}
            ).get(
                "filings",
                {}
            )
            or
            {}
        ).get(
            "files",
            []
        )
        or
        []
    )

    eligible = []

    for item in files:
        if not isinstance(
            item,
            dict
        ):
            continue

        name = str(
            item.get(
                "name",
                ""
            )
        ).strip()

        filing_to = str(
            item.get(
                "filingTo",
                ""
            )
        )[:10]

        # SEC-provided names are expected to be simple JSON filenames. Reject
        # path-like values defensively before using them in a request URL.
        if (
            not name
            or
            not name.endswith(
                ".json"
            )
            or
            "/"
            in
            name
            or
            "\\"
            in
            name
        ):
            continue

        if (
            filing_to
            and
            filing_to
            <
            cutoff_date
        ):
            continue

        eligible.append({
            "name":
            name,

            "filing_from":
            item.get(
                "filingFrom"
            ),

            "filing_to":
            item.get(
                "filingTo"
            )
        })

    eligible.sort(
        key=lambda item: (
            str(
                item.get(
                    "filing_from",
                    ""
                )
            ),
            item.get(
                "name",
                ""
            )
        )
    )

    return eligible


def load_acceptance_metadata(
    client,
    cik_value,
    cutoff_date=HISTORICAL_SUBMISSIONS_CUTOFF_DATE
):
    submissions_payload = client.get_json(
        SEC_SUBMISSIONS_URL.format(
            cik10=cik10(
                cik_value
            )
        )
    )

    acceptance_map = build_acceptance_map(
        submissions_payload
    )

    recent_acceptance_count = len(
        acceptance_map
    )

    historical_files = historical_submission_files(
        submissions_payload,
        cutoff_date=cutoff_date
    )

    loaded_files = []
    failed_files = []
    historical_acceptance_count = 0

    for descriptor in historical_files:
        name = descriptor.get(
            "name"
        )

        try:
            historical_payload = client.get_json(
                SEC_SUBMISSIONS_FILE_URL.format(
                    name=name
                )
            )

            historical_map = build_acceptance_map(
                historical_payload
            )

            added = 0

            for accession, metadata in (
                historical_map.items()
            ):
                if accession in acceptance_map:
                    continue

                acceptance_map[
                    accession
                ] = metadata
                added += 1

            historical_acceptance_count += added

            loaded_files.append({
                **descriptor,
                "acceptance_count":
                len(
                    historical_map
                ),
                "added_acceptance_count":
                added
            })

        except Exception as error:
            failed_files.append({
                **descriptor,
                "error":
                str(
                    error
                )
            })

    return (
        acceptance_map,
        {
            "status":
            (
                "COMPLETE"
                if not failed_files
                else
                "PARTIAL"
            ),

            "historical_cutoff_date":
            cutoff_date,

            "recent_acceptance_count":
            recent_acceptance_count,

            "historical_acceptance_count":
            historical_acceptance_count,

            "total_acceptance_count":
            len(
                acceptance_map
            ),

            "historical_files_discovered":
            len(
                historical_files
            ),

            "historical_files_loaded":
            len(
                loaded_files
            ),

            "historical_files_failed":
            len(
                failed_files
            ),

            "loaded_files":
            loaded_files,

            "failed_files":
            failed_files
        }
    )


def normalize_metric_facts(
    metric,
    namespace,
    concept,
    concept_data,
    acceptance_map=None
):
    units = (
        (
            concept_data
            or
            {}
        ).get(
            "units",
            {}
        )
        or
        {}
    )

    rows = []

    for unit in unit_priority(
        metric,
        units
    ):
        for fact in (
            units.get(
                unit,
                []
            )
            or
            []
        ):
            if not isinstance(
                fact,
                dict
            ):
                continue

            form = str(
                fact.get(
                    "form",
                    ""
                )
            ).upper()

            if form not in ALLOWED_FORMS:
                continue

            filed = fact.get(
                "filed"
            )

            available_date = (
                conservative_available_date(
                    filed
                )
            )

            if not available_date:
                continue

            value = fact.get(
                "val"
            )

            if value is None:
                continue

            accession = normalize_accession(
                fact.get(
                    "accn"
                )
            )

            acceptance_metadata = (
                (
                    acceptance_map
                    or
                    {}
                ).get(
                    accession,
                    {}
                )
                or
                {}
            )

            rows.append({
                "metric":
                metric,

                "namespace":
                namespace,

                "concept":
                concept,

                "unit":
                unit,

                "value":
                value,

                "start":
                fact.get(
                    "start"
                ),

                "end":
                fact.get(
                    "end"
                ),

                "filed":
                filed,

                "available_date":
                available_date,

                "form":
                form,

                "fiscal_year":
                fact.get(
                    "fy"
                ),

                "fiscal_period":
                fact.get(
                    "fp"
                ),

                "accession":
                accession,

                "accepted_at":
                acceptance_metadata.get(
                    "accepted_at"
                ),

                "frame":
                fact.get(
                    "frame"
                )
            })

    return rows


def dedupe_facts(
    rows
):
    seen = set()
    result = []

    for row in rows:
        key = (
            row.get(
                "metric"
            ),
            row.get(
                "namespace"
            ),
            row.get(
                "concept"
            ),
            row.get(
                "unit"
            ),
            row.get(
                "start"
            ),
            row.get(
                "end"
            ),
            row.get(
                "filed"
            ),
            row.get(
                "form"
            ),
            row.get(
                "accession"
            ),
            str(
                row.get(
                    "value"
                )
            )
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            row
        )

    result.sort(
        key=lambda row: (
            str(
                row.get(
                    "available_date"
                    or
                    ""
                )
            ),
            str(
                row.get(
                    "end"
                    or
                    ""
                )
            ),
            str(
                row.get(
                    "metric"
                    or
                    ""
                )
            ),
            str(
                row.get(
                    "accession"
                    or
                    ""
                )
            )
        )
    )

    return result


def normalize_companyfacts(
    ticker,
    cik_value,
    payload,
    acceptance_map=None
):
    facts_root = (
        (
            payload
            or
            {}
        ).get(
            "facts",
            {}
        )
        or
        {}
    )

    all_rows = []
    matched_concepts = {}

    for namespace, metric_map in (
        METRIC_CONCEPTS_BY_NAMESPACE.items()
    ):
        namespace_facts = (
            facts_root.get(
                namespace,
                {}
            )
            or
            {}
        )

        for metric, concepts in (
            metric_map.items()
        ):
            metric_rows = []

            for concept in concepts:
                concept_data = namespace_facts.get(
                    concept
                )

                if not concept_data:
                    continue

                rows = normalize_metric_facts(
                    metric,
                    namespace,
                    concept,
                    concept_data,
                    acceptance_map=acceptance_map
                )

                if rows:
                    metric_rows.extend(
                        rows
                    )

                    matched_concepts.setdefault(
                        metric,
                        []
                    ).append(
                        namespace
                        +
                        ":"
                        +
                        concept
                    )

            all_rows.extend(
                metric_rows
            )

    normalized = dedupe_facts(
        all_rows
    )

    accessions = sorted(
        set(
            row.get(
                "accession"
            )
            for row in normalized
            if row.get(
                "accession"
            )
        )
    )

    latest_available_date = max(
        (
            row.get(
                "available_date"
            )
            for row in normalized
            if row.get(
                "available_date"
            )
        ),
        default=None
    )

    metric_fact_counts = dict(
        sorted(
            Counter(
                row.get(
                    "metric"
                )
                for row in normalized
                if row.get(
                    "metric"
                )
            ).items()
        )
    )

    taxonomy_fact_counts = dict(
        sorted(
            Counter(
                row.get(
                    "namespace"
                )
                for row in normalized
                if row.get(
                    "namespace"
                )
            ).items()
        )
    )

    exact_acceptance_fact_count = sum(
        1
        for row in normalized
        if row.get(
            "accepted_at"
        )
    )

    amendment_fact_count = sum(
        1
        for row in normalized
        if str(
            row.get(
                "form",
                ""
            )
        ).endswith(
            "/A"
        )
    )

    present_metrics = sorted(
        metric_fact_counts
    )

    missing_metrics = sorted(
        set(
            CANONICAL_METRICS
        )
        -
        set(
            present_metrics
        )
    )

    return {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "ticker":
        normalize_ticker(
            ticker
        ),

        "cik":
        cik10(
            cik_value
        ),

        "entity_name":
        (
            payload
            or
            {}
        ).get(
            "entityName"
        ),

        "source":
        "SEC_EDGAR_COMPANYFACTS",

        "taxonomies_supported":
        sorted(
            METRIC_CONCEPTS_BY_NAMESPACE
        ),

        "point_in_time":
        True,

        "availability_rule":
        (
            "available_date = SEC filed date + 1 calendar day; conservative "
            "guard against same-day look-ahead. Exact current and historical "
            "acceptance timestamps from SEC submissions metadata are stored "
            "for audit but do not make the daily as-of date earlier."
        ),

        "matched_concepts":
        matched_concepts,

        "metric_coverage": {
            "canonical_metric_count":
            len(
                CANONICAL_METRICS
            ),

            "present_metric_count":
            len(
                present_metrics
            ),

            "present_metrics":
            present_metrics,

            "missing_metrics":
            missing_metrics,

            "metric_fact_counts":
            metric_fact_counts
        },

        "taxonomy_fact_counts":
        taxonomy_fact_counts,

        "exact_acceptance_fact_count":
        exact_acceptance_fact_count,

        "exact_acceptance_coverage_pct":
        round(
            (
                exact_acceptance_fact_count
                /
                len(
                    normalized
                )
                *
                100.0
            ),
            2
        )
        if normalized
        else
        0.0,

        "amendment_fact_count":
        amendment_fact_count,

        "fact_count":
        len(
            normalized
        ),

        "accession_count":
        len(
            accessions
        ),

        "latest_available_date":
        latest_available_date,

        "facts":
        normalized
    }


def fetch_ticker_facts(
    client,
    ticker,
    ticker_map
):
    normalized = normalize_ticker(
        ticker
    )

    mapping = (
        ticker_map.get(
            normalized
        )
        or
        {}
    )

    cik_value = mapping.get(
        "cik"
    )

    if not cik_value:
        return {
            "engine":
            ENGINE_VERSION,

            "signature":
            SIGNATURE,

            "ticker":
            normalized,

            "status":
            "CIK_NOT_FOUND",

            "point_in_time":
            True,

            "facts":
            []
        }

    acceptance_map = {}
    submissions_metadata = {
        "status":
        "NOT_REQUESTED",

        "historical_cutoff_date":
        HISTORICAL_SUBMISSIONS_CUTOFF_DATE,

        "recent_acceptance_count":
        0,

        "historical_acceptance_count":
        0,

        "total_acceptance_count":
        0,

        "historical_files_discovered":
        0,

        "historical_files_loaded":
        0,

        "historical_files_failed":
        0,

        "loaded_files":
        [],

        "failed_files":
        []
    }

    try:
        (
            acceptance_map,
            submissions_metadata
        ) = load_acceptance_metadata(
            client,
            cik_value
        )

    except Exception as error:
        submissions_metadata[
            "status"
        ] = "UNAVAILABLE"

        submissions_metadata[
            "error"
        ] = str(
            error
        )

    payload = client.get_json(
        SEC_COMPANYFACTS_URL.format(
            cik10=cik_value
        )
    )

    result = normalize_companyfacts(
        normalized,
        cik_value,
        payload,
        acceptance_map=acceptance_map
    )

    result[
        "submissions_metadata"
    ] = submissions_metadata

    result[
        "status"
    ] = (
        "COMPLETE"
        if result.get(
            "fact_count",
            0
        )
        >
        0
        else
        "NO_MATCHED_FACTS"
    )

    return result


def latest_metric_as_of(
    ticker_record,
    metric,
    as_of_date
):
    cutoff = str(
        as_of_date
    )[:10]

    eligible = [
        row
        for row in (
            ticker_record.get(
                "facts",
                []
            )
            or
            []
        )
        if (
            row.get(
                "metric"
            )
            ==
            metric
            and
            str(
                row.get(
                    "available_date"
                    or
                    ""
                )
            )
            <=
            cutoff
        )
    ]

    if not eligible:
        return None

    eligible.sort(
        key=lambda row: (
            str(
                row.get(
                    "available_date"
                    or
                    ""
                )
            ),
            str(
                row.get(
                    "end"
                    or
                    ""
                )
            ),
            str(
                row.get(
                    "filed"
                    or
                    ""
                )
            )
        )
    )

    return eligible[
        -1
    ]


def build_snapshot_as_of(
    ticker_record,
    as_of_date
):
    snapshot = {}

    for metric in CANONICAL_METRICS:
        fact = latest_metric_as_of(
            ticker_record,
            metric,
            as_of_date
        )

        if fact is not None:
            snapshot[
                metric
            ] = fact

    return {
        "ticker":
        ticker_record.get(
            "ticker"
        ),

        "as_of_date":
        str(
            as_of_date
        )[:10],

        "point_in_time":
        True,

        "metric_count":
        len(
            snapshot
        ),

        "metrics":
        snapshot
    }
