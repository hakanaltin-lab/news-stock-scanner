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



def generate_portfolio_intelligence(portfolio):

    intelligence = []

    for stock in portfolio:

        intelligence.append({

            "ticker": stock.get("ticker"),

            "decision": {

                "score": 50,

                "action": "HOLD",

                "confidence": "MEDIUM"

            },

            "signals": {

                "theme_strength": 50,

                "sector_strength": 45,

                "catalyst": 50

            },

            "position": {

                "shares": stock.get("shares"),

                "avg_cost": stock.get("avg_cost"),

                "sector": stock.get("sector"),

                "theme": stock.get("theme"),

                "status": stock.get("status")

            }

        })

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
