"""
V7.1 AI Decision Layer

Purpose:
Generate CIO-style investment reasoning.

Functions:
- Combine intelligence signals
- Generate investment thesis
- Explain decision
- Confidence assessment

"""


from datetime import datetime



def generate_ai_view(
    ticker,
    market_score,
    catalyst_score,
    strategy,
    regime,
    risk_score,
    action
):

    """
    Creates CIO style analysis
    """

    positives = []

    concerns = []



    if market_score >= 70:

        positives.append(
            "Strong market momentum"
        )

    elif market_score < 40:

        concerns.append(
            "Weak technical momentum"
        )



    if catalyst_score >= 70:

        positives.append(
            "Positive catalyst environment"
        )

    elif catalyst_score < 40:

        concerns.append(
            "Limited catalysts"
        )



    if risk_score >= 70:

        positives.append(
            "Risk profile acceptable"
        )

    else:

        concerns.append(
            "Risk requires monitoring"
        )



    if action in [
        "BUY",
        "ACCUMULATE"
    ]:

        conclusion = (
            "Opportunity identified. "
            "Consider disciplined entry."
        )

    elif action == "WATCH":

        conclusion = (
            "Interesting setup but "
            "confirmation required."
        )

    else:

        conclusion = (
            "Current risk/reward "
            "is not attractive."
        )



    confidence = int(

        (
            market_score
            +
            catalyst_score
            +
            risk_score

        ) / 3

    )



    return {


        "ticker":
        ticker,


        "timestamp":
        datetime.utcnow().isoformat(),



        "strategy":
        strategy,



        "market_regime":
        regime,



        "investment_view":

        conclusion,



        "confidence":

        confidence,



        "positive_factors":

        positives,



        "risk_factors":

        concerns

    }




def generate_portfolio_commentary(
    decisions
):

    """
    Portfolio level CIO summary
    """


    buy_count = 0

    watch_count = 0



    for item in decisions:


        action = item.get(
            "action"
        )


        if action in [
            "BUY",
            "ACCUMULATE"
        ]:

            buy_count += 1


        elif action == "WATCH":

            watch_count += 1



    return {


        "engine":
        "V7.1 AI Decision Layer",


        "summary":

        f"{buy_count} opportunities identified, "
        f"{watch_count} names require monitoring.",


        "timestamp":
        datetime.utcnow().isoformat()

    }
