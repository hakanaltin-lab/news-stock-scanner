"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Portfolio Risk Engine v1.0

Purpose:
Measure total portfolio risk profile.

Controls:
- Volatility
- Beta
- Correlation
- Risk contribution
- Portfolio risk score
"""


from datetime import datetime



def calculate_portfolio_volatility(
    volatility_values
):
    """
    Calculates weighted average portfolio volatility.
    """


    if not volatility_values:

        return 0



    return round(

        sum(volatility_values)

        /

        len(volatility_values),

        2

    )





def calculate_average_beta(
    beta_values
):
    """
    Calculates portfolio beta.
    """


    if not beta_values:

        return 0



    return round(

        sum(beta_values)

        /

        len(beta_values),

        2

    )





def evaluate_correlation_risk(
    average_correlation
):
    """
    Evaluates correlation concentration.
    """


    if average_correlation >= 0.80:

        return "HIGH"


    elif average_correlation >= 0.60:

        return "MEDIUM"


    return "LOW"





def calculate_risk_score(
    volatility,
    beta,
    correlation_risk
):
    """
    Generates overall portfolio risk score.
    0 = low risk
    100 = extreme risk
    """


    score = 0


    if volatility > 30:

        score += 40


    elif volatility > 20:

        score += 25


    else:

        score += 10



    if beta > 1.5:

        score += 30


    elif beta > 1.2:

        score += 20


    else:

        score += 10



    if correlation_risk == "HIGH":

        score += 30


    elif correlation_risk == "MEDIUM":

        score += 15



    return min(

        100,

        score

    )





def evaluate_portfolio_risk(
    holdings,
    volatility_values,
    beta_values,
    average_correlation
):
    """
    Main portfolio risk authority function.
    """


    volatility = calculate_portfolio_volatility(

        volatility_values

    )


    beta = calculate_average_beta(

        beta_values

    )


    correlation_risk = evaluate_correlation_risk(

        average_correlation

    )


    risk_score = calculate_risk_score(

        volatility,

        beta,

        correlation_risk

    )


    if risk_score >= 75:

        decision = "REDUCE_RISK"


    elif risk_score >= 50:

        decision = "REBALANCE"


    else:

        decision = "APPROVE"



    return {


        "engine":

        "L6.3 Portfolio Risk Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "holdings":

        holdings,


        "portfolio_volatility":

        volatility,


        "portfolio_beta":

        beta,


        "correlation_risk":

        correlation_risk,


        "risk_score":

        risk_score,


        "decision":

        decision

    }
