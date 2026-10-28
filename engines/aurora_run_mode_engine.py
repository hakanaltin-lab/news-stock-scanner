"""AURORA V8.9.5 fail-closed run-mode controller.

There is intentionally no LIVE mode in this state machine.
A process restart must begin in SAFE_OFF.
"""

import os


SAFE_OFF = "SAFE_OFF"
READ_ONLY = "READ_ONLY"
DRY_RUN = "DRY_RUN"
PAPER_ENABLED = "PAPER_ENABLED"

VALID_RUN_MODES = {
    SAFE_OFF,
    READ_ONLY,
    DRY_RUN,
    PAPER_ENABLED,
}

_ALLOWED_TRANSITIONS = {
    SAFE_OFF: {SAFE_OFF, READ_ONLY},
    READ_ONLY: {SAFE_OFF, READ_ONLY, DRY_RUN},
    DRY_RUN: {SAFE_OFF, READ_ONLY, DRY_RUN, PAPER_ENABLED},
    PAPER_ENABLED: {SAFE_OFF, DRY_RUN, PAPER_ENABLED},
}


def load_run_mode():
    requested = os.getenv("AURORA_RUN_MODE", SAFE_OFF).strip().upper()
    valid = requested in VALID_RUN_MODES
    effective = requested if valid else SAFE_OFF

    return {
        "requested_mode": requested,
        "mode": effective,
        "mode_valid": valid,
        "live_execution_allowed": False,
        "paper_order_submission_requested": effective == PAPER_ENABLED,
        "dry_run": effective == DRY_RUN,
        "read_only": effective == READ_ONLY,
        "safe_off": effective == SAFE_OFF,
    }


def can_transition(current_mode, target_mode):
    current = str(current_mode or SAFE_OFF).strip().upper()
    target = str(target_mode or SAFE_OFF).strip().upper()

    if current not in VALID_RUN_MODES or target not in VALID_RUN_MODES:
        return False

    return target in _ALLOWED_TRANSITIONS[current]


def restart_state():
    return {
        "mode": SAFE_OFF,
        "live_execution_allowed": False,
        "paper_order_submission_requested": False,
        "reason": "PROCESS_RESTART_FAIL_CLOSED",
    }
