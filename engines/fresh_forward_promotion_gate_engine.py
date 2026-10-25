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
    "V8.4.8 Independent-Cohort Fresh Forward Promotion Gate"
)

GATE_SIGNATURE = "V8.4.8"

JOURNAL_FILE = "docs/shadow_policy_journal.json"

OUTPUT_FILE = "docs/fresh_forward_promotion_gate.json"

MIN_20D_INDEPENDENT_COHORTS = 6

MIN_60D_INDEPENDENT_COHORTS = 6

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


def parse_iso_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(
                value
            ).replace(
                "Z",
                "+00:00"
            )
        ).date()

    except Exception:
        try:
            return datetime.strptime(
                str(
                    value
                )[:10],
                "%Y-%m-%d"
            ).date()

        except Exception:
            return None


def median_value(values):
    clean = sorted(
        safe_float(
            value,
            0.0
        )
        for value in values
    )

    if not clean:
        return None

    middle = len(
        clean
    ) // 2

    if len(
        clean
    ) % 2:
        return clean[
            middle
        ]

    return (
        clean[
            middle
            -
            1
        ]
        +
        clean[
            middle
        ]
    ) / 2.0


def summarize_horizon(
    records,
    horizon
):
    evaluated_records = []
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
            and
            horizon_data.get(
                "shadow_relative_alpha_pct"
            )
            is not None
        ):
            evaluated_records.append({
                "record":
                record,

                "horizon":
                horizon_data
            })

        else:
            pending += 1

    raw_alpha_values = [
        safe_float(
            item[
                "horizon"
            ].get(
                "shadow_relative_alpha_pct"
            ),
            0.0
        )
        for item in evaluated_records
    ]

    raw_hits = sum(
        1
        for item in evaluated_records
        if item[
            "horizon"
        ].get(
            "shadow_hit"
        )
        is True
    )

    by_signal_date = {}

    for item in evaluated_records:
        signal_date = str(
            item[
                "record"
            ].get(
                "signal_date"
                or
                ""
            )
        )

        if not signal_date:
            continue

        by_signal_date.setdefault(
            signal_date,
            []
        ).append(
            item
        )

    candidate_cohorts = []

    for signal_date in sorted(
        by_signal_date
    ):
        items = by_signal_date[
            signal_date
        ]

        alphas = [
            safe_float(
                item[
                    "horizon"
                ].get(
                    "shadow_relative_alpha_pct"
                ),
                0.0
            )
            for item in items
        ]

        tickers = sorted(
            set(
                str(
                    item[
                        "record"
                    ].get(
                        "ticker"
                    )
                )
                for item in items
                if item[
                    "record"
                ].get(
                    "ticker"
                )
            )
        )

        evaluation_dates = [
            parse_iso_date(
                item[
                    "horizon"
                ].get(
                    "evaluation_date"
                )
            )
            for item in items
        ]

        evaluation_dates = [
            item
            for item in evaluation_dates
            if item is not None
        ]

        signal_date_value = parse_iso_date(
            signal_date
        )

        if (
            signal_date_value is None
            or
            not evaluation_dates
        ):
            continue

        cohort_alpha = (
            sum(
                alphas
            )
            /
            len(
                alphas
            )
            if alphas
            else 0.0
        )

        candidate_cohorts.append({
            "signal_date":
            signal_date,

            "signal_date_value":
            signal_date_value,

            "evaluation_date":
            max(
                evaluation_dates
            ).isoformat(),

            "evaluation_date_value":
            max(
                evaluation_dates
            ),

            "ticker_count":
            len(
                tickers
            ),

            "tickers":
            tickers,

            "mean_shadow_relative_alpha_pct":
            round(
                cohort_alpha,
                3
            ),

            "median_shadow_relative_alpha_pct":
            round(
                safe_float(
                    median_value(
                        alphas
                    ),
                    0.0
                ),
                3
            ),

            "cohort_hit":
            cohort_alpha
            >
            0
        })

    # Independence rule: after accepting a cohort, the next accepted cohort
    # must start strictly after the previous cohort's forward evaluation date.
    independent_cohorts = []

    previous_evaluation_date = None

    for cohort in candidate_cohorts:
        signal_date_value = cohort[
            "signal_date_value"
        ]

        if (
            previous_evaluation_date is not None
            and
            signal_date_value
            <=
            previous_evaluation_date
        ):
            continue

        independent_cohorts.append(
            cohort
        )

        previous_evaluation_date = cohort[
            "evaluation_date_value"
        ]

    independent_alpha_values = [
        safe_float(
            cohort.get(
                "mean_shadow_relative_alpha_pct"
            ),
            0.0
        )
        for cohort in independent_cohorts
    ]

    independent_hits = sum(
        1
        for cohort in independent_cohorts
        if cohort.get(
            "cohort_hit"
        )
        is True
    )

    unique_tickers = sorted(
        set(
            ticker
            for cohort in independent_cohorts
            for ticker in cohort.get(
                "tickers",
                []
            )
        )
    )

    hit_rate = (
        independent_hits
        /
        len(
            independent_cohorts
        )
        *
        100
        if independent_cohorts
        else None
    )

    average_alpha = (
        sum(
            independent_alpha_values
        )
        /
        len(
            independent_alpha_values
        )
        if independent_alpha_values
        else None
    )

    median_alpha = median_value(
        independent_alpha_values
    )

    serializable_cohorts = []

    for cohort in independent_cohorts:
        serializable_cohorts.append({
            key:
            value
            for key, value in cohort.items()
            if key
            not in {
                "signal_date_value",
                "evaluation_date_value"
            }
        })

    return {
        "raw_evaluated_records":
        len(
            evaluated_records
        ),

        "raw_pending_records":
        pending,

        "raw_hit_rate_pct":
        (
            round(
                raw_hits
                /
                len(
                    evaluated_records
                )
                *
                100,
                1
            )
            if evaluated_records
            else None
        ),

        "raw_average_shadow_relative_alpha_pct":
        (
            round(
                sum(
                    raw_alpha_values
                )
                /
                len(
                    raw_alpha_values
                ),
                3
            )
            if raw_alpha_values
            else None
        ),

        "candidate_signal_date_cohorts":
        len(
            candidate_cohorts
        ),

        "independent_cohorts":
        len(
            independent_cohorts
        ),

        "independent_hits":
        independent_hits,

        "independent_hit_rate_pct":
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
            independent_hits,
            len(
                independent_cohorts
            )
        ),

        "average_cohort_shadow_alpha_pct":
        (
            round(
                average_alpha,
                3
            )
            if average_alpha is not None
            else None
        ),

        "median_cohort_shadow_alpha_pct":
        (
            round(
                median_alpha,
                3
            )
            if median_alpha is not None
            else None
        ),

        "unique_tickers_across_independent_cohorts":
        len(
            unique_tickers
        ),

        "first_independent_signal_date":
        (
            independent_cohorts[
                0
            ][
                "signal_date"
            ]
            if independent_cohorts
            else None
        ),

        "last_independent_signal_date":
        (
            independent_cohorts[
                -1
            ][
                "signal_date"
            ]
            if independent_cohorts
            else None
        ),

        "cohorts":
        serializable_cohorts,

        "independence_rule":
        (
            "Next cohort signal date must be strictly after the prior "
            "selected cohort evaluation date."
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
    min_independent_cohorts,
    min_hit_rate,
    min_avg_alpha
):
    return {
        "independent_cohorts":
        {
            "required":
            min_independent_cohorts,

            "actual":
            summary.get(
                "independent_cohorts"
            ),

            "passed":
            safe_float(
                summary.get(
                    "independent_cohorts"
                ),
                0.0
            )
            >=
            min_independent_cohorts
        },

        "cohort_hit_rate_pct":
        {
            "required":
            min_hit_rate,

            "actual":
            summary.get(
                "independent_hit_rate_pct"
            ),

            "passed":
            metric_pass(
                summary.get(
                    "independent_hit_rate_pct"
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

        "average_cohort_shadow_alpha_pct":
        {
            "required":
            min_avg_alpha,

            "actual":
            summary.get(
                "average_cohort_shadow_alpha_pct"
            ),

            "passed":
            metric_pass(
                summary.get(
                    "average_cohort_shadow_alpha_pct"
                ),
                min_avg_alpha
            )
        },

        "median_cohort_shadow_alpha_positive":
        {
            "required":
            "> 0",

            "actual":
            summary.get(
                "median_cohort_shadow_alpha_pct"
            ),

            "passed":
            (
                safe_float(
                    summary.get(
                        "median_cohort_shadow_alpha_pct"
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
        MIN_20D_INDEPENDENT_COHORTS,
        MIN_20D_HIT_RATE_PCT,
        MIN_20D_AVG_ALPHA_PCT
    )

    checks_60d = build_horizon_checks(
        summary_60d,
        MIN_60D_INDEPENDENT_COHORTS,
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
            "BLOCKED",

            "actual":
            "BLOCKED",

            "passed":
            True
        }
    }

    fresh_maturity_ready = (
        summary_20d.get(
            "independent_cohorts",
            0
        )
        >=
        MIN_20D_INDEPENDENT_COHORTS
        and
        summary_60d.get(
            "independent_cohorts",
            0
        )
        >=
        MIN_60D_INDEPENDENT_COHORTS
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
        "20d_independent_cohorts_needed":
        max(
            0,
            MIN_20D_INDEPENDENT_COHORTS
            -
            summary_20d.get(
                "independent_cohorts",
                0
            )
        ),

        "60d_independent_cohorts_needed":
        max(
            0,
            MIN_60D_INDEPENDENT_COHORTS
            -
            summary_60d.get(
                "independent_cohorts",
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
            "min_20d_independent_cohorts":
            MIN_20D_INDEPENDENT_COHORTS,

            "min_60d_independent_cohorts":
            MIN_60D_INDEPENDENT_COHORTS,

            "min_20d_cohort_hit_rate_pct":
            MIN_20D_HIT_RATE_PCT,

            "min_60d_cohort_hit_rate_pct":
            MIN_60D_HIT_RATE_PCT,

            "min_20d_average_cohort_shadow_alpha_pct":
            MIN_20D_AVG_ALPHA_PCT,

            "min_60d_average_cohort_shadow_alpha_pct":
            MIN_60D_AVG_ALPHA_PCT,

            "min_wilson_lower_bound_90_pct":
            MIN_WILSON_LOWER_BOUND_PCT,

            "max_historical_drawdown_penalty_pct":
            MAX_HISTORICAL_DRAWDOWN_PENALTY_PCT
        },

        "methodology_note":
        (
            "Promotion eligibility uses only fresh V8.2 journal outcomes for "
            "the current candidate. Raw ticker records are grouped by signal "
            "date, then filtered into non-overlapping forward time cohorts. "
            "Wilson confidence is calculated on independent cohort hits, not "
            "ticker records. Historical evidence is only a risk/supporting "
            "gate and never manufactures fresh forward wins."
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
