"""
V6.8 AURORA Opportunity Deep Analysis Engine

Purpose:
- Take strongest candidates from Opportunity Scanner
- Run full AURORA intelligence stack
- Apply V6.8 Safety Gate before final action
- Produce BUY / ACCUMULATE / WATCH / AVOID decisions
"""

from engines.market_data_engine import (
    get_live_market_data,
    build_market_snapshot,
    get_market_signal
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

from engines.opportunity_safety_engine import (
    apply_opportunity_safety_gate
)


ACTION_PRIORITY = {
    "BUY": 4,
    "ACCUMULATE": 3,
    "WATCH": 2,
    "AVOID": 1
}


def analyze_single_opportunity(candidate):

    ticker = candidate.get(
        "ticker"
    )

    if not ticker:
        return None


    # ==============================================
    # LIVE MARKET DATA
    # ==============================================

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

        return {
            "ticker": ticker,
            "status": "NO_MARKET_DATA",
            "fast_scan": candidate
        }


    # ==============================================
    # MARKET INTELLIGENCE
    # ==============================================

    snapshot = build_market_snapshot(
        ticker,
        prices,
        volumes
    )

    market_signal = get_market_signal(
        snapshot
    )

    market_score = calculate_market_score(
        snapshot
    )


    # ==============================================
    # NEWS + CATALYST INTELLIGENCE
    # ==============================================

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


    # ==============================================
    # SECTOR INTELLIGENCE
    # ==============================================

    sector_result = analyze_sector(
        ticker
    )

    sector_score = sector_result.get(
        "sector_score",
        50
    )


    # ==============================================
    # RISK INTELLIGENCE
    # ==============================================

    risk_result = calculate_live_risk(
        ticker,
        prices,
        volumes
    )

    risk_score = risk_result.get(
        "risk_score",
        50
    )


    # ==============================================
    # ALPHA INTELLIGENCE
    # ==============================================

    alpha_score = calculate_alpha_score(
        market_score,
        catalyst_score,
        sector_score,
        risk_score
    )

    rating = generate_rating(
        alpha_score
    )


    # ==============================================
    # BASE DECISION ENGINE
    # ==============================================

    base_decision = generate_decision(
        alpha_score,
        market_score,
        catalyst_score,
        risk_score,
        snapshot.get(
            "last_price"
        )
    )


    # ==============================================
    # V6.8 SAFETY GATE
    # ==============================================

    overextension_pct = candidate.get(
        "overextension_pct",
        0
    )

    decision = apply_opportunity_safety_gate(
        base_decision,
        sector_score,
        overextension_pct
    )

    action = decision.get(
        "action",
        "AVOID"
    )


    # ==============================================
    # RESULT
    # ==============================================

    return {

        "ticker":
        ticker,

        "sector":
        candidate.get(
            "sector",
            sector_result.get(
                "sector",
                "Unknown"
            )
        ),

        "industry":
        candidate.get(
            "industry",
            sector_result.get(
                "industry",
                "Unknown"
            )
        ),

        "fast_scan": {

            "opportunity_score":
            candidate.get(
                "opportunity_score"
            ),

            "opportunity_signal":
            candidate.get(
                "opportunity_signal"
            ),

            "return_5d_pct":
            candidate.get(
                "return_5d_pct"
            ),

            "return_20d_pct":
            candidate.get(
                "return_20d_pct"
            ),

            "return_60d_pct":
            candidate.get(
                "return_60d_pct"
            ),

            "relative_strength_20d":
            candidate.get(
                "relative_strength_20d"
            ),

            "volume_ratio":
            candidate.get(
                "volume_ratio"
            ),

            "overextension_pct":
            overextension_pct
        },

        "market":
        snapshot,

        "market_signal":
        market_signal,

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

        "sector_analysis":
        sector_result,

        "risk":
        risk_result,

        "rating":
        rating,

        "action":
        action,

        "base_decision":
        base_decision,

        "decision":
        decision,

        "status":
        "ANALYZED",

        "data_quality":
        "LIVE"
    }


def analyze_opportunity_candidates(
    opportunity_scan,
    max_candidates=8
):

    candidates = opportunity_scan.get(
        "opportunities",
        []
    )

    selected_candidates = candidates[
        :max_candidates
    ]

    results = []


    for candidate in selected_candidates:

        try:

            result = analyze_single_opportunity(
                candidate
            )

            if result:
                results.append(
                    result
                )

        except Exception as error:

            results.append(
                {
                    "ticker":
                    candidate.get(
                        "ticker",
                        "UNKNOWN"
                    ),

                    "status":
                    "ERROR",

                    "error":
                    str(error),

                    "fast_scan":
                    candidate
                }
            )


    def ranking_key(item):

        action = item.get(
            "action",
            "AVOID"
        )

        alpha_score = (
            item.get(
                "scores",
                {}
            ).get(
                "alpha_score",
                0
            )
        )

        opportunity_score = (
            item.get(
                "fast_scan",
                {}
            ).get(
                "opportunity_score",
                0
            )
            or 0
        )

        return (
            ACTION_PRIORITY.get(
                action,
                0
            ),
            alpha_score,
            opportunity_score
        )


    results = sorted(
        results,
        key=ranking_key,
        reverse=True
    )


    actionable = [
        item
        for item in results
        if item.get(
            "action"
        )
        in [
            "BUY",
            "ACCUMULATE"
        ]
    ]


    watchlist = [
        item
        for item in results
        if item.get(
            "action"
        )
        == "WATCH"
    ]


    safety_blocked = [
        item
        for item in results
        if (
            item.get(
                "decision",
                {}
            ).get(
                "safety_gate",
                {}
            ).get(
                "triggered",
                False
            )
        )
    ]


    return {

        "candidates_received":
        len(candidates),

        "deep_analyzed":
        len(results),

        "actionable_count":
        len(actionable),

        "watch_count":
        len(watchlist),

        "safety_blocked_count":
        len(safety_blocked),

        "top_actionable":
        actionable,

        "watchlist":
        watchlist,

        "safety_blocked":
        safety_blocked,

        "all_analyzed":
        results,

        "data_quality":
        "LIVE"
    }
