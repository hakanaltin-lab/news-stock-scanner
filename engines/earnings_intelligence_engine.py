"""
V10.3 Earnings Intelligence Engine

Purpose:
Analyze company earnings performance
and convert results into CIO investment signals.

Functions:
- EPS surprise analysis
- Revenue surprise analysis
- Guidance assessment
- Earnings quality scoring
- Investment impact
"""


from datetime import datetime



def calculate_eps_surprise(
    expected_eps,
    actual_eps
):
    """
    Calculates EPS surprise percentage
    """


    if expected_eps == 0:

        return 0



    return round(

        (

            (actual_eps - expected_eps)

            /

            expected_eps

        ) * 100,

        2

    )





def calculate_revenue_surprise(
    expected_revenue,
    actual_revenue
):
    """
    Calculates revenue surprise percentage
    """


    if expected_revenue == 0:

        return 0



    return round(

        (

            (actual_revenue - expected_revenue)

            /

            expected_revenue

        ) * 100,

        2

    )





def analyze_guidance(
    guidance
):
    """
    Evaluates management guidance
    """


    if guidance == "RAISED":

        return 30



    elif guidance == "LOWERED":

        return -30



    return 0





def calculate_earnings_quality_score(
    eps_surprise,
    revenue_surprise,
    guidance_score
):
    """
    Creates earnings quality score
    """


    score = 50


    if eps_surprise > 10:

        score += 20


    elif eps_surprise < -10:

        score -= 20



    if revenue_surprise > 5:

        score += 15


    elif revenue_surprise < -5:

        score -= 15



    score += guidance_score



    return max(

        0,

        min(

            100,

            score

        )

    )





def determine_earnings_impact(
    quality_score
):
    """
    Converts score into investment impact
    """


    if quality_score >= 80:

        return "STRONG_POSITIVE"



    elif quality_score >= 60:

        return "POSITIVE"



    elif quality_score >= 40:

        return "NEUTRAL"



    return "NEGATIVE"





def analyze_earnings(
    ticker,
    expected_eps,
    actual_eps,
    expected_revenue,
    actual_revenue,
    guidance
):
    """
    Main earnings intelligence function
    """


    eps_surprise = calculate_eps_surprise(

        expected_eps,

        actual_eps

    )


    revenue_surprise = calculate_revenue_surprise(

        expected_revenue,

        actual_revenue

    )


    guidance_score = analyze_guidance(

        guidance

    )


    quality_score = calculate_earnings_quality_score(

        eps_surprise,

        revenue_surprise,

        guidance_score

    )


    return {


        "engine":

        "V10.3 Earnings Intelligence Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "eps_surprise":

        eps_surprise,


        "revenue_surprise":

        revenue_surprise,


        "guidance":

        guidance,


        "earnings_quality_score":

        quality_score,


        "investment_impact":

        determine_earnings_impact(

            quality_score

        )

    }
