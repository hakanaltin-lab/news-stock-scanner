"""
V6.2 Live Catalyst Intelligence Engine

Purpose:
- Retrieve live company news
- Detect important stock catalysts
- Score positive / negative catalysts
- Generate dynamic catalyst score
"""

import re

from engines.news_engine import fetch_live_news


def keyword_found(text, keyword):
    """
    Match catalyst keywords safely.
    Prevents short words such as 'ai' from matching
    inside unrelated words.
    """

    if keyword == "ai":
        return re.search(r"\bai\b", text) is not None

    return keyword in text


def analyze_catalyst(ticker, news_items=None):

    # If no news was passed from main.py,
    # retrieve live news directly.
    if news_items is None:
        news_items = fetch_live_news(
            ticker,
            count=10
        )

    score = 50

    catalysts = []

    detected = set()

    positive_catalysts = {

        "earnings beat": 10,
        "beats estimates": 10,
        "revenue growth": 8,

        "guidance raise": 10,
        "raises guidance": 10,

        "contract": 7,
        "contract award": 8,

        "partnership": 7,

        "approval": 10,

        "ai": 6,
        "artificial intelligence": 6,

        "upgrade": 6,
        "price target raised": 6,

        "buy rating": 6,

        "buyback": 5,

        "insider buying": 5
    }

    negative_catalysts = {

        "earnings miss": -10,
        "misses estimates": -10,

        "guidance cut": -10,
        "cuts guidance": -10,

        "downgrade": -6,
        "price target cut": -6,

        "investigation": -10,

        "lawsuit": -8,

        "dilution": -8,

        "recall": -8,

        "delay": -5
    }


    for item in news_items:

        text = str(item).lower()

        for keyword, value in positive_catalysts.items():

            if (
                keyword not in detected
                and keyword_found(text, keyword)
            ):

                score += value

                catalysts.append(
                    {
                        "type": "POSITIVE",
                        "catalyst": keyword,
                        "impact": value
                    }
                )

                detected.add(keyword)


        for keyword, value in negative_catalysts.items():

            if (
                keyword not in detected
                and keyword_found(text, keyword)
            ):

                score += value

                catalysts.append(
                    {
                        "type": "NEGATIVE",
                        "catalyst": keyword,
                        "impact": value
                    }
                )

                detected.add(keyword)


    score = max(
        0,
        min(
            score,
            100
        )
    )


    if score >= 65:

        catalyst_signal = "POSITIVE"

    elif score <= 35:

        catalyst_signal = "NEGATIVE"

    else:

        catalyst_signal = "NEUTRAL"


    return {

        "ticker": ticker,

        "catalyst_score": score,

        "catalyst_signal":
            catalyst_signal,

        "catalysts":
            catalysts,

        "article_count":
            len(news_items),

        "data_quality":
            "LIVE"
            if news_items
            else "NO_NEWS"
    }
