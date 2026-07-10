"""
V5.1 Global Market Intelligence Scanner

Portfolio Intelligence Engine
"""

import csv
import json
import os
from datetime import datetime


PORTFOLIO_FILE = "data/portfolio.csv"
UNIVERSE_FILE = "data/us_universe.json"


def load_portfolio():

    portfolio = []

    if not os.path.exists(PORTFOLIO_FILE):
        return portfolio

    with open(PORTFOLIO_FILE, newline="", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:

            portfolio.append(
                {
                    "ticker": row["ticker"],
                    "shares": int(row["shares"]),
                    "avg_cost": float(row["avg_cost"]),
                    "sector": row.get("sector", ""),
                    "theme": row.get("theme", ""),
                    "status": row.get("status", "HOLD"),
                }
            )

    return portfolio


def load_universe():

    if not os.path.exists(UNIVERSE_FILE):
        return []

    with open(UNIVERSE_FILE, encoding="utf-8") as file:

        return json.load(file)


def score_stock(stock):

    score = 50

    theme = stock.get("theme", "").lower()
    sector = stock.get("sector", "").lower()

    if "ai" in theme:
        score += 15

    if "semiconductor" in sector:
        score += 10

    if "cloud" in theme:
        score += 10

    if score >= 75:
        action = "ACCUMULATE"

    elif score >= 60:
        action = "WATCH"

    else:
        action = "HOLD"

    return score, action


def generate_portfolio_intelligence(portfolio):

    intelligence = []

    for stock in portfolio:

        ticker = stock["ticker"]

        score, action = score_stock(stock)

        intelligence.append(
            {
                "ticker": ticker,

                "decision": {
                    "score": score,
                    "action": action,
                    "confidence": "MEDIUM",
                },

                "signals": {
                    "theme_strength": score,
                    "sector_strength": score - 5,
                    "catalyst": score,
                },

                "position": {
                    "shares": stock["shares"],
                    "avg_cost": stock["avg_cost"],
                    "sector": stock["sector"],
                    "theme": stock["theme"],
                    "status": stock["status"],
                },
            }
        )

    return intelligence


def run_scanner():

    portfolio = load_portfolio()

    universe = load_universe()

    print(
        f"Portfolio loaded: {len(portfolio)} stocks"
    )

    print(
        f"Universe loaded: {len(universe)} stocks"
    )

    intelligence = generate_portfolio_intelligence(
        portfolio
    )
        output = {

        "generated": datetime.utcnow().isoformat(),

        "portfolio": intelligence,

        "scanner_version": "V5.1"

    }


    os.makedirs(
        "docs",
        exist_ok=True
    )


    with open(
        "docs/latest.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )


    print(
        "V5.1 Scanner completed successfully"
    )



if __name__ == "__main__":

    run_scanner()
