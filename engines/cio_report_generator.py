"""
V7.1.5 CIO Report Generator

Purpose:
Convert AI trading outputs into human readable
investment committee reports.

Outputs:
- Daily CIO report
- Portfolio summary
- Opportunity summary
- Risk summary

"""


from datetime import datetime



def generate_stock_summary(
    stock
):

    decision = stock.get(
        "decision",
        {}
    )


    ai_view = stock.get(
        "ai_view",
        {}
    )


    return {


        "ticker":
        stock.get(
            "ticker"
        ),


        "action":
        decision.get(
            "action",
            "WATCH"
        ),


        "confidence":
        ai_view.get(
            "confidence",
            0
        ),


        "strategy":
        ai_view.get(
            "strategy",
            "N/A"
        ),


        "investment_view":
        ai_view.get(
            "investment_view",
            ""
        )

    }




def generate_cio_report(
    portfolio,
    market_regime
):

    opportunities=[]

    risks=[]


    for stock in portfolio:


        summary = generate_stock_summary(
            stock
        )


        if summary["action"] in [
            "BUY",
            "ACCUMULATE"
        ]:

            opportunities.append(
                summary
            )


        if summary["confidence"] < 50:

            risks.append({

                "ticker":
                summary["ticker"],

                "issue":
                "Low confidence signal"

            })



    return {


        "report":

        "DAILY CIO MARKET REPORT",



        "generated":

        datetime.utcnow().isoformat(),



        "market_regime":

        market_regime,



        "top_opportunities":

        opportunities,



        "risk_alerts":

        risks,



        "portfolio_size":

        len(portfolio)

    }




def export_report_text(
    report
):

    text = []


    text.append(
        "DAILY CIO MARKET REPORT"
    )


    text.append(
        "======================"
    )


    text.append(
        f"Market Regime: {report.get('market_regime')}"
    )


    text.append(
        ""
    )


    text.append(
        "TOP OPPORTUNITIES"
    )


    for item in report.get(
        "top_opportunities",
        []
    ):

        text.append(

            f"{item['ticker']} - "
            f"{item['action']} "
            f"Confidence: {item['confidence']}"

        )


    return "\n".join(text)
