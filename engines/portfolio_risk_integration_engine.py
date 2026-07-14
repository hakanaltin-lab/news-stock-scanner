"""
V10.6.2 Portfolio Risk Integration Engine

Purpose:
Connect portfolio construction,
risk budget management and risk control.

Functions:
- Allocation validation
- Risk override
- Final capital decision
"""


from datetime import datetime



def evaluate_allocation_request(
    ticker,
    requested_weight,
    risk_action
):
    """
    Evaluates requested allocation
    """

    if risk_action == "ALLOW_ALLOCATION":

        final_action = "ALLOW_POSITION"

        status = "APPROVED"



    elif risk_action == "LIMIT_ALLOCATION":

        final_action = "REDUCE_POSITION_SIZE"

        status = "LIMITED"



    else:

        final_action = "BLOCK_POSITION"

        status = "REJECTED"



    return {


        "ticker":

        ticker,


        "requested_weight":

        requested_weight,


        "risk_status":

        status,


        "final_action":

        final_action

    }





def apply_risk_override(
    requested_action,
    portfolio_risk_score
):
    """
    Risk Sentinel override logic
    """


    if portfolio_risk_score < 50:

        return "BLOCK"


    elif portfolio_risk_score < 75:

        return "LIMIT"


    return requested_action





def generate_final_allocation_decision(
    ticker,
    requested_weight,
    portfolio_risk_score,
    requested_action="ALLOW_POSITION"
):
    """
    Main risk integration function
    """


    risk_override = apply_risk_override(

        requested_action,

        portfolio_risk_score

    )


    if risk_override == "BLOCK":

        risk_action = "BLOCK_ALLOCATION"



    elif risk_override == "LIMIT":

        risk_action = "LIMIT_ALLOCATION"



    else:

        risk_action = "ALLOW_ALLOCATION"



    decision = evaluate_allocation_request(

        ticker,

        requested_weight,

        risk_action

    )



    return {


        "engine":

        "V10.6.2 Portfolio Risk Integration Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio_risk_score":

        portfolio_risk_score,


        "decision":

        decision

    }
