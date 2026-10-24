"""
V6.8 Global Market Intelligence Scanner

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
Opportunity Fast Scanner
        |
Opportunity Deep Analysis
        |
Opportunity Safety Gate
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
    fetch_live_news,
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
    generate_rating
)


from engines.decision_engine import (
    generate_decision
)


from engines.opportunity_scanner_engine import (
    scan_opportunities
)


from engines.opportunity_deep_analysis_engine import (
    analyze_opportunity_candidates
)


PORTFOLIO_FILE = "data/portfolio.csv"

OUTPUT_FILE = "docs/latest.json"


def load_portfolio():

    portfolio = []

    if not os.path.exists(
        PORTFOLIO_FILE
    ):
        return portfolio

    with open(
        PORTFOLIO_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:

            portfolio.append(
                row
            )

    return portfolio


def run_scanner():

    # =====================================================
    # 1. PORTFOLIO ANALYSIS
    # =====================================================

    portfolio = load_portfolio()

    results = []


    for stock in portfolio:

        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        )


        # =================================================
        # LIVE MARKET DATA
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
        # MARKET SNAPSHOT
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
        # NEWS + CATALYST INTELLIGENCE
        # Fetch news once and reuse it
        # =================================================

        news_items = fetch_live_news(
            ticker,
            count=10
        )


        news_result = analyze_news(
            ticker,
            news_items=news_items
        )


        news_score = news_result.get(
            "news_score",
            50
        )


        catalyst_result = analyze_catalyst(
            ticker,
            news_items=news_items
        )


        catalyst_score = catalyst_result.get(
            "catalyst_score",
            50
        )


        # =================================================
        # SECTOR INTELLIGENCE
        # =================================================

        sector_result = analyze_sector(
            ticker
        )


        sector_score = sector_result.get(
            "sector_score",
            50
        )


        # =================================================
        # RISK INTELLIGENCE
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
        # ALPHA INTELLIGENCE
        # =================================================

        alpha_score = calculate_alpha_score(
            market_score,
            catalyst_score,
            sector_score,
            risk_score
        )


        alpha_rating = generate_rating(
            alpha_score
        )


        # =================================================
        # DECISION ENGINE
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


        final_action = decision.get(
            "action",
            "AVOID"
        )


        # =================================================
        # STOCK RESULT
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
            alpha_rating,

            "action":
            final_action,

            "decision":
            decision,

            "status":
            "ACTIVE"
        }


        results.append(
            result
        )


    # =====================================================
    # 2. MARKET OPPORTUNITY FAST SCANNER
    # =====================================================

    opportunity_scan = (
        scan_opportunities(
            top_n=15
        )
    )


    # =====================================================
    # 3. OPPORTUNITY DEEP ANALYSIS + V6.8 SAFETY GATE
    # =====================================================

    opportunity_analysis = (
        analyze_opportunity_candidates(
            opportunity_scan,
            max_candidates=8
        )
    )


    # =====================================================
    # 4. FINAL OUTPUT
    # =====================================================

    output = {

        "generated":
        datetime.utcnow().isoformat(),

        "scanner_version":
        "V6.8",

        "portfolio":
        results,

        "opportunity_scan":
        opportunity_scan,

        "opportunity_analysis":
        opportunity_analysis
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
        "V6.8 Scanner completed successfully"
    )


if __name__ == "__main__":

    run_scanner()
