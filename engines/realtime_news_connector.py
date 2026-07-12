"""
V10.2 Real-Time News & Event Data Connector Layer

Purpose:
Normalize real-time news and market events
for AI CIO decision system.

Functions:
- News normalization
- Event classification
- Impact scoring
- CIO priority routing
"""


from datetime import datetime



def classify_event_type(
    headline,
    keywords
):
    """
    Classifies market event type
    """


    headline_lower = headline.lower()


    for keyword in keywords:

        if keyword.lower() in headline_lower:

            return keyword


    return "GENERAL_NEWS"





def calculate_event_impact(
    sentiment,
    event_type
):
    """
    Calculates event importance
    """


    high_impact_events = [

        "earnings",

        "contract",

        "partnership",

        "regulation",

        "acquisition"

    ]


    if event_type in high_impact_events:

        return "HIGH"



    if sentiment in [

        "POSITIVE",

        "NEGATIVE"

    ]:

        return "MEDIUM"



    return "LOW"





def normalize_news_event(
    ticker,
    headline,
    source,
    sentiment,
    event_type
):
    """
    Creates standardized news object
    """


    impact = calculate_event_impact(

        sentiment,

        event_type

    )



    return {


        "engine":

        "V10.2 Real-Time News Connector",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "headline":

        headline,


        "source":

        source,


        "sentiment":

        sentiment,


        "event_type":

        event_type,


        "impact":

        impact

    }





def prioritize_news_event(
    news_event
):
    """
    Routes important events
    """


    impact = news_event.get(

        "impact",

        "LOW"

    )


    if impact == "HIGH":

        action = "IMMEDIATE_CIO_REVIEW"



    elif impact == "MEDIUM":

        action = "WATCH"



    else:

        action = "IGNORE"




    return {


        "ticker":

        news_event.get(
            "ticker"
        ),


        "priority":

        impact,


        "routing":

        action

    }





def create_news_pipeline(
    events
):
    """
    Creates CIO news pipeline
    """


    pipeline = []



    for event in events:


        pipeline.append(

            prioritize_news_event(

                event

            )

        )



    return {


        "engine":

        "V10.2 News Event Pipeline",


        "timestamp":

        datetime.utcnow().isoformat(),


        "events":

        pipeline,


        "status":

        "READY"

    }
