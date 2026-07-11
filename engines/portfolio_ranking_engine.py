"""
V6.1 Portfolio CIO Ranking Engine

Purpose:
Rank stocks like a portfolio manager.

Input:
- Decision engine output
- Alpha score
- Catalyst score
- Risk score
- Market score

Output:
- CIO ranking
- Top opportunities
- Avoid list
"""


from datetime import datetime


def calculate_cio_score(stock):

    scores = stock.get("scores", {})

    alpha = scores.get("alpha_score", 0)
    catalyst = scores.get("catalyst_score", 0)
    market = scores.get("market_score", 0)
    risk = scores.get("risk_score", 0)

    decision = stock.get(
        "decision",
        {}
    ).get(
        "action",
        "AVOID"
    )


    decision_bonus = {

        "BUY": 20,
        "ACCUMULATE": 15,
        "WATCH": 5,
        "HOLD": 0,
        "AVOID": -20,
        "NO TRADE": -15

    }.get(decision,0)


    cio_score = (

        alpha * 0.35
        +
        catalyst * 0.25
        +
        market * 0.20
        +
        risk * 0.20
        +
        decision_bonus

    )


    return round(cio_score,2)



def rank_portfolio(stocks):

    ranking=[]


    for stock in stocks:

        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )


        score = calculate_cio_score(stock)


        ranking.append({

            "ticker": ticker,

            "cio_score": score,

            "action":
            stock.get(
                "decision",
                {}
            ).get(
                "action",
                "AVOID"
            ),

            "confidence":
            stock.get(
                "decision",
                {}
            ).get(
                "confidence",
                0
            )

        })


    ranking.sort(

        key=lambda x:
        x["cio_score"],

        reverse=True

    )


    return ranking



def generate_cio_report(stocks):

    ranked = rank_portfolio(stocks)


    top_opportunities = [

        x for x in ranked

        if x["action"]
        in [
            "BUY",
            "ACCUMULATE",
            "WATCH"
        ]

    ][:10]


    avoid_list = [

        x for x in ranked

        if x["action"]
        in [
            "AVOID",
            "NO TRADE"
        ]

    ]


    return {

        "generated":
        datetime.utcnow().isoformat(),

        "engine":
        "V6.1 CIO Ranking Engine",

        "top_opportunities":
        top_opportunities,

        "avoid_list":
        avoid_list,

        "full_ranking":
        ranked

    }
