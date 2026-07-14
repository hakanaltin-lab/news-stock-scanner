"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

VaR / CVaR Engine v1.0

Purpose:
Estimate portfolio downside risk.

Controls:
- Value at Risk (VaR)
- Conditional Value at Risk (CVaR)
- Loss threshold monitoring
"""


from datetime import datetime



def calculate_var(
    portfolio_value,
    confidence_level,
    expected_loss_percentage
):
    """
    Calculates Value at Risk.

    Example:
    Portfolio:
    $100,000

    Expected loss:
    5%

    VaR:
    $5,000
    """


    var_amount = (

        portfolio_value

        *

        expected_loss_percentage

        /

        100

    )


    return round(

        var_amount,

        2

    )





def calculate_cvar(
    var_amount,
    tail_multiplier=1.5
):
    """
    Calculates Conditional Value at Risk.

    CVaR represents expected loss
    beyond the VaR threshold.
    """


    return round(

        var_amount

        *

        tail_multiplier,

        2

    )





def evaluate_var_risk(
    portfolio_value,
    var_amount,
    cvar_amount
):
    """
    Evaluates risk severity.
    """


    var_percentage = (

        var_amount

        /

        portfolio_value

    ) * 100



    cvar_percentage = (

        cvar_amount

        /

        portfolio_value

    ) * 100



    if cvar_percentage > 15:

        decision = "BLOCK"



    elif cvar_percentage > 10:

        decision = "REDUCE_RISK"



    elif var_percentage > 5:

        decision = "WARNING"



    else:

        decision = "APPROVE"



    return {


        "var_percentage":

        round(var_percentage,2),


        "cvar_percentage":

        round(cvar_percentage,2),


        "decision":

        decision

    }





def run_var_analysis(
    portfolio_value,
    confidence_level,
    expected_loss_percentage
):
    """
    Main VaR/CVaR risk authority function.
    """


    var_amount = calculate_var(

        portfolio_value,

        confidence_level,

        expected_loss_percentage

    )


    cvar_amount = calculate_cvar(

        var_amount

    )


    risk_evaluation = evaluate_var_risk(

        portfolio_value,

        var_amount,

        cvar_amount

    )



    return {


        "engine":

        "L6.4 VaR CVaR Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio_value":

        portfolio_value,


        "confidence_level":

        confidence_level,


        "var_amount":

        var_amount,


        "cvar_amount":

        cvar_amount,


        "risk_assessment":

        risk_evaluation

    }
