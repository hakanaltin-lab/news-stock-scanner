# SEC fact quarantine v1.0

Effective: 2026-10-27. Data-quality maintenance only; no alpha or trading change.

A normalized fact must satisfy the existing date, numeric, concept, form,
unit and accession rules before entering the primary archive. In particular,
`period_end <= filed_date` and `available_date >= filed_date + 1 calendar day`
remain mandatory. Rejected dates and financial values must never be inferred,
shifted or overwritten to make a record eligible.

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
