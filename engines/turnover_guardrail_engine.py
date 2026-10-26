"""
AURORA Operational Turnover Guardrail v1.0

Suppresses only small partial rebalance trades inside a fixed 1.00 percentage
point target-weight tolerance band. Strategic portfolio actions are preserved.
Full exits are never suppressed. No broker order is authorized.
"""

import copy

from engines.position_sizing_engine import (
    calculate_theme_exposure,
    safe_float,
    THEME_CONCENTRATION_LIMIT
)


ENGINE_VERSION = "V8.9 Operational Turnover Guardrail"
SIGNATURE = "V8.9.0"
POLICY_FILE = "docs/policy/operational_turnover_guardrail_v1.md"

MIN_TARGET_WEIGHT_GAP_PCT = 1.0


def _gross_trade_value(
    plans
):
    return sum(
        abs(
            safe_float(
                plan.get(
                    "suggested_trade_value",
                    0.0
                ),
                0.0
            )
        )
        for plan in (
            plans
            or
            []
        )
        if plan.get(
            "trade_action"
        )
        in {
            "SELL_ALL",
            "SELL_PARTIAL",
            "BUY_TO_TARGET"
        }
    )


def _recalculate(
    adjusted,
    portfolio_results
):
    plans = (
        adjusted.get(
            "rebalancing_plan",
            []
        )
        or
        []
    )

    total_sell_value = sum(
        safe_float(
            plan.get(
                "suggested_trade_value",
                0.0
            ),
            0.0
        )
        for plan in plans
        if plan.get(
            "trade_action"
        )
        in {
            "SELL_ALL",
            "SELL_PARTIAL"
        }
    )

    total_buy_value = sum(
        safe_float(
            plan.get(
                "suggested_trade_value",
                0.0
            ),
            0.0
        )
        for plan in plans
        if plan.get(
            "trade_action"
        )
        ==
        "BUY_TO_TARGET"
    )

    adjusted[
        "estimated_sell_proceeds"
    ] = round(
        total_sell_value,
        2
    )

    adjusted[
        "estimated_buy_requirement"
    ] = round(
        total_buy_value,
        2
    )

    adjusted[
        "estimated_net_cash_generated"
    ] = round(
        total_sell_value
        -
        total_buy_value,
        2
    )

    portfolio_value = safe_float(
        adjusted.get(
            "portfolio_value",
            0.0
        ),
        0.0
    )

    plan_lookup = {
        plan.get(
            "ticker"
        ):
        plan
        for plan in plans
    }

    projected_theme_exposure = (
        calculate_theme_exposure(
            portfolio_results,
            portfolio_value,
            plan_lookup=plan_lookup
        )
    )

    adjusted[
        "projected_theme_exposure"
    ] = projected_theme_exposure

    concentration_alerts = []

    for theme, data in (
        projected_theme_exposure.items()
    ):
        if (
            data.get(
                "concentration_status"
            )
            ==
            "HIGH"
        ):
            concentration_alerts.append({
                "theme":
                theme,

                "projected_weight_pct":
                data.get(
                    "weight_pct"
                ),

                "limit_pct":
                THEME_CONCENTRATION_LIMIT,

                "status":
                "HIGH_CONCENTRATION"
            })

    adjusted[
        "concentration_alerts"
    ] = concentration_alerts

    priority = {
        "SELL_ALL":
        7,

        "SELL_PARTIAL":
        6,

        "EVENT_BLOCK":
        5,

        "MANUAL_REVIEW":
        4,

        "BUY_TO_TARGET":
        3,

        "NO_TRADE":
        1
    }

    plans.sort(
        key=lambda item:
        priority.get(
            item.get(
                "trade_action"
            ),
            0
        ),
        reverse=True
    )

    return adjusted


def apply_operational_turnover_guardrail(
    rebalancing_result,
    portfolio_results
):
    adjusted = copy.deepcopy(
        rebalancing_result
        or
        {}
    )

    plans = (
        adjusted.get(
            "rebalancing_plan",
            []
        )
        or
        []
    )

    portfolio_value = safe_float(
        adjusted.get(
            "portfolio_value",
            0.0
        ),
        0.0
    )

    gross_before = _gross_trade_value(
        plans
    )

    suppressed_rows = []

    for plan in plans:
        trade_action = plan.get(
            "trade_action"
        )

        current_weight = safe_float(
            plan.get(
                "current_weight_pct",
                0.0
            ),
            0.0
        )

        target_weight = safe_float(
            plan.get(
                "target_weight_pct",
                current_weight
            ),
            current_weight
        )

        weight_gap = abs(
            target_weight
            -
            current_weight
        )

        plan[
            "pre_turnover_guardrail_trade_action"
        ] = trade_action

        plan[
            "turnover_guardrail_weight_gap_pct"
        ] = round(
            weight_gap,
            2
        )

        if trade_action not in {
            "BUY_TO_TARGET",
            "SELL_PARTIAL"
        }:
            plan[
                "turnover_guardrail_status"
            ] = "NOT_APPLICABLE"

            continue

        if (
            weight_gap
            >=
            MIN_TARGET_WEIGHT_GAP_PCT
        ):
            plan[
                "turnover_guardrail_status"
            ] = "PASSED"

            continue

        suppressed_value = abs(
            safe_float(
                plan.get(
                    "suggested_trade_value",
                    0.0
                ),
                0.0
            )
        )

        suppressed_rows.append({
            "ticker":
            plan.get(
                "ticker"
            ),

            "pre_guardrail_trade_action":
            trade_action,

            "weight_gap_pct":
            round(
                weight_gap,
                2
            ),

            "suppressed_trade_value":
            round(
                suppressed_value,
                2
            )
        })

        current_value = safe_float(
            plan.get(
                "current_value",
                0.0
            ),
            0.0
        )

        plan[
            "trade_action"
        ] = "NO_TRADE"

        plan[
            "suggested_shares"
        ] = 0

        plan[
            "suggested_trade_value"
        ] = 0.0

        plan[
            "requires_cash"
        ] = False

        plan[
            "projected_value"
        ] = round(
            current_value,
            2
        )

        plan[
            "projected_weight_pct"
        ] = round(
            current_weight,
            2
        )

        plan[
            "turnover_guardrail_status"
        ] = "SUPPRESSED_WITHIN_BAND"

        plan[
            "reason"
        ] = (
            "Operational turnover guardrail: current-to-target weight gap "
            "is below the frozen 1.00 percentage-point tolerance."
        )

    adjusted = _recalculate(
        adjusted,
        portfolio_results
    )

    gross_after = _gross_trade_value(
        adjusted.get(
            "rebalancing_plan",
            []
        )
    )

    suppressed_gross = max(
        0.0,
        gross_before
        -
        gross_after
    )

    before_turnover_pct = (
        gross_before
        /
        portfolio_value
        *
        100
        if portfolio_value
        >
        0
        else 0.0
    )

    after_turnover_pct = (
        gross_after
        /
        portfolio_value
        *
        100
        if portfolio_value
        >
        0
        else 0.0
    )

    adjusted[
        "turnover_guardrail"
    ] = {
        "engine":
        ENGINE_VERSION,

        "signature":
        SIGNATURE,

        "policy_file":
        POLICY_FILE,

        "applied":
        True,

        "strategic_actions_changed":
        False,

        "min_target_weight_gap_pct":
        MIN_TARGET_WEIGHT_GAP_PCT,

        "eligible_trade_actions":
        [
            "BUY_TO_TARGET",
            "SELL_PARTIAL"
        ],

        "full_exit_suppression_allowed":
        False,

        "suppressed_trade_count":
        len(
            suppressed_rows
        ),

        "suppressed_trades":
        suppressed_rows,

        "gross_trade_value_before":
        round(
            gross_before,
            2
        ),

        "gross_trade_value_after":
        round(
            gross_after,
            2
        ),

        "suppressed_gross_trade_value":
        round(
            suppressed_gross,
            2
        ),

        "one_scan_turnover_pct_before":
        round(
            before_turnover_pct,
            2
        ),

        "one_scan_turnover_pct_after":
        round(
            after_turnover_pct,
            2
        ),

        "one_scan_turnover_reduction_pct_points":
        round(
            before_turnover_pct
            -
            after_turnover_pct,
            2
        ),

        "paper_order_submission_authorized":
        False,

        "live_execution_authorized":
        False
    }

    return adjusted
