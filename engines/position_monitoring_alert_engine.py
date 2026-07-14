"""
V10.8.3 Position Monitoring & Alert Engine

Purpose:
Monitor active positions and generate
risk alerts for AI CIO.

Functions:
- Price monitoring
- Drawdown detection
- Position performance analysis
- Thesis risk alerts
- CIO notifications
"""


from datetime import datetime



def calculate_drawdown(
    entry_price,
    current_price
):
    """
    Calculates position drawdown
    """


    if entry_price == 0:

        return 0



    return round(

        (

            (current_price - entry_price)

            /

            entry_price

        ) * 100,

        2

    )





def analyze_price_risk(
    drawdown
):
    """
    Evaluates price risk
    """


    if drawdown <= -15:

        return "HIGH_RISK"


    elif drawdown <= -8:

        return "REVIEW"


    return "NORMAL"





def analyze_position_performance(
    return_percent
):
    """
    Evaluates position performance
    """


    if return_percent >= 30:

        return "MONITOR_PROFIT"



    elif return_percent <= -10:

        return "LOSS_REVIEW"



    return "STABLE"





def analyze_thesis_status(
    earnings_status,
    analyst_status,
    news_status
):
    """
    Detects thesis deterioration
    """


    negative_signals = 0



    if earnings_status == "NEGATIVE":

        negative_signals += 1



    if analyst_status == "DOWNGRADE":

        negative_signals += 1



    if news_status == "NEGATIVE":

        negative_signals += 1



    if negative_signals >= 2:

        return "THESIS_REVIEW"



    return "THESIS_INTACT"





def generate_position_alert(
    ticker,
    entry_price,
    current_price,
    return_percent,
    earnings_status,
    analyst_status,
    news_status
):
    """
    Main position monitoring function
    """


    drawdown = calculate_drawdown(

        entry_price,

        current_price

    )


    price_status = analyze_price_risk(

        drawdown

    )


    performance_status = analyze_position_performance(

        return_percent

    )


    thesis_status = analyze_thesis_status(

        earnings_status,

        analyst_status,

        news_status

    )



    alert_level = "LOW"

    action = "HOLD"



    if price_status == "HIGH_RISK":

        alert_level = "HIGH"

        action = "REVIEW_POSITION"



    if thesis_status == "THESIS_REVIEW":

        alert_level = "HIGH"

        action = "REASSESS_THESIS"



    return {


        "engine":

        "V10.8.3 Position Monitoring & Alert Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "drawdown_percent":

        drawdown,


        "price_status":

        price_status,


        "performance_status":

        performance_status,


        "thesis_status":

        thesis_status,


        "alert_level":

        alert_level,


        "recommended_action":

        action

    }
