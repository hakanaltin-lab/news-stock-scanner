"""
V5.7 News Intelligence Engine

Purpose:
Analyze company news and detect market catalysts.

Output:
- news_score
- detected_events
"""


def analyze_news(ticker, news_items=None):

    if news_items is None:
        news_items = []


    score = 50

    events = []


    positive_signals = {

        "earnings beat": 10,
        "revenue growth": 8,
        "guidance raise": 10,
        "ai": 8,
        "artificial intelligence": 8,
        "partnership": 7,
        "contract": 7,
        "approval": 10,
        "upgrade": 6,
        "buyback": 5,
        "insider buying": 5

    }


    negative_signals = {

        "earnings miss": -10,
        "guidance cut": -10,
        "downgrade": -6,
        "lawsuit": -8,
        "investigation": -10,
        "dilution": -8,
        "delay": -5,
        "recall": -8

    }



    for item in news_items:


        text = item.lower()



        for keyword, value in positive_signals.items():

            if keyword in text:

                score += value

                events.append(
                    keyword
                )



        for keyword, value in negative_signals.items():

            if keyword in text:

                score += value

                events.append(
                    keyword
                )



    score = max(
        0,
        min(
            score,
            100
        )
    )


    return {

        "ticker": ticker,

        "news_score": score,

        "events": events

    }
