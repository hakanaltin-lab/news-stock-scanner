"""
V5.6 Global Market Intelligence Scanner

Controller Layer

Pipeline:

Portfolio Engine
        |
Market Data Engine
        |
Scoring Engine
        |
Catalyst Intelligence Engine
        |
Alpha Intelligence Engine
        |
JSON Report
"""

import os
import json
import csv
from datetime import datetime


from engines.market_data_engine import (
    build_market_snapshot,
    get_market_signal
)


from engines.scoring_engine import (
    calculate_market_score
)


from engines.catalyst_engine import (
    analyze_catalyst
)


from engines.alpha_intelligence_engine import (
    calculate_alpha_score,
    generate_rating,
    generate_action
)


PORTFOLIO_FILE = "data/portfolio.csv"
OUTPUT_FILE = "docs/latest.json"



def load_portfolio():

    portfolio = []

    if not os.path.exists(PORTFOLIO_FILE):
        return portfolio


    with open(
        PORTFOLIO_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            portfolio.append(row)


    return portfolio




def run_scanner():


    portfolio = load_portfolio()

    results = []


    for stock in portfolio:


        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )


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



        market_score = calculate_market_score(
            snapshot
        )



        catalyst_result = analyze_catalyst(
            ticker,
            []
        )


        catalyst_score = catalyst_result[
            "catalyst_score"
        ]



        sector_score = 50

        risk_score = 50




        alpha_score = calculate_alpha_score(

            market_score,

            catalyst_score,

            sector_score,

            risk_score

        )



        result = {


            "ticker": ticker,


            "timestamp":
            datetime.utcnow().isoformat(),



            "market": snapshot,



            "signal": signal,



            "scores": {

                "market_score":
                market_score,


                "catalyst_score":
                catalyst_score,


                "sector_score":
                sector_score,


                "risk_score":
                risk_score,


                "alpha_score":
                alpha_score

            },


            "catalyst":
            catalyst_result,



            "rating":
            generate_rating(
                alpha_score
            ),



            "action":
            generate_action(
                alpha_score
            ),



            "status":
            "ACTIVE"

        }


        results.append(result)



    output = {


        "generated":
        datetime.utcnow().isoformat(),


        "scanner_version":
        "V5.6",


        "portfolio":
        results

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
            indent=2
        )



    print(
        "V5.6 Scanner completed successfully"
    )





if __name__ == "__main__":

    run_scanner()
