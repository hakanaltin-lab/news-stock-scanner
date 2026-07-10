"""
V5.4 Global Market Intelligence Scanner

Controller Layer

Connects:
- Portfolio Engine
- Market Data Engine
- Scoring Engine
- JSON Report Generator
"""

import os
import json
import csv
from datetime import datetime

from engines.market_data_engine import (
    build_market_snapshot,
    get_market_signal
)

from engines.scoring_engine import calculate_market_score


PORTFOLIO_FILE = "data/portfolio.csv"
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



def run_scanner():

    portfolio = load_portfolio()

    results = []


    for stock in portfolio:

        ticker = stock.get("ticker", "UNKNOWN")


        # Temporary market data layer
        prices = [100,101]
        volumes = [100000,120000]


        snapshot = build_market_snapshot(
            ticker,
            prices,
            volumes
        )


        signal = get_market_signal(snapshot)


        score = calculate_market_score(snapshot)


        result = {

            "ticker": ticker,

            "timestamp": datetime.utcnow().isoformat(),

            "market": snapshot,

            "signal": signal,

            "score": score,

            "status": "ACTIVE"

        }


        results.append(result)



    output = {

        "generated": datetime.utcnow().isoformat(),

        "scanner_version": "V5.4",

        "portfolio": results

    }



    os.makedirs("docs", exist_ok=True)


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2
        )


    print(
        "V5.4 Scanner completed successfully"
    )



if __name__ == "__main__":

    run_scanner()
