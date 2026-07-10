"""
V5 Market Intelligence Scanner

Main execution layer

Reads:
- data/portfolio.csv
- data/us_universe.json

Creates:
- Portfolio analysis
- Market opportunity scan
- Dashboard data output
"""

import csv
import json
import os
from datetime import datetime

from scanner_core import MarketScanner


PORTFOLIO_FILE = "data/portfolio.csv"
UNIVERSE_FILE = "data/us_universe.json"


def load_portfolio():

    portfolio = []

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


def analyze_portfolio(portfolio):

    result = []

    for stock in portfolio:

        position_value = (
            stock["shares"] * stock["avg_cost"]
        )

        result.append(
            {
                "ticker": stock["ticker"],
                "shares": stock["shares"],
                "avg_cost": stock["avg_cost"],
                "sector": stock["sector"],
                "theme": stock["theme"],
                "status": stock["status"],
                "position_value": round(position_value, 2),
            }
        )

    return result


def run_scanner():

    print("Starting Market Intelligence Scanner V5")

    portfolio = load_portfolio()

    universe = load_universe()

    scanner = MarketScanner()

    print(
        f"Portfolio loaded: {len(portfolio)} stocks"
    )

    print(
        f"Universe loaded: {len(universe)} stocks"
    )

    portfolio_report = analyze_portfolio(
        portfolio
    )


    output = {

        "generated": datetime.utcnow().isoformat(),

        "portfolio": portfolio_report,

        "scanner_version": "V5"

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


    print("Scanner completed successfully")


if __name__ == "__main__":

    run_scanner()
