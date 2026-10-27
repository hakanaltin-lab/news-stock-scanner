# SEC source-quality review — 2026-10-27

Scope: the six issuers excluded by the first successful 520-ticker SEC
collection. This is data-quality maintenance, with no alpha search, portfolio
policy change or broker-order authorization.

## Finding and remedy

The original issuer-level all-or-nothing check excluded 13,062 facts passing
the existing date, numeric and provenance rules alongside 12 facts whose reported period end was later than the
filing date. Each rejected fact retains its original date, numeric value,
metric, concept and accession in a separate quarantine ledger. Only rows that
pass the unchanged admission rules enter the primary archive. Source dates
are not reinterpreted as earlier dates.

| Ticker | Normalized source facts | Valid facts | Quarantined facts |
|---|---:|---:|---:|
| GD | 2,008 | 2,007 | 1 |
| LLY | 1,765 | 1,764 | 1 |
| MKC | 2,922 | 2,921 | 1 |
| ROP | 2,653 | 2,645 | 8 |
| WMT | 3,726 | 3,725 | 1 |
| Total | 13,074 | 13,062 | 12 |

These counts are from the source review, not a claim that a new collection
has already been published. The archive summary records the actual result.
The review cannot establish whether each future-period context is a source
tagging error or a forward-looking disclosure; both remain inadmissible as
realized historical financial facts.

The as-of rule remains `available_date >= filed_date + 1 calendar day`.
Original and amended filings remain separate versions. The exact acceptance
timestamp is audit metadata and does not advance daily availability.

## VYLR

The Company Facts response for CIK 0002128626 identifies Vylor Inc. and contains
four concepts under `ffd`, with no `us-gaap` or `ifrs-full` namespace. No
canonical financial fact is admitted. This is an explicit source-coverage gap;
the system does not import a predecessor company's financials or treat missing
values as zero. The submissions response and the issuer's October 2026 8-K
confirm a recently separated issuer, but do not supply the supported canonical
Company Facts data required by this foundation.

## Inspectable checks

### V8.9.3 unit, period and snapshot review

The follow-up profile covered all 519 currently usable issuer files and
1,111,499 admitted facts. It found 225 additional rows across 44 tickers that
fail the new semantic contract:

| Finding | Affected rows |
|---|---:|
| EPS unit incompatible with currency/share semantics | 216 |
| Duration metric missing a source start date | 9 |
| Total rows failing at least one new rule | 225 |

The incompatible EPS units are `pure`, `shares`, `shares/USD`,
`BillionsCubicFeet` and `segment`. The duration-shape exceptions affect five
capex facts, two revenue facts, one net-income fact and one EPS fact. The three
historical WMT `pure` EPS facts under accession 0001193125-10-202779 are part of
this broader result. All source units, dates and values remain unchanged in the
quarantine ledger; none is converted to currency/share.

The snapshot review also found 130,837 same-context groups containing more
than one mapped canonical concept across 513 tickers; 107,073 of those groups
contain different values. V8.9.3 therefore makes concept fallback order an
explicit selection rule rather than relying on input order. Selection now uses
the newest reported period first, then the newest available filing version for
that period, then the declared canonical concept priority. A late amendment of
an older period cannot displace a newer period.

Quarter, YTD, annual and instant contexts are classified separately. Exact
duration contexts and reported currencies are exposed in snapshot diagnostics.
Multiple currencies in the selected filing fail closed unless a reported
currency is requested, and no FX conversion occurs. This makes incompatibility
visible; it does not yet authorize a fundamental hypothesis or portfolio use.

These are offline pre-publication profile counts against the then-current
primary archive. The published archive summary remains the controlling source
for actual post-collection admitted and quarantined counts.

### Reproducible validation

- `tests/test_sec_archive_readiness.py`: strict per-row validity, mixed-record
  isolation, value/date preservation, unit and period-shape contracts,
  non-finite audit encoding, amendment availability, identity blocking, and
  unsupported-taxonomy classification.
- `scripts/test_sec_edgar_pit_engine.py`: period-first as-of selection,
  quarter/YTD separation, canonical concept priority, multi-currency blocking,
  no-FX behavior and research/order safety state.
- `scripts/audit_sec_semantic_contract.py`: full-archive unit/period profile,
  concept-overlap inventory, snapshot diagnostics and summary/quarantine
  reconciliation; the post-collection workflow requires a clean result.
- `engines/sec_archive_quality_engine.py`: shared admission predicate,
  quarantine provenance and count recomputation.
- `data/sec_edgar_pit/latest_summary.json`: published coverage and source issues.
- `data/sec_edgar_pit/quarantine/`: original rejected facts after publication.

## Controlling sources

- [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [GD Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000040533.json)
- [LLY Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000059478.json)
- [MKC Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000063754.json)
- [ROP Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000882835.json)
- [WMT Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000104169.json)
- [VYLR Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0002128626.json)
- [VYLR submissions](https://data.sec.gov/submissions/CIK0002128626.json)
- [VYLR 8-K, accession 0001193125-26-419727](https://www.sec.gov/Archives/edgar/data/2128626/000119312526419727/d170287d8k.htm)
- [LLY 2013 10-K filing detail](https://www.sec.gov/Archives/edgar/data/59478/000005947814000078/0000059478-14-000078-index.html)
- [ROP 2009 Q3 10-Q filing detail](https://www.sec.gov/Archives/edgar/data/882835/000088283509000045/0000882835-09-000045-index.html)
