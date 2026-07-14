"""
V10.3.1 Earnings Fusion Integration Engine

Purpose:
Connect earnings intelligence with
AI CIO decision pipeline.

Functions:
- Earnings impact fusion
- Alpha adjustment
- CIO confidence update
- Investment committee input
"""


from datetime import datetime



def calculate_alpha_adjustment(
    earnings_quality_score
):
    """
    Adjust alpha score based on earnings
    """


    if earnings_quality_score >= 85:

        return 8


    elif earnings_quality_score >= 70:

        return 5


    elif earnings_quality_score >= 50:

        return 0


    else:

        return -8





def calculate_confidence_adjustment(
    earnings_impact
):
    """
    Adjust CIO confidence
    """


    if earnings_impact == "STRONG_POSITIVE":

        return 10


    elif earnings_impact == "POSITIVE":

        return 5


    elif earnings_impact == "NEGATIVE":

        return -10


    return 0





def determine_cio_action(
    confidence_change
):
    """
    Creates CIO action
    """


    if confidence_change >= 5:

        return "INCREASE_CONVICTION"


    elif confidence_change <= -5:

        return "REDUCE_CONVICTION"


    return "MAINTAIN_CONVICTION"





def fuse_earnings_signal(
    ticker,
    current_alpha_score,
    current_cio_confidence,
    earnings_quality_score,
    earnings_impact
):
    """
    Main earnings fusion function
    """


    alpha_change = calculate_alpha_adjustment(

        earnings_quality_score

    )


    confidence_change = calculate_confidence_adjustment(

        earnings_impact

    )


    updated_alpha = max(

        0,

        min(

            100,

            current_alpha_score + alpha_change

        )

    )


    updated_confidence = max(

        0,

        min(

            100,

            current_cio_confidence + confidence_change

        )

    )



    return {


        "engine":

        "V10.3.1 Earnings Fusion Integration",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "earnings_quality_score":

        earnings_quality_score,


        "alpha_adjustment":

        alpha_change,


        "updated_alpha_score":

        updated_alpha,


        "confidence_adjustment":

        confidence_change,


        "updated_cio_confidence":

        updated_confidence,


        "cio_action":

        determine_cio_action(

            confidence_change

        )

    }
