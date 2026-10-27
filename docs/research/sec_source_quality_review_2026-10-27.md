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

### Remaining feature-readiness work

This repair validates record admission, not comparability of derived model
features. The WMT source review also found three historical diluted-EPS facts
with unit `pure`, all filed on 2010-09-01 under accession
0001193125-10-202779. Their units are retained literally and are not converted
to currency/share values. They must be resolved or excluded by an explicit
unit contract before any fundamental model uses them.

Currency consistency, quarter/year/YTD duration alignment and latest-period
selection also require a separate feature-readiness review. Existing raw
filing versions must not be summed across units or durations. None of these
source-coverage results authorizes fundamental research or portfolio changes.

### Reproducible validation

- `tests/test_sec_archive_readiness.py`: strict per-row validity, mixed-record
  isolation, value/date preservation, non-finite audit encoding, amendment
  availability, identity blocking, and unsupported-taxonomy classification.
- `engines/sec_archive_quality_engine.py`: shared admission predicate,
  quarantine provenance and count recomputation.
- `data/sec_edgar_pit/latest_summary.json`: published coverage and source issues.
- `data/sec_edgar_pit/quarantine/`: original rejected facts after publication.

## Controlling sources

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
