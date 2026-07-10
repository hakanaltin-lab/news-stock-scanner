"""
V3 Sector Momentum Engine

Purpose:
Rank market sectors before selecting individual stocks.
"""

from dataclasses import dataclass


@dataclass
class SectorScore:
    sector: str
    momentum: float
    catalyst: float
    final_score: float


def calculate_sector_score(
    momentum: float,
    catalyst: float
) -> float:

    return (
        momentum * 0.6 +
        catalyst * 0.4
    )


def rank_sectors():

    sectors = [
        ("Technology", 85, 90),
        ("Healthcare", 80, 85),
        ("Energy", 75, 88),
        ("Financials", 78, 82),
        ("Industrials", 82, 80),
    ]

    results = []

    for sector, momentum, catalyst in sectors:

        score = calculate_sector_score(
            momentum,
            catalyst
        )

        results.append(
            SectorScore(
                sector,
                momentum,
                catalyst,
                score
            )
        )

    return sorted(
        results,
        key=lambda x: x.final_score,
        reverse=True
    )
