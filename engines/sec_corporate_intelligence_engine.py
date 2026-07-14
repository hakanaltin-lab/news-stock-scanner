"""
V10.4 SEC Filing & Corporate Action Intelligence Engine

Purpose:
Analyze corporate information and convert it
into investment intelligence.

Functions:
- SEC filing analysis
- Insider activity analysis
- Capital allocation analysis
- Corporate event scoring
- Corporate health score
"""


from datetime import datetime



def analyze_financial_filing(
    revenue_growth,
    margin_trend,
    cash_position
):
    """
    Evaluates company financial condition
    """

    score = 50


    if revenue_growth >= 20:

        score += 20


    elif revenue_growth < 0:

        score -= 20



    if margin_trend == "IMPROVING":

        score += 15


    elif margin_trend == "DECLINING":

        score -= 15



    if cash_position == "STRONG":

        score += 15


    elif cash_position == "WEAK":

        score -= 15



    return max(

        0,

        min(

            100,

            score

        )

    )





def analyze_insider_activity(
    insider_action
):
    """
    Evaluates insider transactions
    """


    if insider_action == "BUYING":

        return 10


    elif insider_action == "SELLING":

        return -10


    return 0





def analyze_capital_allocation(
    capital_event
):
    """
    Evaluates buyback and dilution
    """


    if capital_event == "BUYBACK":

        return 10


    elif capital_event == "DILUTION":

        return -15


    return 0





def analyze_corporate_event(
    event
):
    """
    Evaluates strategic events
    """


    positive_events = [

        "ACQUISITION",

        "PARTNERSHIP",

        "MAJOR_CONTRACT"

    ]


    negative_events = [

        "LEGAL_RISK",

        "LEADERSHIP_CHANGE"

    ]



    if event in positive_events:

        return 15



    elif event in negative_events:

        return -15



    return 0





def calculate_corporate_health_score(
    financial_score,
    insider_score,
    capital_score,
    event_score
):
    """
    Creates overall corporate health score
    """


    score = (

        financial_score * 0.6

        +

        (50 + insider_score) * 0.15

        +

        (50 + capital_score) * 0.15

        +

        (50 + event_score) * 0.10

    )


    return round(

        max(

            0,

            min(

                100,

                score

            )

        )

    )





def generate_corporate_intelligence(
    ticker,
    revenue_growth,
    margin_trend,
    cash_position,
    insider_action,
    capital_event,
    corporate_event
):
    """
    Main corporate intelligence engine
    """


    financial_score = analyze_financial_filing(

        revenue_growth,

        margin_trend,

        cash_position

    )


    insider_score = analyze_insider_activity(

        insider_action

    )


    capital_score = analyze_capital_allocation(

        capital_event

    )


    event_score = analyze_corporate_event(

        corporate_event

    )


    health_score = calculate_corporate_health_score(

        financial_score,

        insider_score,

        capital_score,

        event_score

    )



    return {


        "engine":

        "V10.4 SEC Filing & Corporate Intelligence Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "financial_score":

        financial_score,


        "insider_signal":

        insider_score,


        "capital_allocation_signal":

        capital_score,


        "corporate_event_signal":

        event_score,


        "corporate_health_score":

        health_score

    }
