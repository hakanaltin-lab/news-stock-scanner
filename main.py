"""
V4 Market Intelligence Scanner

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_portfolio():
    """
    Load user's current portfolio
    """

    path = os.path.join(BASE_DIR, "data", "portfolio.csv")

    portfolio = []

    if not os.path.exists(path):
        return portfolio

    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            portfolio.append(
                {
                    "ticker": row["ticker"],
                    "shares": float(row["shares"]),
                    "cost": float(row["cost"])
                }
            )

    return portfolio


def load_universe():

    path = os.path.join(BASE_DIR, "data", "us_universe.json")

    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8") as file:
        return json.load(file)



def calculate_position_value(position):

    return position["shares"] * position["cost"]



def main():

    print("Starting Market Intelligence Scanner V4")

    scanner = MarketScanner()


    portfolio = load_portfolio()

    universe = load_universe()


    results = []


    for stock in universe:

        score = scanner.scan_stock(
            ticker=stock.get("ticker"),
            news_score=stock.get("news", 50),
            sector_score=stock.get("sector", 50),
            price_score=stock.get("price", 50),
            quality_score=stock.get("quality", 50),
            risk_score=stock.get("risk", 50)
        )


        results.append(score)



    output = {

        "created": datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),

        "portfolio": portfolio,

        "scanner_results": results

    }


    output_path = os.path.join(
        BASE_DIR,
        "data",
        "latest_scan.json"
    )


    with open(
        output_path,
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

    print(
        f"Portfolio positions: {len(portfolio)}"
    )

    print(
        f"Market candidates: {len(results)}"
    )



if __name__ == "__main__":

    main()
