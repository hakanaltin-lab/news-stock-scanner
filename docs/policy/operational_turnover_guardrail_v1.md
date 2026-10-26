# AURORA Operational Turnover Guardrail v1.0

**Decision date:** 2026-10-26  
**Purpose:** Reduce small, low-value rebalancing churn without creating or optimizing stock-selection alpha.

## Frozen operational rule

A proposed existing-position rebalance trade is suppressed when:

- the trade action is `BUY_TO_TARGET` or `SELL_PARTIAL`, and
- the absolute gap between current portfolio weight and target portfolio weight is **less than 1.00 percentage point**.

The 1.00 pp threshold is an operational round-number tolerance, not the output of a performance optimization.

## Never suppressed by this guardrail

- `SELL_ALL` / full EXIT
- `MANUAL_REVIEW`
- `EVENT_BLOCK`
- trades whose current-vs-target weight gap is at least 1.00 pp

The underlying strategic `portfolio_action` is never changed. Only the operational rebalance instruction may be changed to `NO_TRADE`.

## Existing controls remain

- Whole-share sizing remains unchanged.
- Existing minimum trade-value logic remains unchanged.
- Event-risk controls remain upstream.
- Correlation/capital-allocation controls remain downstream.
- Thesis contradiction remains a separate manual-review signal.
- No broker order is authorized.

## Audit fields

For every rebalancing row, preserve:

- pre-guardrail trade action
- weight gap
- guardrail decision
- reason

Portfolio-level output must report:

- proposed gross trade value before guardrail
- gross trade value after guardrail
- suppressed gross trade value
- estimated one-scan turnover before/after
- suppressed trade count

## Research / governance rule

This guardrail is **not** an alpha factor and must not be tuned against historical CAGR, Sharpe, hit rate, or benchmark outperformance.

Any future threshold change requires a separately documented operational review. Historical performance must not be used to search for the best tolerance band.

## Execution safety

- Live broker execution: BLOCKED
- Paper order submission: BLOCKED
- Strategic policy: unchanged
- Price-only research freeze: unchanged
