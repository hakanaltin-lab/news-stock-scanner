"""
V9.7 Autonomous News Intelligence Fusion Engine

Purpose:
Convert market news into investment intelligence.

Functions:
- News sentiment analysis
- Catalyst impact scoring
- Risk news detection
- CIO confidence adjustment
"""


from datetime import datetime



def analyze_news_sentiment(
    news_items
):
    """
    Calculates overall news impact
    """


    positive_score = 0

    negative_score = 0



    for news in news_items:


        sentiment = news.get(
            "sentiment",
            "NEUTRAL"
        )


        impact = news.get(
            "impact",
            "LOW"
        )



        if sentiment == "POSITIVE":


            if impact == "HIGH":

                positive_score += 30


            elif impact == "MEDIUM":

                positive_score += 20


            else:

                positive_score += 10



        elif sentiment == "NEGATIVE":


            if impact == "HIGH":

                negative_score += 30


            elif impact == "MEDIUM":

                negative_score += 20


            else:

                negative_score += 10




    net_score = positive_score - negative_score



    if net_score >= 20:

        view = "POSITIVE"



    elif net_score <= -20:

        view = "NEGATIVE"



    else:

        view = "NEUTRAL"



    return {


        "news_view":

        view,


        "positive_score":

        positive_score,


        "negative_score":

        negative_score,


        "net_score":

        net_score

    }





def calculate_confidence_adjustment(
    net_score
):
    """
    Adjusts CIO confidence based on news
    """


    if net_score >= 30:

        return 10



    elif net_score >= 15:

        return 5



    elif net_score <= -30:

        return -10



    elif net_score <= -15:

        return -5



    return 0





def generate_news_impact(
    ticker,
    news_items,
    current_cio_score
):
    """
    Main news fusion engine
    """


    sentiment = analyze_news_sentiment(

        news_items

    )



    adjustment = calculate_confidence_adjustment(

        sentiment["net_score"]

    )



    new_cio_score = max(

        0,

        min(

            100,

            current_cio_score + adjustment

        )

    )



    if adjustment > 0:

        action = "INCREASE_CONVICTION"



    elif adjustment < 0:

        action = "REDUCE_CONVICTION"



    else:

        action = "MAINTAIN_CONVICTION"




    return {


        "engine":

        "V9.7 News Intelligence Fusion Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "news_analysis":

        sentiment,


        "confidence_adjustment":

        adjustment,


        "updated_cio_score":

        new_cio_score,


        "cio_action":

        action

    }
