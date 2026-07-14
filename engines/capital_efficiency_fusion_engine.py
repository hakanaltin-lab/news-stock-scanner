"""
V10.7.1 Capital Efficiency Fusion Engine

Purpose:
Integrate capital efficiency analysis
into AI CIO portfolio decisions.

Functions:
- Capital efficiency evaluation
- Rotation decision
- Cash deployment signal
- CIO action generation
"""


from datetime import datetime



def evaluate_efficiency_score(
    efficiency_score
):
    """
    Evaluates capital efficiency quality
    """


    if efficiency_score >= 85:

        return "OPTIMAL"


    elif efficiency_score >= 70:

        return "ACCEPTABLE"


    return "INEFFICIENT"





def determine_capital_action(
    rotation_signal,
    cash_signal,
    efficiency_status
):
    """
    Creates capital optimization action
    """


    if rotation_signal == "ROTATE_CAPITAL":

        return "REALLOCATE_CAPITAL"



    if cash_signal == "DEPLOY_CAPITAL":

        return "DEPLOY_CAPITAL"



    if efficiency_status == "OPTIMAL":

        return "MAINTAIN_ALLOCATION"



    return "REVIEW_ALLOCATION"





def calculate_cio_confidence_change(
    efficiency_score
):
    """
    Adjust CIO confidence
    """


    if efficiency_score >= 85:

        return 8


    elif efficiency_score >= 70:

        return 3


    return -5





def fuse_capital_efficiency(
    portfolio_name,
    efficiency_score,
    rotation_signal,
    cash_signal
):
    """
    Main capital efficiency fusion function
    """


    efficiency_status = evaluate_efficiency_score(

        efficiency_score

    )


    confidence_change = calculate_cio_confidence_change(

        efficiency_score

    )


    capital_action = determine_capital_action(

        rotation_signal,

        cash_signal,

        efficiency_status

    )


    return {


        "engine":

        "V10.7.1 Capital Efficiency Fusion Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio":

        portfolio_name,


        "capital_efficiency_score":

        efficiency_score,


        "efficiency_status":

        efficiency_status,


        "rotation_signal":

        rotation_signal,


        "cash_signal":

        cash_signal,


        "cio_confidence_adjustment":

        confidence_change,


        "capital_action":

        capital_action

    }
