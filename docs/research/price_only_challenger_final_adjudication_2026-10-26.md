# AURORA Price-Only Challenger — Final Adjudication & Research Freeze

**Decision date:** 2026-10-26  
**Primary protocol:** `simple_factor_challenger_preregistration_v1.md`  
**Data-source amendment:** `simple_factor_challenger_data_source_amendment_v1_1.md`  
**Ticker continuity addendum:** `simple_factor_challenger_data_recovery_addendum_v1_1.md`

## Final valid holdout outcome

The amended 2012–2021 holdout passed the original data-quality gates for both universes.

### S&P 500

- Verdict: **FAIL**
- Challenger CAGR: **16.42%**
- PIT equal-weight CAGR: **15.57%**
- CAGR advantage: **+0.85 pp**
- Challenger Sharpe: **0.770**
- PIT equal-weight Sharpe: **0.913**
- Sharpe advantage: **-0.143**
- Annualized turnover: **26.74x**

The pre-registered rule required both positive CAGR advantage and non-negative Sharpe advantage. S&P 500 therefore fails.

### Nasdaq-100

- Verdict: **PASS**
- Data label: **DATA_SOURCE_AMENDED_HOLDOUT**
- Challenger CAGR: **29.84%**
- PIT equal-weight CAGR: **19.93%**
- CAGR advantage: **+9.91 pp**
- Challenger Sharpe: **1.160**
- PIT equal-weight Sharpe: **1.064**
- Sharpe advantage: **+0.096**
- Annualized turnover: **29.62x**

Original data coverage was insufficient. The final valid result was obtained only after the frozen data-source amendment and documented ticker-continuity recovery. It is therefore not described as a pristine untouched holdout.

## Overall verdict

`CHALLENGER_UNIVERSE_SPECIFIC_ONLY`

This does **not** validate a general AURORA price-only stock-selection model.

The S&P 500 failure is final and must not be re-optimized or re-run to search for a better price-only specification.

The Nasdaq result is retained as universe-specific research evidence only. It does not authorize changing the live AURORA ranking model, the V8.2 shadow policy, V8.4.8 promotion logic, paper-order submission, or live execution.

## Research freeze

Effective immediately:

- No new price-only factor combinations using the 2012–2021 or 2022–2026 datasets.
- No new momentum horizon search.
- No re-weighting of the 12M momentum / 6M relative-strength challenger.
- No additional ticker/data repair for the purpose of improving the challenger result.
- No threshold optimization based on the observed holdout results.
- No automatic challenger workflow runs on ordinary pushes.

A materially new information source may open a new named research protocol. The next approved information-source program is **SEC EDGAR / XBRL point-in-time fundamentals**.

## AURORA positioning

Current official positioning:

**Primary role:** Portfolio intelligence, risk control, decision discipline and monitoring.

**General stock-selection alpha:** NOT VALIDATED.

**Nasdaq-specific price-only evidence:** SUPPORTIVE BUT UNIVERSE-SPECIFIC, DATA-SOURCE-AMENDED, RESEARCH-ONLY.

## Execution safety

- Live policy changed: **NO**
- Paper order submission authorized: **NO**
- Live broker execution authorized: **NO**
