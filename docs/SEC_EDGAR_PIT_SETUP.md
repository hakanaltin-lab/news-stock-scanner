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
