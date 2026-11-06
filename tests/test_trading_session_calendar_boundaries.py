"""Offline trading-session calendar boundary tests.

A calendar function is deliberately pure: no broker, market-data API or wall clock.
Holidays must be supplied by the caller; weekends alone are insufficient for NYSE.
"""
from datetime import date, timedelta
import unittest


def nth_trading_session_after(signal_date, sessions, holidays=()):
    """Return the Nth later weekday excluding supplied exchange holidays."""
    if sessions < 1:
        raise ValueError("sessions must be positive")
    holiday_set = set(holidays)
    day = signal_date
    count = 0
    while count < sessions:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in holiday_set:
            count += 1
    return day


def is_mature(signal_date, as_of_date, sessions, holidays=()):
    return as_of_date >= nth_trading_session_after(signal_date, sessions, holidays)


class TradingSessionCalendarTests(unittest.TestCase):
    def test_weekend_is_not_a_session(self):
        self.assertEqual(
            nth_trading_session_after(date(2026, 11, 6), 1),
            date(2026, 11, 9),
        )

    def test_explicit_exchange_holiday_is_skipped(self):
        self.assertEqual(
            nth_trading_session_after(
                date(2026, 11, 25), 1, {date(2026, 11, 26)}
            ),
            date(2026, 11, 27),
        )

    def test_pending_until_full_horizon(self):
        signal = date(2026, 10, 23)
        self.assertFalse(is_mature(signal, date(2026, 11, 6), 20))
        self.assertFalse(is_mature(signal, date(2026, 11, 6), 60))

    def test_maturity_boundary_is_inclusive(self):
        signal = date(2026, 10, 23)
        due = nth_trading_session_after(signal, 5)
        self.assertFalse(is_mature(signal, due - timedelta(days=1), 5))
        self.assertTrue(is_mature(signal, due, 5))

    def test_reject_zero_or_negative_horizon(self):
        for sessions in (0, -1):
            with self.subTest(sessions=sessions):
                with self.assertRaises(ValueError):
                    nth_trading_session_after(date(2026, 11, 6), sessions)


if __name__ == "__main__":
    unittest.main()
