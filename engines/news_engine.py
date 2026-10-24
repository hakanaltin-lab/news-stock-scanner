"""
V6.1 News Intelligence Engine

Purpose:
- Retrieve live company news
- Analyze headlines
- Detect positive / negative catalysts
- Generate dynamic news score
"""

import re
import yfinance as yf


def fetch_live_news(ticker, count=10):
    """
    Retrieve recent company news from Yahoo Finance.

    Returns a list of normalized text items.
    If no news is available, returns an empty list.
    """

    try:
        raw_news = []

        # Primary source: yfinance Search API
        try:
            search = yf.Search(
                ticker,
                max_results=1,
                news_count=count,
                lists_count=0,
                recommended=0,
                raise_errors=False
            )

            raw_news = search.news or []

        except Exception:
            raw_news = []

        # Fallback source: ticker news feed
        if not raw_news:

            try:
                stock = yf.Ticker(ticker)
                raw_news = stock.news or []

            except Exception:
                raw_news = []

        news_items = []

        for article in raw_news[:count]:

            if not isinstance(article, dict):
                continue

            related = article.get(
                "relatedTickers",
                []
            )

            if related and ticker not in related:
                continue

            title = article.get(
                "title",
                ""
            )

            summary = article.get(
                "summary",
                ""
            )

            # Yahoo may return nested content
            content = article.get("content")

            if isinstance(content, dict):

                title = (
                    title
                    or content.get(
                        "title",
                        ""
                    )
                )

                summary = (
                    summary
                    or content.get(
                        "summary",
                        ""
                    )
                    or content.get(
                        "description",
                        ""
                    )
                )

            text = f"{title} {summary}".strip()

            if text:
                news_items.append(text)

        return news_items

    except Exception as e:

        print(
            f"News retrieval error for {ticker}: {e}"
        )

        return []


def keyword_found(text, keyword):
    """
    Safer catalyst keyword matching.

    Prevents 'ai' from matching unrelated words
    such as said, gain, raise, etc.
    """

    if keyword == "ai":

        return (
            re.search(
                r"\bai\b",
                text
            )
            is not None
        )

    return keyword in text


def analyze_news(ticker, news_items=None):
    """
    Analyze recent company news.

    Returns:
    - news_score
    - detected events
    - article count
    - data quality

    Neutral baseline = 50.
    """

    if news_items is None:

        news_items = fetch_live_news(
            ticker,
            count=10
        )

    score = 50

    events = []

    detected = set()

    positive_signals = {

        "earnings beat": 10,

        "beats estimates": 10,

        "revenue growth": 8,

        "guidance raise": 10,

        "raises guidance": 10,

        "ai": 8,

        "artificial intelligence": 8,

        "partnership": 7,

        "contract": 7,

        "contract award": 8,

        "approval": 10,

        "upgrade": 6,

        "price target raised": 6,

        "buyback": 5,

        "insider buying": 5
    }

    negative_signals = {

        "earnings miss": -10,

        "misses estimates": -10,

        "guidance cut": -10,

        "cuts guidance": -10,

        "downgrade": -6,

        "price target cut": -6,

        "lawsuit": -8,

        "investigation": -10,

        "dilution": -8,

        "delay": -5,

        "recall": -8
    }

    for item in news_items:

        text = str(item).lower()

        for keyword, value in positive_signals.items():

            if (
                keyword not in detected
                and keyword_found(
                    text,
                    keyword
                )
            ):

                score += value

                events.append(
                    keyword
                )

                detected.add(
                    keyword
                )

        for keyword, value in negative_signals.items():

            if (
                keyword not in detected
                and keyword_found(
                    text,
                    keyword
                )
            ):

                score += value

                events.append(
                    keyword
                )

                detected.add(
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

        "events": events,

        "article_count": len(
            news_items
        ),

        "data_quality":
            "LIVE"
            if news_items
            else "NO_NEWS"
    }
