# Simple Factor Challenger — Data-Source Amendment v1.1

**Status:** FROZEN BEFORE READING THE COMBINED-SOURCE RESULT  
**Amendment date:** 2026-10-25  
**Original pre-registration:** `docs/research/simple_factor_challenger_preregistration_v1.md`

## Why this amendment exists

The original 2012–2021 holdout run failed its pre-registered data-quality gate because Yahoo Finance / yfinance did not return sufficient historical price coverage for many old, renamed, acquired, or delisted symbols.

The original result was therefore:

`CHALLENGER_DATA_INSUFFICIENT`

This amendment is triggered by **data coverage failure**, not by a desire to improve strategy performance.

The strategy formula, portfolio construction, benchmark, transaction-cost model, holdout period, and PASS/FAIL criteria remain unchanged.

## What is changed

Only historical price-data recovery is expanded.

The retrieval hierarchy is frozen as:

1. Yahoo Finance / yfinance batch adjusted daily prices.
2. Yahoo smaller-batch retry.
3. Yahoo single-symbol retry.
4. Yahoo `Ticker.history()` fallback only for securities that were still members of S&P 500 or Nasdaq-100 at the end of the primary holdout period.
5. For symbols still missing after Yahoo recovery, use the public Kaggle/Stooq historical dataset mirror:
   - Repository: `wmhbrown121/trade-datasets`
   - Commit: `c2a1af916490810bc01866deefbd509620225846`
   - Original dataset: Boris Marjanovic, Huge Stock Market Dataset
   - Data vintage: through 2017-11-10
   - Documented adjustment convention: prices adjusted for dividends and splits.
   - License: CC0 / public domain as documented by the original Kaggle dataset.

The fallback is used only where Yahoo produced no usable history for that symbol. It is not allowed to replace a valid Yahoo series based on which source produces better strategy results.

## What is NOT changed

The following remain exactly as pre-registered:

- Primary holdout: 2012-01-01 through 2021-12-31.
- S&P 500 and Nasdaq-100 point-in-time membership source.
- 12-month momentum definition.
- 6-month relative-strength definition.
- 50/50 factor weighting.
- Cross-sectional percentile ranking.
- Top-12 equal-weight portfolio.
- Monthly rebalance.
- Prior-session information cutoff.
- First benchmark trading-day close execution.
- 10 bps friction per traded notional.
- Point-in-time equal-weight primary control.
- Coverage validity thresholds.
- PASS rule: positive CAGR advantage AND non-negative Sharpe advantage.
- Overall verdict rules.
- Research-only / no-live-promotion status.

## Interpretation rule

Results produced under this amendment must be labeled:

`DATA_SOURCE_AMENDED_HOLDOUT`

They are stronger than the original incomplete Yahoo-only run because they address documented missing-history bias, but they are not described as a perfectly untouched pre-registration because the price-source hierarchy was amended after the original coverage failure was observed.

No further source, formula, threshold, portfolio-size, horizon, benchmark, or performance-rule change is allowed after this amendment without creating a new named protocol version.

## Failure rule remains binding

If the amended dataset passes the original coverage gate, the original PASS/FAIL rules are applied without relaxation.

If coverage still fails, the result remains:

`CHALLENGER_DATA_INSUFFICIENT`

and a higher-quality survivorship-aware historical price source is required.

## Live-system isolation

Regardless of result:

- V7.9 live policy is unchanged.
- V8.2 shadow policy is unchanged.
- V8.4.8 promotion gate is unchanged.
- Paper order submission remains blocked.
- Live broker execution remains blocked.
