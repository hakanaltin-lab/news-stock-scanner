"""
V10.9.1 Learning Fusion Engine

Purpose:
Feed performance learning back into
AI CIO decision system.

Functions:
- Pattern evaluation
- Alpha adjustment
- Confidence update
- Strategy feedback
"""


from datetime import datetime



def evaluate_learning_pattern(
    success_rate
):
    """
    Evaluates historical pattern success
    """


    if success_rate >= 80:

        return "HIGH_CONFIDENCE_PATTERN"



    elif success_rate >= 60:

        return "VALID_PATTERN"



    return "WEAK_PATTERN"





def calculate_alpha_learning_adjustment(
    success_rate
):
    """
    Adjusts alpha based on learned patterns
    """


    if success_rate >= 80:

        return 5



    elif success_rate >= 60:

        return 2



    return -3





def calculate_confidence_adjustment(
    learning_signal
):
    """
    Updates CIO confidence
    """


    if learning_signal == "SUCCESSFUL":

        return 5



    elif learning_signal == "FAILED":

        return -5



    return 0





def determine_learning_action(
    pattern_quality
):
    """
    Creates strategy action
    """


    if pattern_quality == "HIGH_CONFIDENCE_PATTERN":

        return "INCREASE_CONVICTION"



    elif pattern_quality == "VALID_PATTERN":

        return "MAINTAIN_STRATEGY"



    return "REVIEW_PATTERN"





def fuse_learning_feedback(
    ticker,
    current_alpha,
    current_confidence,
    pattern,
    success_rate,
    learning_signal
):
    """
    Main learning fusion function
    """


    pattern_quality = evaluate_learning_pattern(

        success_rate

    )


    alpha_adjustment = calculate_alpha_learning_adjustment(

        success_rate

    )


    confidence_adjustment = calculate_confidence_adjustment(

        learning_signal

    )



    updated_alpha = max(

        0,

        min(

            100,

            current_alpha + alpha_adjustment

        )

    )



    updated_confidence = max(

        0,

        min(

            100,

            current_confidence + confidence_adjustment

        )

    )



    return {


        "engine":

        "V10.9.1 Learning Fusion Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "pattern":

        pattern,


        "success_rate":

        success_rate,


        "pattern_quality":

        pattern_quality,


        "alpha_adjustment":

        alpha_adjustment,


        "updated_alpha":

        updated_alpha,


        "confidence_adjustment":

        confidence_adjustment,


        "updated_confidence":

        updated_confidence,


        "strategy_action":

        determine_learning_action(

            pattern_quality

        )

    }
