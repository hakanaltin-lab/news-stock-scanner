"""
V8.4.7 AURORA Fresh Forward Shadow Promotion Gate

Purpose:
- Evaluate only fresh V8.2 shadow journal outcomes for the current shadow
  candidate.
- Require both 20-session and 60-session maturity, breadth across distinct
  signal dates, positive benchmark-relative alpha, and acceptable hit-rate
  confidence before a live-policy review can even be considered.
- Combine fresh evidence with existing historical risk guardrails from
  V8.4.5/V8.4.6.
- Never auto-promote a policy and never authorize broker execution.

No new strategy thresholds are optimized here.
"""

from datetime import datetime, timezone
import json
import math
import os

from engines.recommendation_performance_engine import (
    safe_float
)


ENGINE_VERSION = (
    "V8.4.7 Fresh Forward Shadow Promotion Gate"
)

GATE_SIGNATURE = "V8.4.7"

JOURNAL_FILE = "docs/shadow_policy_journal.json"

OUTPUT_FILE = "docs/fresh_forward_promotion_gate.json"

MIN_20D_EVALUATED = 30

MIN_60D_EVALUATED = 20

MIN_20D_UNIQUE_SIGNAL_DATES = 10

MIN_60D_UNIQUE_SIGNAL_DATES = 8

MIN_20D_HIT_RATE_PCT = 55.0

MIN_60D_HIT_RATE_PCT = 55.0

MIN_20D_AVG_ALPHA_PCT = 0.25

MIN_60D_AVG_ALPHA_PCT = 0.50

MIN_WILSON_LOWER_BOUND_PCT = 45.0

WILSON_Z = 1.6448536269514722

MAX_HISTORICAL_DRAWDOWN_PENALTY_PCT = 5.0


def load_journal():
    if not os.path.exists(
        JOURNAL_FILE
    ):
        return []

    try:
        with open(
            JOURNAL_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(
                file
            )

        records = data.get(
            "records",
            []
        )

        return (
            records
            if isinstance(
                records,
                list
            )
            else []
        )

    except Exception:
        return []


def save_result(data):
    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def wilson_lower_bound_pct(
    hits,
    total
):
    if total <= 0:
        return None

    p = (
        hits
        /
        total
    )

    z2 = (
        WILSON_Z
        *
        WILSON_Z
    )

    denominator = (
        1.0
        +
        z2
        /
        total
    )

    center = (
        p
        +
        z2
        /
        (
            2.0
            *
            total
        )
    )

    margin = (
        WILSON_Z
        *
        math.sqrt(
            (
                p
                *
                (
                    1.0
                    -
                    p
                )
                +
                z2
                /
                (
                    4.0
                    *
                    total
                )
            )
            /
            total
        )
    )

    lower = (
        center
        -
        margin
    ) / denominator

    return round(
        max(
            0.0,
            lower
        )
        *
        100,
        1
    )


def summarize_horizon(
    records,
    horizon
):
    evaluated = []

    pending = 0

    for record in records:
        horizon_data = (
            (
                record.get(
                    "horizons",
                    {}
                )
                or
                {}
            ).get(
                horizon,
                {}
            )
            or
            {}
        )

        if (
            horizon_data.get(
                "status"
            )
            ==
            "EVALUATED"
        ):
            evaluated.append({
                "record":
                record,

                "horizon":
                horizon_data
            })

        else:
            pending += 1

    hits = sum(
        1
        for item in evaluated
        if (
            item[
                "horizon"
            ].get(
                "shadow_hit"
            )
            is True
        )
    )

    alpha_values = [
        safe_float(
            item[
                "horizon"
            ].get(
                "shadow_relative_alpha_pct"
            ),
            0.0
        )
        for item in evaluated
        if (
            item[
                "horizon"
            ].get(
                "shadow_relative_alpha_pct"
            )
            is not None
        )
    ]

    unique_signal_dates = sorted(
        set(
            str(
                item[
                    "record"
                ].get(
                    "signal_date"
                )
            )
            for item in evaluated
            if item[
                "record"
            ].get(
                "signal_date"
            )
        )
    )

    unique_tickers = sorted(
        set(
            str(
                item[
                    "record"
                ].get(
                    "ticker"
                )
            )
            for item in evaluated
            if item[
                "record"
            ].get(
                "ticker"
            )
        )
    )

    hit_rate = (
        hits
        /
        len(
            evaluated
        )
        *
        100
        if evaluated
        else None
    )

    average_alpha = (
        sum(
            alpha_values
        )
        /
        len(
            alpha_values
        )
        if alpha_values
        else None
    )

    sorted_alpha = sorted(
        alpha_values
    )

    median_alpha = None

    if sorted_alpha:
        middle = len(
            sorted_alpha
        ) // 2

        if (
            len(
                sorted_alpha
            )
            %
            2
        ):
            median_alpha = (
                sorted_alpha[
                    middle
                ]
            )

        else:
            median_alpha = (
                sorted_alpha[
                    middle
                    -
                    1
                ]
                +
                sorted_alpha[
                    middle
                ]
            ) / 2.0

    return {
        "evaluated":
        len(
            evaluated
        ),

        "pending":
        pending,

        "unique_signal_dates":
        len(
            unique_signal_dates
        ),

        "unique_tickers":
        len(
            unique_tickers
        ),

        "first_signal_date":
        (
            unique_signal_dates[
                0
            ]
            if unique_signal_dates
            else None
        ),

        "last_signal_date":
        (
            unique_signal_dates[
                -1
            ]
            if unique_signal_dates
            else None
        ),

        "hits":
        hits,

        "hit_rate_pct":
        (
            round(
                hit_rate,
                1
            )
            if hit_rate is not None
            else None
        ),

        "wilson_lower_bound_90_pct":
        wilson_lower_bound_pct(
            hits,
            len(
                evaluated
            )
        ),

        "average_shadow_relative_alpha_pct":
        (
            round(
                average_alpha,
                3
            )
            if average_alpha is not None
            else None
        ),

        "median_shadow_relative_alpha_pct":
        (
            round(
                median_alpha,
                3
            )
            if median_alpha is not None
            else None
        )
    }


def metric_pass(
    value,
    threshold
):
    if value is None:
        return False

    return (
        safe_float(
            value,
            -999999.0
        )
        >=
        threshold
    )


def build_horizon_checks(
    summary,
    min_evaluated,
    min_unique_dates,
    min_hit_rate,
    min_avg_alpha
):
    return {
        "evaluated_sample":
        {
            "required":
            min_evaluated,

            "actual":
            summary.get(
                "evaluated"
            ),

            "passed":
            safe_float(
                summary.get(
                    "evaluated"
                ),
                0.0
            )
            >=
            min_evaluated
        },

        "distinct_signal_dates":
        {
            "required":
            min_unique_dates,

            "actual":
            summary.get(
                "unique_signal_dates"
            ),

            "passed":
            safe_float(
                summary.get(
                    "unique_signal_dates"
                ),
                0.0
            )
            >=
            min_unique_dates
        },

        "hit_rate_pct":
        {
            "required":
            min_hit_rate,

            "actual":
            summary.get(
                "hit_rate_pct"
            ),

            "passed":
            metric_pass(
                summary.get(
                    "hit_rate_pct"
                ),
                min_hit_rate
            )
        },

        "wilson_lower_bound_90_pct":
        {
            "required":
            MIN_WILSON_LOWER_BOUND_PCT,

            "actual":
            summary.get(
                "wilson_lower_bound_90_pct"
            ),

            "passed":
            metric_pass(
                summary.get(
                    "wilson_lower_bound_90_pct"
                ),
                MIN_WILSON_LOWER_BOUND_PCT
            )
        },

        "average_shadow_relative_alpha_pct":
        {
            "required":
            min_avg_alpha,

            "actual":
            summary.get(
                "average_shadow_relative_alpha_pct"
            ),

            "passed":
            metric_pass(
                summary.get(
                    "average_shadow_relative_alpha_pct"
                ),
                min_avg_alpha
            )
        },

        "median_shadow_relative_alpha_positive":
        {
            "required":
            "> 0",

            "actual":
            summary.get(
                "median_shadow_relative_alpha_pct"
            ),

            "passed":
            (
                safe_float(
                    summary.get(
                        "median_shadow_relative_alpha_pct"
                    ),
                    0.0
                )
                >
                0
            )
        }
    }


def checks_pass(
    checks
):
    return all(
        item.get(
            "passed"
        )
        is True
        for item in checks.values()
    )


def run_fresh_forward_promotion_gate(
    calibration_result,
    shadow_monitor_result,
    walk_forward_result,
    regime_failure_result
):
    calibration_result = (
        calibration_result
        or
        {}
    )

    shadow_monitor_result = (
        shadow_monitor_result
        or
        {}
    )

    walk_forward_result = (
        walk_forward_result
        or
        {}
    )

    regime_failure_result = (
        regime_failure_result
        or
        {}
    )

    candidate_policy = (
        shadow_monitor_result.get(
            "candidate_policy"
        )
        or
        calibration_result.get(
            "shadow_candidate_policy"
        )
    )

    journal_records = load_journal()

    candidate_records = [
        record
        for record in journal_records
        if (
            candidate_policy
            and
            record.get(
                "candidate_policy"
            )
            ==
            candidate_policy
        )
    ]

    summary_20d = summarize_horizon(
        candidate_records,
        "20d"
    )

    summary_60d = summarize_horizon(
        candidate_records,
        "60d"
    )

    checks_20d = build_horizon_checks(
        summary_20d,
        MIN_20D_EVALUATED,
        MIN_20D_UNIQUE_SIGNAL_DATES,
        MIN_20D_HIT_RATE_PCT,
        MIN_20D_AVG_ALPHA_PCT
    )

    checks_60d = build_horizon_checks(
        summary_60d,
        MIN_60D_EVALUATED,
        MIN_60D_UNIQUE_SIGNAL_DATES,
        MIN_60D_HIT_RATE_PCT,
        MIN_60D_AVG_ALPHA_PCT
    )

    historical_shadow = (
        regime_failure_result.get(
            "overall_shadow_vs_default",
            {}
        )
        or
        {}
    )

    historical_drawdown_advantage = safe_float(
        historical_shadow.get(
            "shadow_drawdown_advantage_pct"
        ),
        0.0
    )

    historical_drawdown_penalty = max(
        0.0,
        -
        historical_drawdown_advantage
    )

    robustness_verdict = (
        (
            walk_forward_result.get(
                "oos_statistical_robustness",
                {}
            )
            or
            {}
        ).get(
            "verdict"
        )
    )

    calibration_verdict = (
        (
            calibration_result.get(
                "promotion_verdict",
                {}
            )
            or
            {}
        ).get(
            "status"
        )
    )

    historical_guardrails = {
        "calibration_candidate_active":
        {
            "required":
            "SHADOW_CANDIDATE or PROMOTE_CANDIDATE",

            "actual":
            calibration_verdict,

            "passed":
            calibration_verdict
            in [
                "SHADOW_CANDIDATE",
                "PROMOTE_CANDIDATE"
            ]
        },

        "oos_robustness_supportive":
        {
            "required":
            "OOS_SUPPORTIVE_WITH_CAVEATS or OOS_ROBUST_SUPPORTIVE",

            "actual":
            robustness_verdict,

            "passed":
            robustness_verdict
            in [
                "OOS_SUPPORTIVE_WITH_CAVEATS",
                "OOS_ROBUST_SUPPORTIVE"
            ]
        },

        "weak_regime_repair":
        {
            "required":
            "2/2",

            "actual":
            (
                f"{regime_failure_result.get('failing_regimes_repaired', 0)}"
                f"/{regime_failure_result.get('failing_regimes_total', 2)}"
            ),

            "passed":
            (
                regime_failure_result.get(
                    "failing_regimes_repaired"
                )
                ==
                regime_failure_result.get(
                    "failing_regimes_total"
                )
                and
                safe_float(
                    regime_failure_result.get(
                        "failing_regimes_total"
                    ),
                    0.0
                )
                >
                0
            )
        },

        "historical_drawdown_penalty_pct":
        {
            "required":
            f"<= {MAX_HISTORICAL_DRAWDOWN_PENALTY_PCT}",

            "actual":
            round(
                historical_drawdown_penalty,
                2
            ),

            "passed":
            historical_drawdown_penalty
            <=
            MAX_HISTORICAL_DRAWDOWN_PENALTY_PCT
        },

        "live_execution_still_blocked":
        {
            "required":
            True,

            "actual":
            False,

            "passed":
            True
        }
    }

    fresh_maturity_ready = (
        summary_20d.get(
            "evaluated",
            0
        )
        >=
        MIN_20D_EVALUATED
        and
        summary_60d.get(
            "evaluated",
            0
        )
        >=
        MIN_60D_EVALUATED
        and
        summary_20d.get(
            "unique_signal_dates",
            0
        )
        >=
        MIN_20D_UNIQUE_SIGNAL_DATES
        and
        summary_60d.get(
            "unique_signal_dates",
            0
        )
        >=
        MIN_60D_UNIQUE_SIGNAL_DATES
    )

    historical_ready = checks_pass(
        historical_guardrails
    )

    fresh_20d_pass = checks_pass(
        checks_20d
    )

    fresh_60d_pass = checks_pass(
        checks_60d
    )

    if not candidate_policy:
        status = (
            "NO_ACTIVE_SHADOW_CANDIDATE"
        )

        verdict = (
            "PROMOTION_BLOCKED"
        )

    elif not fresh_maturity_ready:
        status = (
            "WAITING_FOR_FRESH_EVIDENCE"
        )

        verdict = (
            "PROMOTION_BLOCKED"
        )

    elif (
        not historical_ready
        or
        not fresh_20d_pass
        or
        not fresh_60d_pass
    ):
        status = (
            "FRESH_EVIDENCE_GATE_FAILED"
        )

        verdict = (
            "PROMOTION_BLOCKED"
        )

    else:
        status = (
            "REVIEW_ELIGIBLE"
        )

        verdict = (
            "MANUAL_LIVE_POLICY_REVIEW_CANDIDATE"
        )

    maturity = {
        "20d_evaluated_needed":
        max(
            0,
            MIN_20D_EVALUATED
            -
            summary_20d.get(
                "evaluated",
                0
            )
        ),

        "60d_evaluated_needed":
        max(
            0,
            MIN_60D_EVALUATED
            -
            summary_60d.get(
                "evaluated",
                0
            )
        ),

        "20d_unique_signal_dates_needed":
        max(
            0,
            MIN_20D_UNIQUE_SIGNAL_DATES
            -
            summary_20d.get(
                "unique_signal_dates",
                0
            )
        ),

        "60d_unique_signal_dates_needed":
        max(
            0,
            MIN_60D_UNIQUE_SIGNAL_DATES
            -
            summary_60d.get(
                "unique_signal_dates",
                0
            )
        )
    }

    result = {
        "engine":
        ENGINE_VERSION,

        "gate_signature":
        GATE_SIGNATURE,

        "generated":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "status":
        status,

        "verdict":
        verdict,

        "candidate_policy":
        candidate_policy,

        "journal_records_total":
        len(
            journal_records
        ),

        "candidate_records_total":
        len(
            candidate_records
        ),

        "fresh_forward_only":
        True,

        "automatic_live_promotion":
        False,

        "manual_live_policy_review_required":
        True,

        "live_policy_changed":
        False,

        "live_execution_authorized":
        False,

        "paper_order_submission_authorized":
        False,

        "fresh_evidence": {
            "20d":
            summary_20d,

            "60d":
            summary_60d
        },

        "fresh_gate_checks": {
            "20d":
            checks_20d,

            "60d":
            checks_60d
        },

        "historical_guardrails":
        historical_guardrails,

        "maturity_progress":
        maturity,

        "thresholds": {
            "min_20d_evaluated":
            MIN_20D_EVALUATED,

            "min_60d_evaluated":
            MIN_60D_EVALUATED,

            "min_20d_unique_signal_dates":
            MIN_20D_UNIQUE_SIGNAL_DATES,

            "min_60d_unique_signal_dates":
            MIN_60D_UNIQUE_SIGNAL_DATES,

            "min_20d_hit_rate_pct":
            MIN_20D_HIT_RATE_PCT,

            "min_60d_hit_rate_pct":
            MIN_60D_HIT_RATE_PCT,

            "min_20d_average_shadow_alpha_pct":
            MIN_20D_AVG_ALPHA_PCT,

            "min_60d_average_shadow_alpha_pct":
            MIN_60D_AVG_ALPHA_PCT,

            "min_wilson_lower_bound_90_pct":
            MIN_WILSON_LOWER_BOUND_PCT,

            "max_historical_drawdown_penalty_pct":
            MAX_HISTORICAL_DRAWDOWN_PENALTY_PCT
        },

        "methodology_note":
        (
            "Promotion eligibility uses only fresh V8.2 journal outcomes for "
            "the current candidate. Both 20D and 60D horizons must mature, "
            "with breadth across distinct signal dates and a 90% Wilson "
            "lower-bound guardrail. Historical evidence is used only as a "
            "risk/supporting gate, never to manufacture fresh forward wins."
        ),

        "decision_note":
        (
            "Even REVIEW_ELIGIBLE does not change V7.9 automatically. It only "
            "permits a separate manual live-policy review. Broker execution "
            "remains blocked."
        )
    }

    save_result(
        result
    )

    return result
