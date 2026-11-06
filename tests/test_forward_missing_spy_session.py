"""Regression: missing SPY sessions must not silently shift forward horizons.

This is intentionally a red test documenting the current evaluator defect.
It uses synthetic prices only, never a broker or network.
"""
import unittest
from datetime import date
import pandas as pd
from engines.recommendation_performance_engine import evaluate_record, blank_horizons


class MissingSessionRegression(unittest.TestCase):
    def test_missing_spy_session_does_not_shift_five_day_horizon(self):
        signal = date(2026, 10, 26)  # Monday
        # 27 Oct is an actual weekday session but absent from SPY feed.
        # Five sessions after 26 Oct should be 2 Nov, not 3 Nov.
        dates = [date(2026, 10, 28), date(2026, 10, 29),
                 date(2026, 10, 30), date(2026, 11, 2),
                 date(2026, 11, 3)]
        frame = pd.DataFrame({"SPY": [100, 101, 102, 103, 104],
                              "TEST": [100, 101, 102, 103, 104]}, index=dates)
        record = {"signal_date": signal.isoformat(), "ticker": "TEST",
                  "signal_price": 100, "benchmark_entry_price": 100,
                  "direction": "LONG", "horizons": blank_horizons()}
        result = evaluate_record(record, frame)
        self.assertEqual(result["horizons"]["5d"]["status"], "PENDING",
                         "Missing SPY session must block evaluation, not shift horizon")


if __name__ == "__main__":
    unittest.main()
