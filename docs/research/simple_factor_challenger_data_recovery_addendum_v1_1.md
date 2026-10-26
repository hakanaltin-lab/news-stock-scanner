# Simple Factor Challenger — Data Recovery Addendum v1.1

**Date:** 2026-10-26  
**Scope:** Data-quality repair only. Strategy formula, holdout period, portfolio construction, transaction cost and PASS/FAIL criteria remain unchanged.

## Why this addendum exists

The first pre-registered 2012–2021 holdout run returned `CHALLENGER_DATA_INSUFFICIENT`, not a strategy PASS or FAIL. The pre-registration explicitly requires a better historical price source before adjudication when point-in-time coverage fails.

The membership source documents that Nasdaq-100 history before 2017 is reliable but imperfect and that some historical constituents may carry later ticker symbols. Yahoo also does not consistently return historical prices for renamed or delisted symbols.

## Frozen recovery rule

Historical price recovery may use an alternate ticker **only when it represents the same continuous listed equity security through a documented ticker/name change**.

Allowed recovery is limited to explicitly documented continuity mappings:

- `NLOK <- SYMC` for history before NortonLifeLock began trading under NLOK on 2019-11-05.
- `RIMM <- BB` / BlackBerry security lineage for the pre-2013 Research In Motion period.
- `KFT <- MDLZ` for the pre-2012 Kraft/Mondelez ticker transition already documented by the PIT membership source.
- `HANS <- MNST` for the Hansen Natural / Monster Beverage ticker transition already documented by the PIT membership source.

The recovery source currently used is the pinned public Kaggle/Stooq mirror already integrated into the holdout engine:

- Repository: `wmhbrown121/trade-datasets`
- Commit: `c2a1af916490810bc01866deefbd509620225846`
- Dataset cutoff: 2017-11-10

## Prohibited recovery

The following are prohibited:

- Using the acquirer’s stock to replace an acquired company.
- Using a peer/security proxy.
- Backfilling missing prices by interpolation.
- Forward-filling prices to initiate a new position.
- Mapping a ticker based only on a similar company name.
- Changing the challenger score, weights, rebalance schedule, Top-12 size, costs or PASS/FAIL gates.
- Selecting mappings because they improve challenger performance.

If continuity cannot be documented, the ticker remains missing.

## Interpretation

This addendum repairs symbol/data continuity only. It does not create new information or alter the pre-registered stock-selection hypothesis. The official holdout verdict remains invalid until all original data-quality gates pass.
