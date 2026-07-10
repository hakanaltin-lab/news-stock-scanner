"""
V5.6 Catalyst Intelligence Engine

Purpose:
Detect stock catalysts and generate catalyst score.

Inputs:
- ticker
- news keywords
- event signals

Output:
- catalyst_score
- catalyst_type
"""


def analyze_catalyst(ticker, news_items=None):

    score = 50
    catalysts = []

    if news_items is None:
        news_items = []


    positive_keywords = [
        "earnings beat",
        "revenue growth",
        "guidance raise",
        "contract",
        "partnership",
        "approval",
        "ai",
        "artificial intelligence",
        "upgrade",
        "buy rating"
    ]


    negative_keywords = [
        "earnings miss",
        "guidance cut",
        "downgrade",
        "investigation",
        "lawsuit",
        "recall",
        "delay"
    ]


    for news in news_items:

        text = news.lower()


        for word in positive_keywords:
            if word in text:
                score += 5
                catalysts.append(word)


        for word in negative_keywords:
            if word in text:
                score -= 5
                catalysts.append(word)


    if score > 100:
        score = 100

    if score < 0:
        score = 0


    return {
        "ticker": ticker,
        "catalyst_score": score,
        "catalysts": catalysts
    }
