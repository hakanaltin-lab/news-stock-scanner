"""
V6.4 Market Data Intelligence Engine

Purpose:
- Retrieve recent market data
- Calculate VWAP
- Calculate absolute and percentage momentum
- Calculate distance from VWAP
- Measure relative volume
- Build normalized market snapshot
"""

from datetime import datetime

import yfinance as yf


def calculate_vwap(prices, volumes):

    if not prices or not volumes:
        return 0

    total_volume = sum(volumes)

    if total_volume == 0:
        return 0

    weighted_sum = sum(
        price * volume
        for price, volume in zip(
            prices,
            volumes
        )
    )

    return round(
        weighted_sum / total_volume,
        2
    )


def calculate_momentum(prices):

    if len(prices) < 2:
        return 0

    return round(
        prices[-1] - prices[0],
        2
    )


def calculate_momentum_pct(prices):

    if len(prices) < 2:
        return 0

    start_price = prices[0]

    end_price = prices[-1]

    if not start_price:
        return 0

    return round(
        (
            (end_price / start_price)
            - 1
        ) * 100,
        2
    )


def calculate_vwap_distance_pct(
    price,
    vwap
):

    if not price or not vwap:
        return 0

    return round(
        (
            (price / vwap)
            - 1
        ) * 100,
        2
    )


def calculate_volume_ratio(volumes):

    if not volumes or len(volumes) < 4:
        return 1.0

    recent_window = max(
        4,
        len(volumes) // 5
    )

    recent_window = min(
        26,
        recent_window
    )

    recent_volumes = volumes[
        -recent_window:
    ]

    historical_volumes = volumes[
        :-recent_window
    ]

    if not historical_volumes:
        return 1.0

    recent_average = (
        sum(recent_volumes)
        / len(recent_volumes)
    )

    historical_average = (
        sum(historical_volumes)
        / len(historical_volumes)
    )

    if historical_average <= 0:
        return 1.0

    ratio = (
        recent_average
        / historical_average
    )

    return round(
        min(ratio, 5.0),
        2
    )


def get_live_market_data(ticker):

    try:

        stock = yf.Ticker(
            ticker
        )

        data = stock.history(
            period="5d",
            interval="15m"
        )

        if data.empty:

            return {
                "ticker": ticker,
                "prices": [],
                "volumes": [],
                "data_quality": "NO_DATA"
            }

        clean_data = data.dropna(
            subset=[
                "Close",
                "Volume"
            ]
        )

        if clean_data.empty:

            return {
                "ticker": ticker,
                "prices": [],
                "volumes": [],
                "data_quality": "NO_DATA"
            }

        latest = clean_data.iloc[-1]

        prices = [
            round(
                float(price),
                2
            )
            for price
            in clean_data["Close"].tolist()
        ]

        volumes = [
            int(volume)
            for volume
            in clean_data["Volume"].tolist()
        ]

        return {

            "ticker":
            ticker,

            "last_price":
            round(
                float(
                    latest["Close"]
                ),
                2
            ),

            "volume":
            int(
                latest["Volume"]
            ),

            "high":
            round(
                float(
                    latest["High"]
                ),
                2
            ),

            "low":
            round(
                float(
                    latest["Low"]
                ),
                2
            ),

            "open":
            round(
                float(
                    latest["Open"]
                ),
                2
            ),

            "prices":
            prices,

            "volumes":
            volumes,

            "data_points":
            len(prices),

            "data_quality":
            "LIVE"

        }

    except Exception as e:

        return {

            "ticker":
            ticker,

            "prices":
            [],

            "volumes":
            [],

            "error":
            str(e),

            "data_quality":
            "ERROR"

        }


def build_market_snapshot(
    ticker,
    prices,
    volumes
):

    last_price = (
        prices[-1]
        if prices
        else None
    )

    vwap = calculate_vwap(
        prices,
        volumes
    )

    momentum = calculate_momentum(
        prices
    )

    momentum_pct = calculate_momentum_pct(
        prices
    )

    vwap_distance_pct = (
        calculate_vwap_distance_pct(
            last_price,
            vwap
        )
    )

    volume_ratio = calculate_volume_ratio(
        volumes
    )

    snapshot = {

        "ticker":
        ticker,

        "timestamp":
        datetime.utcnow().isoformat(),

        "last_price":
        last_price,

        "vwap":
        vwap,

        "momentum":
        momentum,

        "momentum_pct":
        momentum_pct,

        "vwap_distance_pct":
        vwap_distance_pct,

        "volume":
        sum(volumes),

        "volume_ratio":
        volume_ratio,

        "data_points":
        len(prices),

        "data_quality":
        "LIVE"

    }

    return snapshot


def get_market_signal(snapshot):

    momentum_pct = snapshot.get(
        "momentum_pct",
        0
    )

    price = snapshot.get(
        "last_price",
        0
    )

    vwap = snapshot.get(
        "vwap",
        0
    )

    if (
        price > vwap
        and momentum_pct > 0
    ):

        return "BULLISH"

    elif (
        price < vwap
        and momentum_pct < 0
    ):

        return "BEARISH"

    else:

        return "NEUTRAL"
