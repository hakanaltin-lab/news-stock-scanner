"""
V10.7 Tax & Capital Efficiency Engine

Purpose:
Optimize capital usage across portfolio.

Functions:
- Tax loss harvesting intelligence
- Capital rotation analysis
- Cash deployment logic
- Opportunity cost analysis
- Capital efficiency scoring
"""


from datetime import datetime



def analyze_tax_loss(
    unrealized_loss_percent,
    alpha_score
):
    """
    Determines tax harvesting opportunity
    """


    if unrealized_loss_percent <= -20 and alpha_score < 50:

        return "CONSIDER_TAX_HARVEST"



    if unrealized_loss_percent <= -20:

        return "HOLD_REVIEW"



    return "NO_ACTION"





def analyze_capital_rotation(
    current_alpha,
    alternative_alpha
):
    """
    Compares current holding with alternatives
    """


    if alternative_alpha >= current_alpha + 20:

        return "ROTATE_CAPITAL"



    return "MAINTAIN_POSITION"





def analyze_cash_deployment(
    market_regime,
    cash_percentage
):
    """
    Evaluates cash usage
    """


    if market_regime == "BULLISH" and cash_percentage > 15:

        return "DEPLOY_CAPITAL"



    if market_regime == "RISK_OFF":

        return "PRESERVE_CASH"



    return "MAINTAIN_CASH"





def calculate_opportunity_cost(
    current_return,
    alternative_return
):
    """
    Calculates return gap
    """


    return round(

        alternative_return - current_return,

        2

    )





def calculate_capital_efficiency_score(
    rotation_signal,
    cash_signal,
    tax_signal
):
    """
    Creates capital efficiency score
    """


    score = 70



    if rotation_signal == "ROTATE_CAPITAL":

        score += 15



    if cash_signal == "DEPLOY_CAPITAL":

        score += 10



    if tax_signal == "CONSIDER_TAX_HARVEST":

        score += 5



    return max(

        0,

        min(

            100,

            score

        )

    )





def generate_capital_efficiency_report(
    ticker,
    unrealized_loss_percent,
    alpha_score,
    alternative_alpha,
    current_return,
    alternative_return,
    market_regime,
    cash_percentage
):
    """
    Main capital efficiency engine
    """


    tax_action = analyze_tax_loss(

        unrealized_loss_percent,

        alpha_score

    )


    rotation_signal = analyze_capital_rotation(

        alpha_score,

        alternative_alpha

    )


    cash_signal = analyze_cash_deployment(

        market_regime,

        cash_percentage

    )


    opportunity_gap = calculate_opportunity_cost(

        current_return,

        alternative_return

    )


    efficiency_score = calculate_capital_efficiency_score(

        rotation_signal,

        cash_signal,

        tax_action

    )


    return {


        "engine":

        "V10.7 Tax & Capital Efficiency Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "tax_action":

        tax_action,


        "rotation_signal":

        rotation_signal,


        "cash_signal":

        cash_signal,


        "opportunity_cost_percent":

        opportunity_gap,


        "capital_efficiency_score":

        efficiency_score

    }
