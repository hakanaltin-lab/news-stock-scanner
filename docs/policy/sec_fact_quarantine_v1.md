# SEC fact quarantine and semantic contract v1.1

Effective: 2026-10-27. Data-quality maintenance only; no alpha or trading change.

A normalized fact must satisfy the existing date, numeric, concept, form,
unit and accession rules before entering the primary archive. In particular,
`period_end <= filed_date` and `available_date >= filed_date + 1 calendar day`
remain mandatory. Rejected dates and financial values must never be inferred,
shifted or overwritten to make a record eligible.

The V8.9.3 semantic admission rules are metric-specific:

- Revenue, operating income, net income, operating cash flow and capex are
  monetary duration facts. Their source unit must be an exact three-uppercase-
  letter currency unit and their source context must include a valid start date.
- Diluted EPS is a duration fact. Its exact source unit must be
  `<reported currency>/shares`, such as `USD/shares` or `EUR/shares`.
  `pure`, `shares`, inverse units and unrelated physical units are incompatible.
- Cash, assets, liabilities, equity and debt are monetary instant facts. Their
  source unit must be an exact three-uppercase-letter currency unit and their
  source context must not contain a start date.

These syntax rules establish dimensional compatibility; they do not assert
that every three-letter source unit is the issuer's correct presentation
currency. Reported currencies are retained literally. No FX conversion,
currency substitution or unit repair is permitted.

When a successful issuer response contains both valid and invalid facts:

1. Preserve every invalid normalized fact and its exact rejection reasons in
   `data/sec_edgar_pit/quarantine/<ticker>.json`.
2. Admit only rows that independently pass the same existing rules.
3. Recompute fact counts, concept coverage, accession counts, taxonomy counts,
   acceptance coverage and amendment counts from admitted rows only.
4. Record source counts, quarantine counts and the quarantine reference in the
   admitted issuer file. Report original source issues separately from issues
   still present in the admitted archive.
5. Preserve all legitimate filing and amendment versions. A later amendment
   does not become visible before its original availability date.

## Comparable as-of selection

Snapshot selection is explicit and deterministic. For each metric it filters
to facts available on the requested as-of date, the requested duration class
(`quarter`, `year_to_date`, `annual` or `nonstandard_duration`) and, when
provided, the requested reported currency. It then selects:

1. the latest reported period end;
2. the latest available filing version for that period; and
3. the first available mapped concept in the declared canonical concept order.

Duration classification follows the SEC calendar-frame tolerances: 61–121
days is a quarter and 335–395 days is annual. Valid durations between those
ranges are `year_to_date`; shorter or longer valid contexts remain explicit as
`nonstandard_duration` rather than being re-dated.

An amendment of an older reporting period cannot displace a newer reporting
period. Quarter, YTD and annual facts are never summed or substituted for one
another. When the selected filing version contains more than one compatible
reported currency and the caller has not requested one, selection fails closed
as `ambiguous_reporting_currency`; it never performs an implicit conversion.

The snapshot reports each selected duration context, selected currencies and
whether those contexts are exactly aligned. Technical comparability does not
authorize a research hypothesis, strategy promotion, paper order or LIVE order.

An empty response, invalid issuer identity or unsuccessful fetch remains
unusable. An all-invalid response never overwrites a previous valid archive.
Unsupported financial taxonomies remain explicit coverage gaps; do not fill
them with zero, inherited company data, prices or third-party fundamentals.

Non-finite numbers cannot appear as JSON financial values. The quarantine
ledger encodes them as explicit textual audit markers. They are never promoted
into usable values.

`point_in_time_validation_passed` applies to the admitted rows. Original source
issues and quarantined counts remain visible even when the admitted dataset
passes. Collection/coverage readiness does not authorize research use, a new
strategy, paper orders or live execution.
