"""
V6.6 Trading Orchestrator Engine

Central decision coordinator.

Pipeline:

Market Data
     |
Opportunity Scanner
     |
Alpha Intelligence
     |
Decision Engine
     |
Risk Management
     |
Execution Engine
     |
Broker Connector

Purpose:
- Generate trade candidates
- Apply risk gate
- Prepare execution instructions
- Keep live trading disabled by default
"""


from datetime import datetime


LIVE_TRADING_ENABLED = False


def create_trade_candidate(
    ticker,
    decision,
    risk_check,
    execution_plan=None
):
    """
    Creates structured trade candidate
    """

    return {

        "ticker": ticker,

        "timestamp": datetime.utcnow().isoformat(),

        "decision": decision,

        "risk_check": risk_check,

        "execution_plan": execution_plan,

        "status":
            "READY"
            if risk_check.get("approved")
            else "BLOCKED",

        "live_order":
            LIVE_TRADING_ENABLED

    }



def evaluate_trade(
    ticker,
    opportunity_score,
    decision_output,
    risk_output
):
    """
    Main orchestration layer
    """

    if opportunity_score < 70:

        return create_trade_candidate(
            ticker,
            decision_output,
            {
                "approved": False,
                "reason": "Opportunity score below threshold"
            }
        )


    if not risk_output.get("approved"):

        return create_trade_candidate(
            ticker,
            decision_output,
            risk_output
        )


    return create_trade_candidate(
        ticker,
        decision_output,
        risk_output,
        {
            "action": decision_output.get("action"),
            "execution_mode": "PAPER_READY"
        }
    )



def run_orchestrator(scan_results):
    """
    Receives scanner output
    and creates ranked trade candidates
    """

    candidates = []


    for item in scan_results:

        candidate = evaluate_trade(

            ticker=item.get("ticker"),

            opportunity_score=
                item.get("opportunity_score",0),

            decision_output=
                item.get("decision",{}),

            risk_output=
                item.get(
                    "risk",
                    {
                        "approved":False
                    }
                )

        )

        candidates.append(candidate)


    return {

        "generated":
            datetime.utcnow().isoformat(),

        "engine":
            "V6.6",

        "live_trading":
            LIVE_TRADING_ENABLED,

        "candidates":
            candidates

    }
