"""Read-only integrity checks for published forward journal evidence."""
import json
from pathlib import Path
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1] / "docs"
JOURNAL = ROOT / "recommendation_journal.json"
SUMMARY = ROOT / "recommendation_performance.json"


def inspect_record(record):
    """Return reasons a published observation is internally inconsistent."""
    problems = []
    signal_date = date.fromisoformat(record["signal_date"])
    for horizon, outcome in record["horizons"].items():
        status = outcome["status"]
        if outcome["target_trading_sessions"] != int(horizon[:-1]):
            problems.append(f"{horizon}: horizon/session mismatch")
        if status == "PENDING":
            if any(outcome.get(k) is not None for k in (
                "evaluation_date", "future_price", "future_spy_price",
                "stock_return_pct", "spy_return_pct", "excess_return_pct",
                "decision_alpha_pct", "benchmark_hit", "absolute_hit",
            )):
                problems.append(f"{horizon}: pending record contains future outcome")
        elif status == "EVALUATED":
            if outcome["evaluation_date"] is None or (
                date.fromisoformat(outcome["evaluation_date"]) <= signal_date
            ):
                problems.append(f"{horizon}: non-future evaluation date")
            if outcome["future_price"] is None or outcome["future_spy_price"] is None:
                problems.append(f"{horizon}: missing future prices")
        else:
            problems.append(f"{horizon}: unknown status {status}")
    return problems


class ForwardJournalIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
        cls.summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    def test_record_count_matches_summary(self):
        self.assertEqual(len(self.journal["records"]), self.summary["total_signals"])

    def test_horizon_counts_match_summary(self):
        records = self.journal["records"]
        for horizon in ("5d", "20d", "60d"):
            outcomes = [record["horizons"][horizon]["status"] for record in records]
            published = self.summary["horizons"][horizon]
            self.assertEqual(outcomes.count("EVALUATED"), published["evaluated"])
            self.assertEqual(outcomes.count("PENDING"), published["pending"])

    def test_no_pending_future_data_or_nonfuture_evaluations(self):
        for record in self.journal["records"]:
            with self.subTest(id=record["id"]):
                self.assertEqual(inspect_record(record), [])

    def test_synthetic_future_data_leak_is_rejected(self):
        record = json.loads(json.dumps(self.journal["records"][0]))
        record["horizons"]["20d"]["future_price"] = 999.0
        self.assertIn("20d: pending record contains future outcome", inspect_record(record))

    def test_synthetic_lookahead_date_is_rejected(self):
        record = json.loads(json.dumps(self.journal["records"][0]))
        record["horizons"]["5d"]["evaluation_date"] = record["signal_date"]
        self.assertIn("5d: non-future evaluation date", inspect_record(record))


if __name__ == "__main__":
    unittest.main()
