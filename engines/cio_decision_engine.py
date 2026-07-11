"""
V7 CIO Decision Engine

Purpose:
Convert AI intelligence signals and risk controls
into final CIO portfolio decisions.

Layer:
Decision Engine
        ↓
Risk Controller
        ↓
CIO Decision Layer
        ↓
Execution
"""


from datetime import datetime


def generate_cio_decision(
    ticker,
    decision,
    risk_check
):
    """
    Final institutional portfolio decision layer
    """

    output = {

        "ticker": ticker,

        "timestamp": datetime.utcnow().isoformat(),

        "input_action": decision.get(
            "action",
            "UNKNOWN"
        ),

        "risk_status": risk_check.get(
            "status",
            "UNKNOWN"
        ),

        "final_action": None,

        "approval": False
    }


    # Risk Controller blocks trade

    if risk_check.get("approved") is False:

        output["final_action"] = "BLOCKED"

        output["approval"] = False

        return output



    action = decision.get(
        "action"
    )


    confidence = decision.get(
        "confidence",
        0
    )


    # CIO approval rules

    if action == "BUY" and confidence >= 70:

        output["final_action"] = "BUY_APPROVED"

        output["approval"] = True



    elif action == "BUY" and confidence >= 50:

        output["final_action"] = "BUY_REDUCED"

        output["approval"] = True



    elif action == "WATCH":

        output["final_action"] = "MONITOR"



    else:

        output["final_action"] = "AVOID"



    return output
