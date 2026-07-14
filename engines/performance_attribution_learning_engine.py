"""
V10.9 AI CIO Performance Attribution & Learning Engine

Purpose:
Analyze investment decisions after execution
and generate learning signals.

Functions:
- Decision tracking
- Outcome analysis
- Performance attribution
- Decision quality scoring
- Learning feedback
"""


from datetime import datetime



def analyze_outcome(
    expected_return,
    actual_return
):
    """
    Compares expected vs actual performance
    """


    difference = actual_return - expected_return


    if difference >= 5:

        return "OUTPERFORM"



    elif difference <= -5:

        return "UNDERPERFORM"



    return "AS_EXPECTED"





def calculate_decision_quality(
    expected_return,
    actual_return,
    confidence
):
    """
    Calculates decision success score
    """


    score = 50



    performance_gap = actual_return - expected_return



    if performance_gap > 0:

        score += 25


    elif performance_gap < 0:

        score -= 20



    if confidence >= 90:

        score += 15


    elif confidence < 60:

        score -= 10



    return max(

        0,

        min(

            100,

            score

        )

    )





def attribute_performance(
    stock_selection,
    market_timing,
    sector_rotation
):
    """
    Breaks performance into sources
    """


    total = (

        stock_selection

        +

        market_timing

        +

        sector_rotation

    )



    return {


        "stock_selection":

        stock_selection,


        "market_timing":

        market_timing,


        "sector_rotation":

        sector_rotation,


        "total_attribution":

        total

    }





def generate_learning_signal(
    decision_quality_score
):
    """
    Generates strategy learning feedback
    """


    if decision_quality_score >= 85:

        return "INCREASE_CONFIDENCE"



    elif decision_quality_score >= 60:

        return "MAINTAIN_STRATEGY"



    return "REVIEW_PATTERN"





def analyze_investment_decision(
    ticker,
    decision,
    expected_return,
    actual_return,
    confidence,
    stock_selection,
    market_timing,
    sector_rotation
):
    """
    Main performance attribution engine
    """


    outcome = analyze_outcome(

        expected_return,

        actual_return

    )


    quality_score = calculate_decision_quality(

        expected_return,

        actual_return,

        confidence

    )


    attribution = attribute_performance(

        stock_selection,

        market_timing,

        sector_rotation

    )


    learning_signal = generate_learning_signal(

        quality_score

    )



    return {


        "engine":

        "V10.9 Performance Attribution & Learning Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "decision":

        decision,


        "outcome":

        outcome,


        "decision_quality_score":

        quality_score,


        "performance_attribution":

        attribution,


        "learning_signal":

        learning_signal

    }
