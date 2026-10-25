# AURORA Simple Factor Challenger — Pre-Registration v1.0

**Status:** FROZEN BEFORE TEST EXECUTION  
**Pre-registration date:** 2026-10-25  
**Purpose:** Independently test a simple price-only stock-selection challenger without using the 2022–2026 discovery period as primary evidence.

## 1. Research question

Can a simple, pre-specified combination of 12-month momentum and 6-month relative strength select a 12-stock portfolio that outperforms the point-in-time equal-weight investable universe after modeled trading costs, on a period that was not used to identify these factors?

This is a stock-selection test. It is not a test of AURORA's news, catalyst, fundamental-thesis, event-risk, broker, or live-execution layers.

## 2. Discovery period vs holdout period

The 2022-06-01 to 2026-06-05 V8.6 PIT validation period is classified as **DISCOVERY / SECONDARY ONLY** because the proposed factors were highlighted after inspecting that period.

The primary challenger test is frozen as:

- **Primary holdout calendar period:** 2012-01-01 through 2021-12-31 inclusive.
- Monthly execution occurs on the first benchmark trading day of each month.
- Membership and factors are measured using information available on the prior trading session.
- No result from 2022–2026 may be used to alter the challenger definition, weights, rebalance frequency, portfolio size, friction assumption, or PASS/FAIL rules after this document is committed.

The 2022–2026 period may be reported only as a secondary consistency diagnostic after the primary holdout result is calculated.

## 3. Point-in-time universes

Two universes are tested independently:

1. S&P 500 point-in-time membership, benchmark ETF SPY.
2. Nasdaq-100 point-in-time membership, benchmark ETF QQQ.

Membership source is frozen to:

- Repository: `thuningxu/sp500nq100`
- Commit: `1cc1de2770874293597a418b41b079e5337b260c`
- S&P file: `sp500_components_history.csv`
- Nasdaq-100 file: `nasdaq100_components_history.csv`

The latest membership snapshot effective on or before the decision date is used.

## 4. Price data and eligibility

Adjusted daily close data are obtained using the same Yahoo Finance / yfinance convention used by V8.6.

A security is eligible at a monthly decision date only if:

- It is a point-in-time member of the relevant index.
- It has at least 252 prior valid daily close observations.
- Both pre-registered challenger features can be calculated.
- An exact execution-date close exists for a new purchase.

Existing positions may use forward-filled prices for valuation only when a daily quote disappears, matching the V8.6 convention. Forward-filled prices may not be used to initiate a new position.

## 5. Frozen challenger formula

No thresholds, filters, sector rules, volatility filters, risk-overlay rules, news inputs, fundamental inputs, or discretionary adjustments are allowed.

For every eligible stock on each decision date:

### Feature A — 12-month momentum

`return_12m_pct` = percentage return over the prior 252 trading sessions, measured exactly as in `strategic_state_as_of()`.

### Feature B — 6-month relative strength

`relative_strength_6m_pct` = stock 126-session percentage return minus benchmark ETF 126-session percentage return, measured exactly as in `strategic_state_as_of()`.

Benchmark is SPY for the S&P 500 test and QQQ for the Nasdaq-100 test.

### Cross-sectional ranking

Within each point-in-time eligible universe and decision date:

- Rank `return_12m_pct` cross-sectionally from worst to best using average ranks for ties.
- Convert the rank to a 0–100 percentile score.
- Rank `relative_strength_6m_pct` the same way.
- Calculate:

`challenger_score = 0.50 * momentum_12m_percentile + 0.50 * relative_strength_6m_percentile`

No other feature is permitted.

## 6. Portfolio construction

- Select the top **12** securities by `challenger_score`.
- Equal weight the selected securities.
- Fully invested subject only to missing execution quotes.
- No AURORA V7.9 risk overlay.
- No cash timing rule.
- No sector cap.
- No turnover buffer.
- No fundamental or news confirmation.
- Monthly rebalance on the first benchmark trading day.
- Decision information cutoff: prior trading session.
- Execution assumption: rebalance at that month's first benchmark trading-day close.

Tie break, if challenger scores are identical:

1. Higher 12-month momentum percentile.
2. Higher 6-month relative-strength percentile.
3. Alphabetical ticker order.

## 7. Transaction costs

Trading friction is frozen at **10 basis points per traded notional**, identical to V8.6.

The reported primary result is always **after modeled transaction costs**.

No additional tax model is included. This limitation must be stated in the result.

## 8. Primary control portfolio

The primary benchmark for stock-selection alpha is the **point-in-time equal-weight investable universe**.

It must:

- Use the same point-in-time membership.
- Use the same price-data eligibility rules.
- Rebalance monthly.
- Use the same 10 bps trading-friction model.
- Use the same execution timing.

SPY and QQQ are secondary market benchmarks, not the primary stock-selection controls.

## 9. Data-quality validity gate

A universe test is eligible to produce a research verdict only if all are true:

- At least **100 monthly rebalance observations** are available.
- Average point-in-time execution coverage is at least **85%**.
- Minimum monthly execution coverage is at least **75%**.
- At least 12 eligible securities with exact execution quotes are available at each counted challenger rebalance.

If these conditions fail, that universe receives:

`INVALID_DATA_COVERAGE`

It must not be counted as a challenger PASS or FAIL.

Missing/delisted/renamed security coverage must be reported explicitly.

## 10. Pre-registered success / failure rules

For each valid universe, calculate:

- Challenger after-cost CAGR.
- PIT equal-weight after-cost CAGR.
- CAGR advantage = Challenger CAGR − PIT EW CAGR.
- Challenger Sharpe.
- PIT equal-weight Sharpe.
- Sharpe advantage = Challenger Sharpe − PIT EW Sharpe.

A universe **PASSES** only if both are true:

1. `CAGR advantage > 0.00 percentage points`
2. `Sharpe advantage >= 0.000`

No post-test relaxation is allowed.

### Overall verdict

**CHALLENGER_VALIDATED_GENERAL**

- Both S&P 500 and Nasdaq-100 tests are valid, and
- Both universes PASS.

**CHALLENGER_UNIVERSE_SPECIFIC_ONLY**

- Both tests are valid, and
- Exactly one universe PASSes.

This does not validate the challenger for general AURORA use.

**CHALLENGER_NOT_VALIDATED**

- Both tests are valid, and
- Neither universe PASSes.

If this occurs, the current **price-only cross-sectional stock-ranking research line is closed**. AURORA remains positioned as a risk / discipline / monitoring system unless a materially new, independently testable information source or hypothesis is introduced. The same price-history period may not be mined for another replacement factor combination.

**CHALLENGER_DATA_INSUFFICIENT**

- One or both universe tests fail the data-quality validity gate.

This is not a strategy PASS or FAIL. A better point-in-time price source is required before adjudication.

## 11. Secondary diagnostics

The following are reported but cannot override the primary verdict:

- Total return.
- Max drawdown.
- Sortino.
- Calmar.
- Annualized volatility.
- Annualized turnover.
- Total modeled trading costs.
- SPY / QQQ CAGR comparison.
- Calendar-year performance.
- 2022–2026 discovery-period replay.
- Cross-sectional Spearman and quintile spreads.

A favorable secondary metric may not rescue a failed primary rule.

## 12. Anti-overfitting rules

After this pre-registration commit, the following are prohibited before reading the primary result:

- Changing 50/50 factor weights.
- Replacing 12M or 6M horizons.
- Adding a third factor.
- Adding market-regime filters.
- Adding volatility or risk filters.
- Changing Top-12 portfolio size.
- Changing monthly rebalance frequency.
- Adding sector constraints.
- Adding a turnover buffer.
- Changing transaction-cost assumptions.
- Changing the 2012–2021 primary holdout window.
- Changing PASS/FAIL criteria because of observed performance.

Any future alternative specification requires a new named research hypothesis and a new genuinely independent validation dataset. It may not reuse 2012–2021 as fresh holdout evidence.

## 13. Live-system isolation

This challenger is research-only.

Regardless of result:

- It does not change V7.9 live portfolio actions.
- It does not change the V8.2 shadow candidate automatically.
- It does not modify V8.4.7 promotion rules.
- It does not authorize paper order submission.
- It does not authorize live broker execution.
- Any adoption requires a separate explicit manual review after the pre-registered test.

## 14. Interpretation guardrail

The factors were motivated by V8.6 diagnostics and by the broader momentum literature, but the 2012–2021 result must be treated as the first primary AURORA holdout test of this exact 50/50 challenger.

The test should answer one narrow question:

> Does this exact simple price-only ranking beat the same point-in-time equal-weight investable universe after costs, with no post-hoc tuning?

No other claim is pre-authorized.
