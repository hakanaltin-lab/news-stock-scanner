# Forward evaluation engine audit — 2026-11-06

Scope: read-only review of `engines/recommendation_performance_engine.py`, especially `get_close_frame()` and `evaluate_record()`.

## Confirmed behavior

- The evaluator counts future dates from the SPY daily-close series, rather than calendar days.
- It chooses the SPY date at the Nth available future row as the horizon date.
- It requires a stock close on that exact date; absent stock or SPY prices leave the horizon pending.
- Completed horizons are skipped on subsequent passes.

## Open correctness risks (not resolved by the current test PR)

1. **Missing SPY trading session:** If Yahoo omits a valid US market session, the Nth *available* SPY row can occur later than the Nth actual exchange session. This creates delayed or misaligned forward evaluation. The current engine does not compare SPY rows to an authoritative exchange calendar.
2. **Incomplete current-day bar:** A daily bar may appear before its trading session is finalized. The evaluator does not explicitly verify exchange-close finality or data-provider freshness before accepting it.
3. **Missing ticker close:** The evaluator correctly declines to use a nonmatching stock date, but it cannot distinguish an exchange halt from a provider data gap without a separate quality signal.
4. **Timezone normalization:** `get_close_frame()` converts downloaded index timestamps to dates. A provider/index timezone change could shift the trading-date label unless normalized to the exchange timezone.

## Recommended fail-closed production follow-up

- Supply an authoritative NYSE session calendar for each evaluated horizon.
- Check the SPY index against that calendar and mark missing required sessions as DATA_GAP, rather than treating a shorter price series as a complete trading calendar.
- Require a finalized daily bar after exchange close and a bounded provider-data freshness lag.
- Normalize all bar timestamps to America/New_York trading dates before extracting dates.
- Add isolated production-function tests with synthetic bars for missing SPY sessions, stale/intraday bars, stock gaps, holidays and daylight-saving transitions.

## Scope of this PR

The current PR adds **read-only offline tests and diagnostics only**. It does not alter the evaluator, broker connectivity, order permissions, live/paper authorization, or existing report values. The new calendar helper is a test oracle, not the production exchange calendar. Passing CI is **not** evidence that these open production risks are fixed.
