"""Regression tests for fail-closed AURORA run-mode behavior.

These tests intentionally do not connect to any broker or place orders.
"""
import os
import unittest
from unittest.mock import patch

from engines.aurora_run_mode_engine import (
    SAFE_OFF, READ_ONLY, DRY_RUN, PAPER_ENABLED,
    load_run_mode, can_transition, restart_state,
)


class RunModeSafetyTests(unittest.TestCase):
    def test_default_is_safe_off(self):
        with patch.dict(os.environ, {}, clear=True):
            state = load_run_mode()
        self.assertEqual(state["mode"], SAFE_OFF)
        self.assertFalse(state["live_execution_allowed"])
        self.assertFalse(state["paper_order_submission_requested"])

    def test_invalid_and_live_modes_fail_closed(self):
        for requested in ("LIVE", "LIVE_REAL_MONEY", "UNKNOWN"):
            with self.subTest(requested=requested):
                with patch.dict(os.environ, {"AURORA_RUN_MODE": requested}):
                    state = load_run_mode()
                self.assertEqual(state["mode"], SAFE_OFF)
                self.assertFalse(state["live_execution_allowed"])

    def test_no_direct_transition_from_safe_off_to_paper(self):
        self.assertFalse(can_transition(SAFE_OFF, PAPER_ENABLED))
        self.assertFalse(can_transition(SAFE_OFF, DRY_RUN))
        self.assertTrue(can_transition(SAFE_OFF, READ_ONLY))

    def test_paper_transition_requires_dry_run(self):
        self.assertFalse(can_transition(READ_ONLY, PAPER_ENABLED))
        self.assertTrue(can_transition(READ_ONLY, DRY_RUN))
        self.assertTrue(can_transition(DRY_RUN, PAPER_ENABLED))

    def test_restart_always_disables_orders(self):
        state = restart_state()
        self.assertEqual(state["mode"], SAFE_OFF)
        self.assertFalse(state["live_execution_allowed"])
        self.assertFalse(state["paper_order_submission_requested"])

    def test_environment_cannot_bypass_paper_transition(self):
        # Safety requirement: environment alone must not arm paper orders.
        # Regression: direct environment selection must remain unarmed.
        with patch.dict(os.environ, {"AURORA_RUN_MODE": PAPER_ENABLED}):
            state = load_run_mode()
        self.assertFalse(state["paper_order_submission_requested"])


if __name__ == "__main__":
    unittest.main()
