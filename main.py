"""
V5.2 Global Market Intelligence Scanner
Main Controller
"""

import os
import json
import csv
from datetime import datetime


PORTFOLIO_FILE = "data/portfolio.csv"
UNIVERSE_FILE = "data/us_universe.json"
OUTPUT_FILE = "docs/latest.json"


def load_portfolio():

    portfolio = []

    if not os.path.exists(PORTFOLIO_FILE):
        return portfolio

    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:
            portfolio.append(row)

    return portfolio


def load_universe():

    if not os.path.exists(UNIVERSE_FILE):
        return []

    with open(
        UNIVERSE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def generate_intelligence(portfolio):

    results = []

    for stock in portfolio:

        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )

        item = {

            "ticker": ticker,

            "decision": {

                "score": 50,
                "action": "HOLD",
                "confidence": "MEDIUM"

            },

            "signals": {

                "theme_strength": 50,
                "sector_strength": 50,
                "catalyst": 50

            },

            "status": "MONITOR"

        }

        results.append(item)


    return results



def run_scanner():

    portfolio = load_portfolio()

    universe = load_universe()


    print(
        f"Portfolio loaded: {len(portfolio)} stocks"
    )


    print(
        f"Universe loaded: {len(universe)} stocks"
    )


    intelligence = generate_intelligence(
        portfolio
    )


    output = {

        "generated":
            datetime.utcnow().isoformat(),

        "portfolio":
            intelligence,

        "scanner_version":
            "V5.2"

    }


    os.makedirs(
        "docs",
        exist_ok=True
    )


    with open(
        OUTPUT_FILE,
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
        "V5.2 Scanner completed successfully"
    )



if __name__ == "__main__":

    run_scanner()
