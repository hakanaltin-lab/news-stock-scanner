"""
V7.6 Global Market Intelligence Scanner

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
New Entry Decision Engine
        |
Portfolio Management Engine
        |
Position Sizing & Rebalancing Engine
        |
Opportunity Fast Scanner
        |
Opportunity Deep Analysis
        |
Opportunity Safety Gate
        |
Market Regime Engine
        |
Earnings & Event Risk Engine
        |
Regime + Event-Aware Capital Allocation Engine
        |
Final Portfolio Projection Engine
        |
Portfolio Correlation & Factor Risk Engine
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


from engines.portfolio_management_engine import (
    evaluate_portfolio_position
)


from engines.position_sizing_engine import (
    build_rebalancing_plan,
    apply_event_risk_to_rebalancing
)


from engines.opportunity_scanner_engine import (
    scan_opportunities
)


from engines.opportunity_deep_analysis_engine import (
    analyze_opportunity_candidates
)


from engines.market_regime_engine import (
    analyze_market_regime
)


from engines.event_risk_engine import (
    build_event_risk_summary
)


from engines.capital_allocation_engine import (
    build_capital_allocation_plan
)


from engines.final_portfolio_projection_engine import (
    build_final_portfolio_projection
)


from engines.portfolio_correlation_factor_risk_engine import (
    analyze_portfolio_correlation_factor_risk
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
    # 1. CURRENT PORTFOLIO ANALYSIS
    # =====================================================

    portfolio = load_portfolio()

    results = []


    for stock in portfolio:

        ticker = stock.get(
            "ticker",
            "UNKNOWN"
        ).strip().upper()


        shares = stock.get(
            "shares",
            0
        )


        avg_cost = stock.get(
            "avg_cost",
            0
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


        current_price = snapshot.get(
            "last_price",
            0
        )


        # =================================================
        # NEWS + CATALYST INTELLIGENCE
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
        # NEW ENTRY DECISION
        # =================================================

        entry_decision = generate_decision(
            alpha_score,
            market_score,
            catalyst_score,
            risk_score,
            current_price
        )


        # =================================================
        # PORTFOLIO MANAGEMENT
        # =================================================

        portfolio_management = (
            evaluate_portfolio_position(
                ticker=ticker,
                shares=shares,
                avg_cost=avg_cost,
                current_price=current_price,
                alpha_score=alpha_score,
                market_score=market_score,
                catalyst_score=catalyst_score,
                sector_score=sector_score,
                risk_score=risk_score,
                signal=signal
            )
        )


        portfolio_action = (
            portfolio_management.get(
                "action",
                "WATCH"
            )
        )


        # =================================================
        # STOCK RESULT
        # =================================================

        result = {

            "ticker":
            ticker,

            "timestamp":
            datetime.utcnow().isoformat(),

            "holding": {

                "shares":
                shares,

                "avg_cost":
                avg_cost,

                "sector":
                stock.get(
                    "sector"
                ),

                "theme":
                stock.get(
                    "theme"
                ),

                "status":
                stock.get(
                    "status"
                )
            },

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

            "entry_action":
            entry_decision.get(
                "action",
                "AVOID"
            ),

            "entry_decision":
            entry_decision,

            "portfolio_action":
            portfolio_action,

            "portfolio_management":
            portfolio_management,

            "status":
            "ACTIVE"
        }


        results.append(
            result
        )


    # =====================================================
    # 2. V7.1 POSITION SIZING & REBALANCING
    # =====================================================

    portfolio_rebalancing = (
        build_rebalancing_plan(
            results
        )
    )


    # =====================================================
    # 3. MARKET OPPORTUNITY FAST SCANNER
    # =====================================================

    opportunity_scan = (
        scan_opportunities(
            top_n=15
        )
    )


    # =====================================================
    # 4. OPPORTUNITY DEEP ANALYSIS + SAFETY GATE
    # =====================================================

    opportunity_analysis = (
        analyze_opportunity_candidates(
            opportunity_scan,
            max_candidates=8
        )
    )


    # =====================================================
    # 5. V7.4 MARKET REGIME
    # =====================================================

    market_regime = (
        analyze_market_regime()
    )


    # =====================================================
    # 6. V7.5 EARNINGS & EVENT RISK
    # =====================================================

    event_risk = (
        build_event_risk_summary(
            results,
            opportunity_analysis
        )
    )


    portfolio_rebalancing = (
        apply_event_risk_to_rebalancing(
            portfolio_rebalancing,
            event_risk,
            results
        )
    )


    # =====================================================
    # 7. V7.5 REGIME + EVENT-AWARE CAPITAL ALLOCATION
    # =====================================================

    capital_allocation = (
        build_capital_allocation_plan(
            portfolio_rebalancing,
            opportunity_analysis,
            market_regime_result=market_regime,
            event_risk_result=event_risk
        )
    )


    # =====================================================
    # 8. V7.3 FINAL PORTFOLIO PROJECTION
    # =====================================================

    final_portfolio_projection = (
        build_final_portfolio_projection(
            results,
            portfolio_rebalancing,
            capital_allocation
        )
    )


    # =====================================================
    # 9. V7.6 PORTFOLIO CORRELATION & FACTOR RISK
    # =====================================================

    portfolio_correlation_factor_risk = (
        analyze_portfolio_correlation_factor_risk(
            final_portfolio_projection
        )
    )


    # =====================================================
    # 10. FINAL OUTPUT
    # =====================================================

    output = {

        "generated":
        datetime.utcnow().isoformat(),

        "scanner_version":
        "V7.6",

        "portfolio":
        results,

        "portfolio_rebalancing":
        portfolio_rebalancing,

        "opportunity_scan":
        opportunity_scan,

        "opportunity_analysis":
        opportunity_analysis,

        "market_regime":
        market_regime,

        "event_risk":
        event_risk,

        "capital_allocation":
        capital_allocation,

        "final_portfolio_projection":
        final_portfolio_projection,

        "portfolio_correlation_factor_risk":
        portfolio_correlation_factor_risk
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
        "V7.6 Scanner completed successfully"
    )


if __name__ == "__main__":

    run_scanner()
