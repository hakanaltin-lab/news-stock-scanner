"""
V5.2 Market Data Engine

Foundation layer for:
- Price data
- OHLCV structure
- Momentum calculation
- VWAP calculation
- Volume intelligence
"""

from datetime import datetime


def calculate_vwap(prices, volumes):
    """
    Calculate Volume Weighted Average Price
    """

    if not prices or not volumes:
        return 0

    total_volume = sum(volumes)

    if total_volume == 0:
        return 0

    weighted_sum = sum(
        price * volume
        for price, volume in zip(prices, volumes)
    )

    return round(weighted_sum / total_volume, 2)



def calculate_momentum(prices):
    """
    Simple momentum calculation
    """

    if len(prices) < 2:
        return 0

    first = prices[0]
    last = prices[-1]

    if first == 0:
        return 0

    momentum = ((last - first) / first) * 100

    return round(momentum, 2)



def build_market_snapshot(
    ticker,
    prices,
    volumes
):
    """
    Creates market intelligence snapshot
    """

    snapshot = {

        "ticker": ticker,

        "timestamp": datetime.utcnow().isoformat(),

        "last_price": prices[-1] if prices else None,

        "vwap": calculate_vwap(
            prices,
            volumes
        ),

        "momentum": calculate_momentum(
            prices
        ),

        "volume": sum(volumes),

        "data_quality": "FOUNDATION"

    }

    return snapshot



def get_market_signal(snapshot):
    """
    Basic market interpretation layer
    """

    momentum = snapshot.get(
        "momentum",
        0
    )

    vwap = snapshot.get(
        "vwap",
        0
    )

    price = snapshot.get(
        "last_price",
        0
    )


    if price > vwap and momentum > 1:
        return "BULLISH"


    if price < vwap and momentum < -1:
        return "BEARISH"


    return "NEUTRAL"



def run_market_engine(
    ticker,
    prices,
    volumes
):

    snapshot = build_market_snapshot(
        ticker,
        prices,
        volumes
    )

    snapshot["signal"] = get_market_signal(
        snapshot
    )

    return snapshot
