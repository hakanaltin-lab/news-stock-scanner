"""
V6.6 AURORA Opportunity Scanner Engine

Purpose:
- Scan the broader US stock universe
- Exclude current portfolio holdings
- Use fast batch market data
- Rank stocks before expensive deep analysis
- Identify the strongest new opportunity candidates

Fast-screen factors:
- 5-day momentum
- 20-day momentum
- 60-day trend
- Relative strength versus SPY
- Volume confirmation
- 20-day moving-average trend
- Liquidity
- Overextension control
"""

import csv
import json
import os

import pandas as pd
import yfinance as yf


UNIVERSE_FILE = "data/us_universe.json"
PORTFOLIO_FILE = "data/portfolio.csv"


def clamp(
    value,
    minimum=0,
    maximum=100
):

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def load_universe():

    if not os.path.exists(
        UNIVERSE_FILE
    ):

        return []

    try:

        with open(
            UNIVERSE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            list
        ):

            return data

    except Exception:

        pass

    return []


def load_portfolio_tickers():

    tickers = set()

    if not os.path.exists(
        PORTFOLIO_FILE
    ):

        return tickers

    try:

        with open(
            PORTFOLIO_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(
                file
            )

            for row in reader:

                ticker = str(
                    row.get(
                        "ticker",
                        ""
                    )
                ).strip().upper()

                if ticker:

                    tickers.add(
                        ticker
                    )

    except Exception:

        pass

    return tickers


def calculate_return(
    prices,
    periods
):

    if not prices:

        return 0.0

    if len(prices) <= periods:

        return 0.0

    start_price = prices[
        -(periods + 1)
    ]

    end_price = prices[-1]

    if not start_price:

        return 0.0

    return (
        (
            end_price / start_price
        )
        - 1
    ) * 100


def calculate_sma(
    prices,
    periods=20
):

    if not prices:

        return 0.0

    sample = prices[
        -periods:
    ]

    if not sample:

        return 0.0

    return (
        sum(sample)
        / len(sample)
    )


def calculate_volume_ratio(
    volumes
):

    if len(volumes) < 25:

        return 1.0

    recent = volumes[
        -5:
    ]

    previous = volumes[
        -25:-5
    ]

    recent_average = (
        sum(recent)
        / len(recent)
    )

    previous_average = (
        sum(previous)
        / len(previous)
    )

    if previous_average <= 0:

        return 1.0

    return round(
        recent_average
        / previous_average,
        2
    )


def calculate_average_dollar_volume(
    prices,
    volumes
):

    if not prices or not volumes:

        return 0.0

    length = min(
        20,
        len(prices),
        len(volumes)
    )

    if length <= 0:

        return 0.0

    values = []

    for price, volume in zip(
        prices[-length:],
        volumes[-length:]
    ):

        values.append(
            price * volume
        )

    if not values:

        return 0.0

    return (
        sum(values)
        / len(values)
    )


def get_ticker_frame(
    data,
    ticker
):

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            level_zero = list(
                data.columns.get_level_values(
                    0
                )
            )

            level_one = list(
                data.columns.get_level_values(
                    1
                )
            )

            if ticker in level_zero:

                frame = data[
                    ticker
                ].copy()

                return frame

            if ticker in level_one:

                frame = data.xs(
                    ticker,
                    axis=1,
                    level=1
                ).copy()

                return frame

        if ticker == "SPY":

            return data.copy()

    except Exception:

        pass

    return pd.DataFrame()


def calculate_fast_score(
    return_5d,
    return_20d,
    return_60d,
    relative_strength_20d,
    volume_ratio,
    above_sma20,
    overextension_pct
):

    momentum_20_score = clamp(
        50
        + return_20d * 2.5
    )

    momentum_5_score = clamp(
        50
        + return_5d * 4
    )

    relative_strength_score = clamp(
        50
        + relative_strength_20d * 3
    )

    volume_score = clamp(
        50
        + (
            volume_ratio - 1
        ) * 35
    )

    trend_score = (
        70
        if above_sma20
        else 30
    )

    if return_60d > 0:

        trend_score += 15

    else:

        trend_score -= 10

    trend_score = clamp(
        trend_score
    )

    score = (

        momentum_20_score * 0.25

        + momentum_5_score * 0.15

        + relative_strength_score * 0.25

        + volume_score * 0.15

        + trend_score * 0.20

    )

    if overextension_pct > 12:

        penalty = min(
            15,
            (
                overextension_pct
                - 12
            ) * 1.5
        )

        score -= penalty

    return round(
        clamp(
            score
        ),
        1
    )


def classify_candidate(
    score
):

    if score >= 75:

        return "HIGH_POTENTIAL"

    elif score >= 65:

        return "STRONG"

    elif score >= 55:

        return "WATCH"

    else:

        return "PASS"


def scan_opportunities(
    top_n=15
):

    universe = load_universe()

    portfolio_tickers = (
        load_portfolio_tickers()
    )

    candidates = []

    universe_map = {}

    for item in universe:

        ticker = str(
            item.get(
                "ticker",
                ""
            )
        ).strip().upper()

        if not ticker:

            continue

        universe_map[
            ticker
        ] = item

    tickers = [
        ticker
        for ticker in universe_map
        if ticker
        not in portfolio_tickers
    ]

    if not tickers:

        return {
            "scanned":
            0,

            "qualified":
            0,

            "opportunities":
            [],

            "data_quality":
            "NO_DATA"
        }

    download_tickers = list(
        dict.fromkeys(
            tickers
            + ["SPY"]
        )
    )

    try:

        market_data = yf.download(
            tickers=download_tickers,
            period="6mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker"
        )

    except Exception:

        return {
            "scanned":
            0,

            "qualified":
            0,

            "opportunities":
            [],

            "data_quality":
            "ERROR"
        }

    spy_frame = get_ticker_frame(
        market_data,
        "SPY"
    )

    if spy_frame.empty:

        return {
            "scanned":
            0,

            "qualified":
            0,

            "opportunities":
            [],

            "data_quality":
            "NO_MARKET_BENCHMARK"
        }

    spy_prices = [
        float(value)
        for value
        in spy_frame[
            "Close"
        ].dropna().tolist()
    ]

    spy_return_20d = (
        calculate_return(
            spy_prices,
            20
        )
    )

    scanned_count = 0

    for ticker in tickers:

        frame = get_ticker_frame(
            market_data,
            ticker
        )

        if frame.empty:

            continue

        if (
            "Close"
            not in frame.columns
            or "Volume"
            not in frame.columns
        ):

            continue

        clean_frame = frame.dropna(
            subset=[
                "Close",
                "Volume"
            ]
        )

        if len(clean_frame) < 25:

            continue

        prices = [
            float(value)
            for value
            in clean_frame[
                "Close"
            ].tolist()
        ]

        volumes = [
            float(value)
            for value
            in clean_frame[
                "Volume"
            ].tolist()
        ]

        if not prices:

            continue

        scanned_count += 1

        last_price = prices[-1]

        return_5d = calculate_return(
            prices,
            5
        )

        return_20d = calculate_return(
            prices,
            20
        )

        return_60d = calculate_return(
            prices,
            60
        )

        relative_strength_20d = (
            return_20d
            - spy_return_20d
        )

        sma20 = calculate_sma(
            prices,
            20
        )

        above_sma20 = (
            last_price > sma20
            if sma20
            else False
        )

        overextension_pct = (
            (
                last_price / sma20
                - 1
            ) * 100
            if sma20
            else 0
        )

        volume_ratio = (
            calculate_volume_ratio(
                volumes
            )
        )

        average_dollar_volume = (
            calculate_average_dollar_volume(
                prices,
                volumes
            )
        )

        if last_price < 5:

            continue

        if (
            average_dollar_volume
            < 10_000_000
        ):

            continue

        opportunity_score = (
            calculate_fast_score(
                return_5d,
                return_20d,
                return_60d,
                relative_strength_20d,
                volume_ratio,
                above_sma20,
                overextension_pct
            )
        )

        opportunity_signal = (
            classify_candidate(
                opportunity_score
            )
        )

        if opportunity_score < 55:

            continue

        metadata = universe_map.get(
            ticker,
            {}
        )

        candidates.append(
            {

                "ticker":
                ticker,

                "sector":
                metadata.get(
                    "sector",
                    "Unknown"
                ),

                "industry":
                metadata.get(
                    "industry",
                    "Unknown"
                ),

                "last_price":
                round(
                    last_price,
                    2
                ),

                "return_5d_pct":
                round(
                    return_5d,
                    2
                ),

                "return_20d_pct":
                round(
                    return_20d,
                    2
                ),

                "return_60d_pct":
                round(
                    return_60d,
                    2
                ),

                "spy_return_20d_pct":
                round(
                    spy_return_20d,
                    2
                ),

                "relative_strength_20d":
                round(
                    relative_strength_20d,
                    2
                ),

                "volume_ratio":
                volume_ratio,

                "above_sma20":
                above_sma20,

                "overextension_pct":
                round(
                    overextension_pct,
                    2
                ),

                "average_dollar_volume":
                round(
                    average_dollar_volume,
                    2
                ),

                "opportunity_score":
                opportunity_score,

                "opportunity_signal":
                opportunity_signal,

                "data_quality":
                "LIVE"

            }
        )

    candidates = sorted(
        candidates,
        key=lambda item:
        item[
            "opportunity_score"
        ],
        reverse=True
    )

    top_candidates = candidates[
        :top_n
    ]

    return {

        "scanned":
        scanned_count,

        "qualified":
        len(candidates),

        "returned":
        len(top_candidates),

        "benchmark":
        "SPY",

        "benchmark_return_20d_pct":
        round(
            spy_return_20d,
            2
        ),

        "opportunities":
        top_candidates,

        "data_quality":
        "LIVE"

    }
