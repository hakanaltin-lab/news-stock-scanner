"""
V6.3 Global Market Intelligence Scanner

Controller Layer

Pipeline:

Portfolio Engine
        |
Market Data Engine
        |
Scoring Engine
        |
News Intelligence Engine
        |
Catalyst Engine
        |
Sector Intelligence Engine
        |
Risk Intelligence Engine
        |
Alpha Intelligence Engine
        |
Decision Engine
        |
JSON Report
"""

import os
import json
import csv

from datetime import datetime


from engines.market_data_engine import (
    build_market_snapshot,
    get_market_signal,
    get_live_market_data
)


from engines.scoring_engine import (
    calculate_market_score
)


from engines.news_engine import (
    analyze_news
)


from engines.catalyst_engine import (
    analyze_catalyst
)


from engines.sector_engine import (
    analyze_sector
)


from engines.risk_engine import (
    calculate_live_risk
)


from engines.alpha_intelligence_engine import (
    calculate_alpha_score,
    generate_rating,
    generate_action
)


from engines.decision_engine import (
    generate_decision
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

        # =================================================
        # 1. LIVE MARKET DATA
        # =================================================

        live_data = get_live_market_data(
            ticker
        )

        prices = live_data.get(
            "prices",
            []
        )

        volumes = live_data.get(
            "volumes",
            []
        )

        if not prices or not volumes:
            continue


        # =================================================
        # 2. MARKET SNAPSHOT
        # =================================================

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


        # =================================================
        # 3. NEWS INTELLIGENCE
        # =================================================

        news_result = analyze_news(
            ticker
        )

        news_score = news_result.get(
            "news_score",
            50
        )


        # =================================================
        # 4. CATALYST INTELLIGENCE
        # =================================================

        catalyst_result = analyze_catalyst(
            ticker
        )

        catalyst_score = catalyst_result.get(
            "catalyst_score",
            50
        )


        # =================================================
        # 5. SECTOR INTELLIGENCE
        # =================================================

        sector_result = analyze_sector(
            ticker
        )

        sector_score = sector_result.get(
            "sector_score",
            50
        )


        # =================================================
        # 6. DYNAMIC RISK INTELLIGENCE
        # =================================================

        risk_result = calculate_live_risk(
            ticker,
            prices,
            volumes
        )

        risk_score = risk_result.get(
            "risk_score",
            50
        )


        # =================================================
        # 7. ALPHA INTELLIGENCE
        # =================================================

        alpha_score = calculate_alpha_score(
            market_score,
            catalyst_score,
            sector_score,
            risk_score
        )


        # =================================================
        # 8. DECISION ENGINE
        # =================================================

        decision = generate_decision(
            alpha_score,
            market_score,
            catalyst_score,
            risk_score,
            snapshot.get(
                "last_price"
            )
        )


        # =================================================
        # 9. STOCK RESULT
        # =================================================

        result = {

            "ticker":
            ticker,

            "timestamp":
            datetime.utcnow().isoformat(),

            "market":
            snapshot,

            "signal":
            signal,

            "scores": {

                "market_score":
                market_score,

                "news_score":
                news_score,

                "catalyst_score":
                catalyst_score,

                "sector_score":
                sector_score,

                "risk_score":
                risk_score,

                "alpha_score":
                alpha_score

            },

            "news":
            news_result,

            "catalyst":
            catalyst_result,

            "sector":
            sector_result,

            "risk":
            risk_result,

            "rating":
            generate_rating(
                alpha_score
            ),

            "action":
            generate_action(
                alpha_score
            ),

            "decision":
            decision,

            "status":
            "ACTIVE"

        }

        results.append(
            result
        )


    # =====================================================
    # 10. FINAL PORTFOLIO OUTPUT
    # =====================================================

    output = {

        "generated":
        datetime.utcnow().isoformat(),

        "scanner_version":
        "V6.3",

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
        "V6.3 Scanner completed successfully"
    )


if __name__ == "__main__":

    run_scanner()
