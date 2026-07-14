"""
V10.8.4 CIO Alert & Notification Engine

Purpose:
Convert portfolio monitoring signals into
CIO actionable alerts.

Functions:
- Alert priority classification
- Alert type detection
- Action recommendation
- Dashboard notification output
"""


from datetime import datetime



def classify_alert_priority(
    price_status,
    thesis_status,
    portfolio_risk
):
    """
    Determines alert severity
    """


    if (

        price_status == "HIGH_RISK"

        or

        thesis_status == "THESIS_REVIEW"

        or

        portfolio_risk == "HIGH"

    ):

        return "HIGH"



    if (

        price_status == "REVIEW"

        or

        portfolio_risk == "ELEVATED"

    ):

        return "MEDIUM"



    return "LOW"





def identify_alert_type(
    price_status,
    thesis_status,
    portfolio_risk
):
    """
    Determines alert category
    """


    if thesis_status == "THESIS_REVIEW":

        return "THESIS_RISK"



    if price_status in [

        "HIGH_RISK",

        "REVIEW"

    ]:

        return "PRICE_RISK"



    if portfolio_risk in [

        "HIGH",

        "ELEVATED"

    ]:

        return "PORTFOLIO_RISK"



    return "MONITOR"





def recommend_cio_action(
    priority,
    alert_type
):
    """
    Creates CIO recommendation
    """


    if priority == "HIGH":

        if alert_type == "THESIS_RISK":

            return "REVIEW_POSITION"


        return "REDUCE_RISK"



    if priority == "MEDIUM":

        return "MONITOR_POSITION"



    return "NO_ACTION"





def generate_cio_alert(
    ticker,
    price_status,
    thesis_status,
    portfolio_risk
):
    """
    Main CIO alert function
    """


    priority = classify_alert_priority(

        price_status,

        thesis_status,

        portfolio_risk

    )


    alert_type = identify_alert_type(

        price_status,

        thesis_status,

        portfolio_risk

    )


    action = recommend_cio_action(

        priority,

        alert_type

    )



    return {


        "engine":

        "V10.8.4 CIO Alert & Notification Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "priority":

        priority,


        "alert_type":

        alert_type,


        "recommendation":

        action,


        "dashboard_status":

        "UPDATED"

    }
