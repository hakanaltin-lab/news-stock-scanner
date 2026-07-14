"""
V10.5.1 Analyst Consensus Fusion Engine

Purpose:
Integrate analyst consensus intelligence
into AI CIO decision pipeline.

Functions:
- Consensus score adjustment
- Alpha score update
- CIO confidence update
- Analyst conviction signal
"""


from datetime import datetime



def calculate_alpha_adjustment(
    consensus_score
):
    """
    Adjust alpha based on analyst consensus
    """


    if consensus_score >= 85:

        return 8


    elif consensus_score >= 70:

        return 5


    elif consensus_score >= 50:

        return 0


    else:

        return -8





def calculate_confidence_adjustment(
    consensus_score
):
    """
    Adjust CIO confidence
    """


    if consensus_score >= 85:

        return 10


    elif consensus_score >= 70:

        return 5


    elif consensus_score < 50:

        return -10


    return 0





def determine_analyst_signal(
    confidence_adjustment
):
    """
    Creates analyst conviction signal
    """


    if confidence_adjustment >= 5:

        return "INCREASE_CONVICTION"


    elif confidence_adjustment <= -5:

        return "REDUCE_CONVICTION"


    return "MAINTAIN_CONVICTION"





def fuse_analyst_consensus(
    ticker,
    current_alpha_score,
    current_cio_confidence,
    consensus_score
):
    """
    Main analyst fusion function
    """


    alpha_adjustment = calculate_alpha_adjustment(

        consensus_score

    )


    confidence_adjustment = calculate_confidence_adjustment(

        consensus_score

    )



    updated_alpha = max(

        0,

        min(

            100,

            current_alpha_score + alpha_adjustment

        )

    )



    updated_confidence = max(

        0,

        min(

            100,

            current_cio_confidence + confidence_adjustment

        )

    )



    return {


        "engine":

        "V10.5.1 Analyst Consensus Fusion Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "consensus_score":

        consensus_score,


        "alpha_adjustment":

        alpha_adjustment,


        "updated_alpha_score":

        updated_alpha,


        "confidence_adjustment":

        confidence_adjustment,


        "updated_cio_confidence":

        updated_confidence,


        "analyst_signal":

        determine_analyst_signal(

            confidence_adjustment

        )

    }
