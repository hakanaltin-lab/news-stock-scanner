"""
V7.4 Live Intelligence Integration Engine

Purpose:
Central intelligence aggregation layer.

Combines:

- Market Data
- News Intelligence
- Catalyst Intelligence
- Alpha Intelligence
- Risk Intelligence
- CIO Decision Layer

Output:
Unified investment intelligence report
"""


from datetime import datetime



def calculate_confidence(
    market_score,
    news_score,
    alpha_score,
    risk_score
):
    """
    Calculates overall confidence
    """

    confidence = (

        market_score +
        news_score +
        alpha_score +
        risk_score

    ) / 4


    return round(
        confidence,
        2
    )




def determine_cio_action(
    confidence,
    risk_score
):
    """
    Generates CIO level action
    """

    if risk_score < 40:

        return "BLOCKED"


    if confidence >= 80:

        return "BUY_APPROVED"


    if confidence >= 65:

        return "BUY_REDUCED"


    if confidence >= 50:

        return "WATCH"


    return "AVOID"




def build_live_intelligence(
    ticker,
    market_score,
    news_score,
    catalyst_score,
    alpha_score,
    risk_score
):
    """
    Creates unified intelligence object
    """


    confidence = calculate_confidence(

        market_score,

        news_score,

        alpha_score,

        risk_score

    )


    action = determine_cio_action(

        confidence,

        risk_score

    )



    return {


        "ticker":
        ticker,


        "timestamp":
        datetime.utcnow().isoformat(),



        "intelligence": {


            "market_score":
            market_score,


            "news_score":
            news_score,


            "catalyst_score":
            catalyst_score,


            "alpha_score":
            alpha_score,


            "risk_score":
            risk_score

        },



        "cio_decision": {


            "action":
            action,


            "confidence":
            confidence

        },


        "engine":
        "V7.4 Live Intelligence Integration"

    }





def generate_market_snapshot(
    assets
):
    """
    Creates portfolio intelligence snapshot
    """


    report = []


    for asset in assets:


        report.append(

            build_live_intelligence(

                asset.get("ticker"),

                asset.get(
                    "market_score",
                    0
                ),

                asset.get(
                    "news_score",
                    0
                ),

                asset.get(
                    "catalyst_score",
                    0
                ),

                asset.get(
                    "alpha_score",
                    0
                ),

                asset.get(
                    "risk_score",
                    0
                )

            )

        )


    return {


        "generated":

        datetime.utcnow().isoformat(),


        "engine":

        "V7.4",


        "assets":

        report

    }
