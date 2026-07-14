"""
V10.9.5 AI CIO Adaptive Strategy Controller

Purpose:
Apply self optimization results into
future AI CIO decision behavior.

Functions:
- Strategy mode adaptation
- Alpha threshold update
- Risk mode adjustment
- Position sizing optimization
"""


from datetime import datetime



def determine_strategy_behavior(
    optimization_score,
    dominant_signal
):
    """
    Determines adaptive investment behavior
    """


    if optimization_score >= 85:

        if dominant_signal == "FUNDAMENTAL":

            return "FUNDAMENTAL_HIGH_CONVICTION"


        elif dominant_signal == "TECHNICAL":

            return "TECHNICAL_MOMENTUM_MODE"


        return "ADAPTIVE_HIGH_CONVICTION"



    elif optimization_score >= 60:

        return "BALANCED_MODE"



    return "DEFENSIVE_MODE"





def update_alpha_threshold(
    current_threshold,
    optimized_threshold
):
    """
    Updates alpha entry threshold
    """


    if optimized_threshold:

        return optimized_threshold



    return current_threshold





def determine_risk_mode(
    risk_adjustment
):
    """
    Determines risk behavior
    """


    if risk_adjustment == "REDUCE_CONCENTRATION":

        return "CONTROLLED_RISK"



    elif risk_adjustment == "ALLOW_MORE_FLEXIBILITY":

        return "FLEXIBLE_RISK"



    return "NORMAL_RISK"





def optimize_position_size(
    current_position_limit,
    risk_mode
):
    """
    Adjusts position sizing rules
    """


    if risk_mode == "CONTROLLED_RISK":

        return max(

            5,

            current_position_limit - 3

        )



    elif risk_mode == "FLEXIBLE_RISK":

        return min(

            20,

            current_position_limit + 3

        )



    return current_position_limit





def generate_adaptive_strategy(
    optimization_score,
    dominant_signal,
    current_alpha_threshold,
    optimized_alpha_threshold,
    risk_adjustment,
    current_position_limit
):
    """
    Main adaptive strategy controller
    """


    strategy_behavior = determine_strategy_behavior(

        optimization_score,

        dominant_signal

    )


    alpha_threshold = update_alpha_threshold(

        current_alpha_threshold,

        optimized_alpha_threshold

    )


    risk_mode = determine_risk_mode(

        risk_adjustment

    )


    position_limit = optimize_position_size(

        current_position_limit,

        risk_mode

    )



    return {


        "engine":

        "V10.9.5 AI CIO Adaptive Strategy Controller",


        "timestamp":

        datetime.utcnow().isoformat(),


        "optimization_score":

        optimization_score,


        "strategy_behavior":

        strategy_behavior,


        "alpha_threshold":

        alpha_threshold,


        "risk_mode":

        risk_mode,


        "max_position_limit":

        position_limit,


        "controller_status":

        "ACTIVE"

    }
