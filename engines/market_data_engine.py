"""
V5.8 Market Data Intelligence Engine

Functions:
- Live market data layer
- Price intelligence
- VWAP calculation
- Momentum analysis
- Market snapshot generation
"""

from datetime import datetime

import yfinance as yf


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

    return round(
        weighted_sum / total_volume,
        2
    )


def calculate_momentum(prices):
    """
    Basic momentum calculation
    """

    if len(prices) < 2:
        return 0

    return round(
        prices[-1] - prices[0],
        2
    )


def get_live_market_data(ticker):
    """
    Retrieve live market data

    Future expansion:
    - Real time feed
    - IBKR API
    - Alpaca API
    """

    try:

        stock = yf.Ticker(ticker)

        data = stock.history(
            period="5d",
            interval="15m"
        )


        if data.empty:

            return {
                "ticker": ticker,
                "data_quality": "NO_DATA"
            }


        latest = data.iloc[-1]


        return {

            "ticker": ticker,

            "last_price":
                round(
                    float(latest["Close"]),
                    2
                ),

            "volume":
                int(
                    latest["Volume"]
                ),

            "high":
                round(
                    float(latest["High"]),
                    2
                ),

            "low":
                round(
                    float(latest["Low"]),
                    2
                ),

            "open":
                round(
                    float(latest["Open"]),
                    2
                ),

            "data_quality":
                "LIVE"

        }


    except Exception as e:


        return {

            "ticker": ticker,

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

    """
    Creates market intelligence snapshot
    """


    snapshot = {


        "ticker":
            ticker,


        "timestamp":
            datetime.utcnow().isoformat(),


        "last_price":
            prices[-1]
            if prices
            else None,


        "vwap":
            calculate_vwap(
                prices,
                volumes
            ),


        "momentum":
            calculate_momentum(
                prices
            ),


        "volume":
            sum(volumes),


        "data_quality":
            "FOUNDATION"

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


    price = snapshot.get(
        "last_price",
        0
    )


    vwap = snapshot.get(
        "vwap",
        0
    )


    if price > vwap and momentum > 0:

        return "BULLISH"


    elif price < vwap and momentum < 0:

        return "BEARISH"


    else:

        return "NEUTRAL"
