"""
V3 News Catalyst Engine

Purpose:
Convert news headlines into investment catalysts.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class NewsImpact:
    headline: str
    theme: str
    sentiment: str
    affected_tickers: List[str]
    catalyst_score: float


POSITIVE_WORDS = [
    "beats",
    "upgrade",
    "partnership",
    "contract",
    "growth",
    "strong demand",
    "record revenue",
    "ai",
    "expansion",
    "approval",
]

NEGATIVE_WORDS = [
    "miss",
    "downgrade",
    "investigation",
    "lawsuit",
    "weak demand",
    "cut forecast",
    "decline",
    "warning",
]


def analyze_news(
    headline: str,
    theme: str,
    tickers: List[str],
) -> NewsImpact:

    text = headline.lower()

    positive_score = sum(
        1 for word in POSITIVE_WORDS if word in text
    )

    negative_score = sum(
        1 for word in NEGATIVE_WORDS if word in text
    )

    if positive_score > negative_score:
        sentiment = "POSITIVE"
        score = min(100, 60 + positive_score * 8)

    elif negative_score > positive_score:
        sentiment = "NEGATIVE"
        score = max(0, 40 - negative_score * 8)

    else:
        sentiment = "NEUTRAL"
        score = 50

    return NewsImpact(
        headline=headline,
        theme=theme,
        sentiment=sentiment,
        affected_tickers=tickers,
        catalyst_score=score,
    )
