"""
V6.3 Dynamic Sector Intelligence Engine

Purpose:
- Detect company sector / industry
- Select relevant sector or industry ETF
- Measure sector momentum
- Compare sector performance versus S&P 500
- Measure short-term trend and volatility
- Generate dynamic 0-100 sector score

Higher sector_score = stronger sector environment
"""

from functools import lru_cache
from statistics import pstdev

import yfinance as yf


SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Communication Services": "XLC",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}


INDUSTRY_ETF_MAP = {
    "Semiconductor": "SMH",
    "Semiconductors": "SMH",
    "Healthcare Plans": "XLV",
    "Medical": "XLV",
    "Biotechnology": "XBI",
    "Banks": "KBE",
    "Insurance": "KIE",
    "Oil & Gas": "XLE",
    "Oil & Gas Equipment": "XES",
    "Aerospace": "ITA",
    "Defense": "ITA",
    "Software": "IGV",
    "Internet": "XLC",
    "Communication Equipment": "XLC",
    "Specialty Industrial Machinery": "XLI",
}


def clamp(value, minimum=0, maximum=100):

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


@lru_cache(maxsize=64)
def get_price_history(ticker):

    try:

        data = yf.Ticker(
            ticker
        ).history(
            period="3mo",
            interval="1d"
        )

        if data.empty:
            return tuple()

        closes = [
            float(value)
            for value in data["Close"].dropna().tolist()
        ]

        return tuple(
            closes
        )

    except Exception:

        return tuple()


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
        end_price / start_price
        - 1
    )


def calculate_daily_volatility(
    prices
):

    if len(prices) < 3:
        return 0.0

    returns = []

    for index in range(
        1,
        len(prices)
    ):

        previous = prices[
            index - 1
        ]

        current = prices[
            index
        ]

        if previous:

            returns.append(
                current / previous
                - 1
            )

    if len(returns) < 2:
        return 0.0

    return pstdev(
        returns
    )


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

    return sum(
        sample
    ) / len(
        sample
    )


def get_company_classification(
    ticker
):

    sector = "Unknown"

    industry = "Unknown"

    try:

        stock = yf.Ticker(
            ticker
        )

        info = stock.get_info()

        if isinstance(
            info,
            dict
        ):

            sector = info.get(
                "sector",
                "Unknown"
            )

            industry = info.get(
                "industry",
                "Unknown"
            )

    except Exception:

        pass

    return (
        sector,
        industry
    )


def choose_sector_etf(
    sector,
    industry
):

    industry_lower = str(
        industry
    ).lower()

    for keyword, etf in INDUSTRY_ETF_MAP.items():

        if keyword.lower() in industry_lower:

            return etf

    return SECTOR_ETF_MAP.get(
        sector,
        "SPY"
    )


def calculate_sector_score(
    sector_prices,
    market_prices
):

    if not sector_prices:

        return {
            "score": 50.0,
            "sector_momentum_20d": 0.0,
            "sector_momentum_5d": 0.0,
            "market_momentum_20d": 0.0,
            "relative_strength": 0.0,
            "volatility_pct": 0.0,
            "trend_above_sma20": False
        }


    sector_20d = calculate_return(
        sector_prices,
        20
    )

    sector_5d = calculate_return(
        sector_prices,
        5
    )

    market_20d = calculate_return(
        market_prices,
        20
    )


    relative_strength = (
        sector_20d
        - market_20d
    )


    volatility = calculate_daily_volatility(
        sector_prices
    )


    sma20 = calculate_sma(
        sector_prices,
        20
    )


    last_price = (
        sector_prices[-1]
        if sector_prices
        else 0
    )


    trend_above_sma20 = (
        last_price > sma20
        if sma20
        else False
    )


    score = 50.0


    # Sector absolute momentum
    score += clamp(
        sector_20d * 200,
        -15,
        15
    )


    # Sector short-term momentum
    score += clamp(
        sector_5d * 150,
        -10,
        10
    )


    # Relative strength versus S&P 500
    score += clamp(
        relative_strength * 300,
        -20,
        20
    )


    # Trend quality
    if trend_above_sma20:

        score += 7

    else:

        score -= 7


    # Excess volatility penalty
    volatility_pct = (
        volatility * 100
    )

    if volatility_pct > 3.0:

        score -= 10

    elif volatility_pct > 2.0:

        score -= 5


    score = round(
        clamp(
            score
        ),
        1
    )


    return {

        "score":
        score,

        "sector_momentum_20d":
        round(
            sector_20d * 100,
            2
        ),

        "sector_momentum_5d":
        round(
            sector_5d * 100,
            2
        ),

        "market_momentum_20d":
        round(
            market_20d * 100,
            2
        ),

        "relative_strength":
        round(
            relative_strength * 100,
            2
        ),

        "volatility_pct":
        round(
            volatility_pct,
            2
        ),

        "trend_above_sma20":
        trend_above_sma20

    }


def analyze_sector(
    ticker
):

    sector, industry = (
        get_company_classification(
            ticker
        )
    )


    sector_etf = choose_sector_etf(
        sector,
        industry
    )


    sector_prices = list(
        get_price_history(
            sector_etf
        )
    )


    market_prices = list(
        get_price_history(
            "SPY"
        )
    )


    metrics = calculate_sector_score(
        sector_prices,
        market_prices
    )


    sector_score = metrics[
        "score"
    ]


    if sector_score >= 70:

        sector_signal = (
            "STRONG"
        )

    elif sector_score >= 55:

        sector_signal = (
            "POSITIVE"
        )

    elif sector_score >= 45:

        sector_signal = (
            "NEUTRAL"
        )

    elif sector_score >= 30:

        sector_signal = (
            "WEAK"
        )

    else:

        sector_signal = (
            "VERY_WEAK"
        )


    return {

        "ticker":
        ticker,

        "sector":
        sector,

        "industry":
        industry,

        "sector_etf":
        sector_etf,

        "sector_score":
        sector_score,

        "sector_signal":
        sector_signal,

        "metrics":
        {

            "sector_momentum_20d":
            metrics[
                "sector_momentum_20d"
            ],

            "sector_momentum_5d":
            metrics[
                "sector_momentum_5d"
            ],

            "market_momentum_20d":
            metrics[
                "market_momentum_20d"
            ],

            "relative_strength":
            metrics[
                "relative_strength"
            ],

            "volatility_pct":
            metrics[
                "volatility_pct"
            ],

            "trend_above_sma20":
            metrics[
                "trend_above_sma20"
            ]

        },

        "data_quality":
        (
            "LIVE"
            if sector_prices
            else "NO_DATA"
        )

    }
