"""
V9.6 Autonomous Market Scanner Engine

Purpose:
Scan market opportunities and identify
high potential investment candidates.

Functions:
- Momentum detection
- Volume anomaly detection
- Catalyst scoring
- Opportunity ranking
- CIO review pipeline
"""


from datetime import datetime



def calculate_momentum_score(
    price_change,
    volume_change
):
    """
    Measures market momentum
    """


    score = 0


    if price_change >= 5:

        score += 40


    elif price_change >= 2:

        score += 20



    if volume_change >= 100:

        score += 40


    elif volume_change >= 50:

        score += 20



    return min(
        score,
        100
    )





def calculate_catalyst_score(
    catalysts
):
    """
    Evaluates catalyst strength
    """


    score = 0



    for catalyst in catalysts:


        impact = catalyst.get(
            "impact",
            "LOW"
        )


        if impact == "HIGH":

            score += 30


        elif impact == "MEDIUM":

            score += 20


        else:

            score += 10



    return min(
        score,
        100
    )





def calculate_opportunity_score(
    momentum_score,
    catalyst_score,
    quality_score
):
    """
    Creates opportunity score
    """


    return round(

        momentum_score * 0.40

        +

        catalyst_score * 0.35

        +

        quality_score * 0.25

    )





def classify_opportunity(
    score
):
    """
    Sends opportunities to CIO pipeline
    """


    if score >= 85:

        return "SEND_TO_CIO_REVIEW"


    elif score >= 70:

        return "WATCHLIST"


    else:

        return "IGNORE"





def scan_market_candidate(
    ticker,
    price_change,
    volume_change,
    catalysts,
    quality_score
):
    """
    Main scanner function
    """


    momentum_score = calculate_momentum_score(

        price_change,

        volume_change

    )


    catalyst_score = calculate_catalyst_score(

        catalysts

    )


    opportunity_score = calculate_opportunity_score(

        momentum_score,

        catalyst_score,

        quality_score

    )



    return {


        "ticker":

        ticker,


        "opportunity_score":

        opportunity_score,


        "momentum_score":

        momentum_score,


        "catalyst_score":

        catalyst_score,


        "recommendation":

        classify_opportunity(

            opportunity_score

        )

    }





def generate_market_scan_report(
    opportunities
):
    """
    Creates CIO market scan report
    """


    opportunities.sort(

        key=lambda x:

        x["opportunity_score"],

        reverse=True

    )


    return {


        "engine":

        "V9.6 Autonomous Market Scanner Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "top_opportunities":

        opportunities,


        "status":

        "READY"

    }
