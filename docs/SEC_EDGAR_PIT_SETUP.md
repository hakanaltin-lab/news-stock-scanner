# AURORA V8.8 — SEC EDGAR Point-in-Time Fundamental Setup

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

The first SEC archive covers the current AURORA evidence universe
(`data/us_universe.json` plus `data/portfolio.csv`).

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
- frame when supplied

## Point-in-time rule

Company Facts usually provides a filing date rather than a complete historical
acceptance timestamp for every normalized fact. To prevent same-day look-ahead,
AURORA uses:

    available_date = filed_date + 1 calendar day

A future version may enrich this with exact acceptance timestamps from SEC
submission metadata, but it must never make evidence available earlier than
the original filing.

## SEC endpoints

- Ticker/CIK mapping: `www.sec.gov/files/company_tickers.json`
- Company Facts: `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Requests are throttled by AURORA below the SEC's published 10 requests/second
maximum.

## Next milestone after first successful archive

1. Validate CIK coverage for the current evidence universe.
2. Extend SEC evidence scope to the current S&P 500 + Nasdaq-100 union.
3. Add IFRS concept support for relevant foreign issuers/ADRs.
4. Add exact submission acceptance timestamps where available.
5. Only then define a new pre-registered fundamental research hypothesis.
