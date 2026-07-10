"""
V3 Portfolio Selection Engine

Selects top opportunities from all sectors.
Avoids over concentration.
Creates ranked TOP 10 list.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class PortfolioCandidate:
    ticker: str
    sector: str
    score: float



def diversify_selection(
    candidates: List[PortfolioCandidate],
    top_n: int = 10,
    max_sector_weight: int = 3
):

    selected = []
    sector_count = {}

    ranked = sorted(
        candidates,
        key=lambda x: x.score,
        reverse=True
    )

    for stock in ranked:

        current_sector = sector_count.get(
            stock.sector,
            0
        )

        if current_sector >= max_sector_weight:
            continue

        selected.append(stock)

        sector_count[stock.sector] = (
            current_sector + 1
        )

        if len(selected) >= top_n:
            break

    return selected



def generate_top10(candidates):

    return diversify_selection(
        candidates,
        top_n=10,
        max_sector_weight=3
    )
