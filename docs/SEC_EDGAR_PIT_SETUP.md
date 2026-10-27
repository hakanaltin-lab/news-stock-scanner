# AURORA V8.8.3 — SEC EDGAR Point-in-Time Fundamental Setup

AURORA's SEC foundation uses the public SEC EDGAR data APIs for historical,
filing-dated fundamental evidence. It does not submit filings and requires no
SEC API key.

## Safety / research state

- Research and data-foundation only.
- Live portfolio actions are unchanged.
- Paper-order submission remains blocked.
- Live broker execution remains blocked.
- Price-only research freeze remains in force.
- SEC data must not be used in a new alpha model until a separate named,
  pre-registered fundamental research protocol is created.

## Current operational status

The code, synthetic no-lookahead tests, current-index scope, IFRS mappings,
historical submission-shard enrichment and coverage telemetry are in place.
The first real SEC archive has not yet been produced because the repository
does not currently expose `SEC_USER_AGENT` to the workflow.

The workflow now fails closed when this secret is missing. A green workflow
therefore means that the SEC archive actually ran; a disabled no-op can no
longer be mistaken for a successful archive.

## SEC fair-access requirement

SEC automated access requires a declared User-Agent with contact information.
AURORA intentionally does not hard-code a personal email address in the repo.

Create a GitHub Actions repository secret named:

    SEC_USER_AGENT

Use a value in the SEC-declared format, for example:

    AURORA Research your-contact-email@example.com

Use an email address you control and monitor.

Do not place the contact email directly in source code.

## GitHub setup

Repository:

    hakanaltin-lab/news-stock-scanner

Open:

    Settings
    → Secrets and variables
    → Actions
    → New repository secret

Name:

    SEC_USER_AGENT

Value:

    AURORA Research <your monitored contact email>

After the secret is added, run the workflow manually once:

    Actions
    → SEC EDGAR PIT Fundamental Archive
    → Run workflow

## Current first milestone

The SEC archive now prefers the daily current-index snapshot
(`data/current_index_universe/latest.json`) and therefore covers the current
S&P 500 + Nasdaq-100 union, while always adding AURORA scanner/portfolio names
that fall outside those indices. If the current-index snapshot is unavailable,
it fails safely back to the smaller AURORA core universe.

For each ticker it stores normalized filing-dated facts for:

- revenue
- operating income
- net income
- diluted EPS
- operating cash flow
- capex
- cash
- total assets
- total liabilities
- stockholders' equity
- long-term debt
- current debt

Each reported fact preserves:

- SEC concept
- unit
- value
- period start/end
- filed date
- conservative availability date
- form
- fiscal year / fiscal period
- accession number
- exact SEC acceptance timestamp when available
- acceptance metadata source coverage
- frame when supplied

The engine reads both the current submissions payload and SEC-provided
historical submission shard files ending in the XBRL era (2009 onward). This
extends exact acceptance-time audit coverage beyond the most recent filing
window without crawling pre-XBRL history.

## Point-in-time rule

Company Facts provides filing dates but not complete acceptance timestamps.
The submissions API is used to enrich current and historical accessions with
exact acceptance times. To remain conservative at daily model resolution,
AURORA still uses:

    available_date = filed_date + 1 calendar day

The exact timestamp is retained for audit and future intraday-safe research,
but it never makes the daily `available_date` earlier than the rule above.

## V8.9.3 collection readiness, semantic contract and fact quarantine

The workflow's offline no-lookahead tests and its real data collection are
separate checks. A missing `SEC_USER_AGENT` now exits with code 2, publishes
`DISABLED_MISSING_SEC_USER_AGENT`, and fails the collection step. It must not be
interpreted as a successful SEC archive. The workflow still publishes its
blocked status so the dashboard shows the setup requirement.

Readiness is published in:

- `data/sec_edgar_pit/latest_summary.json`: complete per-ticker collection report.
- `docs/sec_archive_readiness.json`: compact public dashboard status.
- GitHub Actions job summary: collection status and usable ticker count.

Reports count CIK matches, actual normalized facts, metric coverage, US-GAAP /
IFRS namespaces, reporting units, amended facts, and exact acceptance metadata.
Missing metrics remain explicit gaps; different units are never converted or
combined by the coverage report. Current constituents remain a forward
universe and must not be substituted for historical index membership.

Rows with invalid dates, availability earlier than filing plus one day,
non-finite/non-numeric values, missing core provenance, incompatible metric
units, or incompatible instant/duration context shapes fail the quality check.
They are preserved with their original dates, units and values in
`data/sec_edgar_pit/quarantine/<ticker>.json`; independently valid rows from a
successful issuer response remain eligible. No row-admission rule is relaxed,
no date is corrected, and no missing financial value is imputed. See
[SEC fact quarantine policy](policy/sec_fact_quarantine_v1.md).

V8.9.3 accepts exact three-uppercase-letter source currency units for monetary
facts and exact `<currency>/shares` source units for diluted EPS. It does not
convert currencies. Revenue, income, cash flow, capex and EPS require duration
contexts; cash, balance-sheet and debt metrics require instant contexts.

As-of snapshots request a duration class explicitly. Selection orders by
latest period end before latest filing version, so a later amendment of an
older period cannot replace a newer period. The declared canonical concept
order resolves overlapping mapped concepts within the selected filing.
Multiple reported currencies in the selected filing fail closed unless the
caller requests one; quarter, YTD and annual facts are never mixed implicitly.
Snapshot output includes exact context and currency-alignment diagnostics, no
FX conversion, and all research/order authorization flags remain false.

A failed or empty fetch, invalid issuer identity, or response with no valid
facts never replaces an existing valid fact file. Retained older evidence does
not count as current-run coverage. The report keeps original
`source_quality_issues` and `quarantined_fact_count` separate from
`quality_issues` in the admitted archive. The point-in-time validation flag
applies to admitted rows, not to quarantined source data. Up to 20 source
date/provenance examples are retained per rejected issuer.
Bootstrap failures and runs with no usable facts exit nonzero and publish an
explicit blocker. A usable archive with missing issuers or concepts reports
`COMPLETE_WITH_GAPS`; `COMPLETE` requires full issuer and metric coverage.
An issuer with only unsupported financial taxonomies is explicitly reported
as `NO_SUPPORTED_FINANCIAL_TAXONOMY`; it is not filled with unrelated data.

`collection_ready` means data was collected, not that a strategy is validated.
The research-use, paper-order and LIVE-execution authorization fields remain
false in every state. The User-Agent and contact address are never written to
public reports or exception messages.

Offline verification:

    PYTHONPATH=. python scripts/test_sec_edgar_pit_engine.py
    python -m unittest discover -s tests -p 'test_sec_archive_readiness.py' -v
    python -m unittest discover -s tests -p 'test_sec_evidence_publish.py' -v
    PYTHONPATH=. python scripts/audit_sec_semantic_contract.py --require-clean

## Evidence publication and recovery

An Actions rerun can start from an older checkout even after newer status
reports have been committed to `main`. Generated SEC JSON must not be rebased
over those reports: the publisher saves its collected files, advances to the
latest `main`, restores only the SEC evidence paths and retries a raced push
up to three times. Concurrent changes outside those paths are preserved.

The workflow uploads a run-specific evidence artifact before publishing, with
three-day retention. A publication failure can therefore be recovered without
repeating all SEC requests. A successful collection step alone does not mean
the archive was durably published; inspect the publication step as well.

## SEC endpoints

- Ticker/CIK mapping: `www.sec.gov/files/company_tickers.json`
- Company Facts: `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Requests are throttled by AURORA below the SEC's published 10 requests/second
maximum.

## Next milestone after first successful archive

1. Validate CIK coverage for the current S&P 500 + Nasdaq-100 union.
2. Review the emitted per-metric, taxonomy and exact-acceptance coverage.
3. Validate historical concept continuity and amended filings on real data.
4. Freeze explicit data-quality thresholds before reading any alpha result.
5. Only then define a new pre-registered fundamental research hypothesis.

Official sources:

- [SEC data API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC fair-access and declared User-Agent requirements](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
