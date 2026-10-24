"""
V6.8 AURORA Opportunity Safety Gate

Purpose:
- Prevent chasing overextended stocks
- Prevent BUY / ACCUMULATE when sector backdrop is very weak
- Downgrade risky new opportunities to WATCH
- Preserve original decision for transparency
"""


def apply_opportunity_safety_gate(
    decision,
    sector_score,
    overextension_pct
):

    if not isinstance(decision, dict):

        return decision


    safe_decision = decision.copy()

    original_action = decision.get(
        "action",
        "AVOID"
    )


    safety_reasons = []


    # ==============================================
    # ONLY CONTROL NEW ENTRY ACTIONS
    # ==============================================

    if original_action not in [
        "BUY",
        "ACCUMULATE"
    ]:

        safe_decision[
            "safety_gate"
        ] = {

            "triggered":
            False,

            "original_action":
            original_action,

            "reasons":
            []

        }

        return safe_decision


    # ==============================================
    # 1. VERY WEAK SECTOR FILTER
    # ==============================================

    if (
        sector_score is not None
        and sector_score < 30
    ):

        safety_reasons.append(
            "Sector backdrop is very weak"
        )


    # ==============================================
    # 2. OVEREXTENSION FILTER
    # ==============================================

    if (
        overextension_pct is not None
        and overextension_pct >= 12
    ):

        safety_reasons.append(
            "Price is overextended versus SMA20"
        )


    # ==============================================
    # SAFETY DOWNGRADE
    # ==============================================

    if safety_reasons:

        safe_decision[
            "action"
        ] = "WATCH"

        safe_decision[
            "setup_quality"
        ] = "WAIT_FOR_PULLBACK"

        safe_decision[
            "entry_zone"
        ] = None

        safe_decision[
            "stop_loss"
        ] = None

        safe_decision[
            "target_price"
        ] = None

        safe_decision[
            "risk_reward"
        ] = None

        safe_decision[
            "reasons"
        ] = (
            safety_reasons
            + [
                "New entry blocked by V6.8 Safety Gate"
            ]
        )

        safe_decision[
            "safety_gate"
        ] = {

            "triggered":
            True,

            "original_action":
            original_action,

            "final_action":
            "WATCH",

            "reasons":
            safety_reasons

        }

        return safe_decision


    # ==============================================
    # PASS
    # ==============================================

    safe_decision[
        "safety_gate"
    ] = {

        "triggered":
        False,

        "original_action":
        original_action,

        "final_action":
        original_action,

        "reasons":
        []

    }


    return safe_decision
