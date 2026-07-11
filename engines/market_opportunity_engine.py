"""
V6.2 Market Opportunity Scanner

Purpose:
Find market opportunities automatically.

Pipeline:

Market Universe
        |
Momentum Filter
        |
Volume Expansion
        |
Catalyst Check
        |
Alpha Ranking
        |
CIO Decision

"""


from datetime import datetime



def calculate_opportunity_score(stock):

    scores = stock.get(
        "scores",
        {}
    )


    momentum = scores.get(
        "market_score",
        0
    )

    catalyst = scores.get(
        "catalyst_score",
        0
    )

    alpha = scores.get(
        "alpha_score",
        0
    )

    risk = scores.get(
        "risk_score",
        0
    )


    score = (

        momentum * 0.30
        +
        catalyst * 0.25
        +
        alpha * 0.35
        +
        risk * 0.10

    )


    return round(score,2)



def scan_market_opportunities(
        stocks
):

    opportunities=[]


    for stock in stocks:


        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )


        score = calculate_opportunity_score(
            stock
        )


        if score >= 70:

            opportunities.append({

                "ticker":ticker,

                "opportunity_score":score,

                "signal":
                "HIGH PRIORITY",

                "timestamp":
                datetime.utcnow().isoformat()

            })


    opportunities.sort(

        key=lambda x:
        x["opportunity_score"],

        reverse=True

    )


    return opportunities[:20]



def generate_opportunity_report(
        stocks
):

    return {

        "engine":
        "V6.2 Market Opportunity Scanner",

        "generated":
        datetime.utcnow().isoformat(),

        "top_opportunities":
        scan_market_opportunities(
            stocks
        )

    }
