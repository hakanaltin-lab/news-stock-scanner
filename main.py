"""
V5.3 Global Market Intelligence Scanner

Main Controller

Connects:
- Portfolio Engine
- Market Data Engine
- Scoring Logic
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



def generate_score(snapshot, signal):

    score = 50


    momentum = snapshot.get("momentum", 0)
    vwap = snapshot.get("vwap", 0)
    price = snapshot.get("last_price", 0)


    # Momentum factor

    if momentum > 3:
        score += 20

    elif momentum < -3:
        score -= 20



    # VWAP factor

    if price and vwap:

        if price > vwap:
            score += 10

        else:
            score -= 10



    # Signal factor

    if signal == "BULLISH":
        score += 15

    elif signal == "BEARISH":
        score -= 15



    if score > 100:
        score = 100

    if score < 0:
        score = 0


    return score



def get_action(score):

    if score >= 75:
        return "ADD"

    elif score >= 60:
        return "WATCH"

    elif score >= 35:
        return "HOLD"

    else:
        return "AVOID"



def generate_intelligence(portfolio):

    results = []


    for stock in portfolio:

        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )


        # Temporary market input layer
        # Real API connection will be added next

        prices = [
            100,
            101
        ]

        volumes = [
            100000,
            120000
        ]


        snapshot = build_market_snapshot(
            ticker,
            prices,
            volumes
        )


        signal = get_market_signal(
            snapshot
        )


        score = generate_score(
            snapshot,
            signal
        )


        item = {

            "ticker": ticker,

            "decision": {

                "score": score,

                "action": get_action(score),

                "confidence": "MEDIUM"

            },


            "market": snapshot,


            "signal": signal,


            "status": "ACTIVE"

        }


        results.append(item)



    return results



def run_scanner():

    portfolio = load_portfolio()


    intelligence = generate_intelligence(
        portfolio
    )


    output = {

        "generated":

            datetime.utcnow().isoformat(),


        "scanner_version":

            "V5.3",


        "portfolio":

            intelligence

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
        "V5.3 Scanner completed successfully"
    )



if __name__ == "__main__":

    run_scanner()
