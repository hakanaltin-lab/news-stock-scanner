# Forward evidence maturity diagnostic — 2026-11-06

This note is read-only and does not authorize any broker operation.

## Observed source reports
- `docs/recommendation_performance.json`: 189 signals, oldest signal 2026-10-23, newest 2026-10-29.
- 5 trading-day horizon: 189 evaluated, 0 pending; benchmark hit rate 67.2%, mean excess return -0.50%, mean decision alpha -0.33%.
- 20 trading-day horizon: 0 evaluated, 189 pending.
- 60 trading-day horizon: 0 evaluated, 189 pending.
- `docs/fresh_forward_promotion_gate.json`: candidate-specific 100 records pending for each 20d/60d horizon; 0 independent cohorts; verdict `PROMOTION_BLOCKED`.

## Interpretation
The oldest journal signal is dated 2026-10-23. By 2026-11-06, neither a 20- nor a 60-trading-session forward horizon can mature naturally. Pending outcomes are therefore expected, not evidence of a defective evaluator. The 189-record general journal and the 100-record candidate-specific promotion gate use different scopes; do not conflate their denominators.

A 67.2% 5d benchmark hit rate is **not** evidence of positive average excess returns: the reported mean 5d excess return is -0.50%. It also does not satisfy the candidate-specific 20d/60d independent-cohort requirements.

## Follow-up verification
1. When sufficient actual market sessions elapse, check pending→evaluated transitions against an exchange trading calendar, including holidays.
2. Confirm source prices, signal timestamps, benchmark timestamps and future close provenance; no future data at signal creation.
3. Ensure independent cohorts are non-overlapping and never manufactured from multiple tickers on one signal date.
4. Keep automatic promotion, Paper submission and LIVE execution disabled. Do not accelerate maturity by changing clocks, dates, or thresholds.
5. Confirm historical OOS robustness independently: `OOS_MIXED_ROBUSTNESS` is currently a failed guardrail.

No performance or CI test claim is made by this note.
