"""
V6.2 Dynamic Risk Intelligence Engine

Purpose:
- Measure short-term volatility
- Measure maximum drawdown
- Measure liquidity quality
- Measure downside momentum
- Generate dynamic 0-100 risk quality score

Higher risk_score = safer / better risk profile
"""

from statistics import pstdev


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def calculate_max_drawdown(prices):
    if not prices:
        return 0.0

    peak = prices[0]
    max_drawdown = 0.0

    for price in prices:
        if price > peak:
            peak = price

        if peak > 0:
            drawdown = ((peak - price) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)

    return round(max_drawdown, 2)


def calculate_live_risk(ticker, prices, volumes):

    if not prices or len(prices) < 2:

        return {
            "ticker": ticker,
            "risk_score": 50,
            "risk_signal": "UNKNOWN",
            "data_quality": "NO_DATA"
        }

    returns = []

    for i in range(1, len(prices)):

        previous = prices[i - 1]

        if previous > 0:
            change = (
                (prices[i] / previous) - 1
            ) * 100

            returns.append(change)

    volatility = (
        pstdev(returns)
        if len(returns) > 1
        else 0
    )

    max_drawdown = calculate_max_drawdown(prices)

    trend_pct = (
        (prices[-1] / prices[0]) - 1
    ) * 100

    dollar_volumes = [
        price * volume
        for price, volume
        in zip(prices, volumes)
    ]

    average_dollar_volume = (
        sum(dollar_volumes) / len(dollar_volumes)
        if dollar_volumes
        else 0
    )

    volatility_score = clamp(
        100 - volatility * 25
    )

    drawdown_score = clamp(
        100 - max_drawdown * 8
    )

    if average_dollar_volume >= 50_000_000:
        liquidity_score = 100

    elif average_dollar_volume >= 20_000_000:
        liquidity_score = 90

    elif average_dollar_volume >= 5_000_000:
        liquidity_score = 80

    elif average_dollar_volume >= 1_000_000:
        liquidity_score = 65

    elif average_dollar_volume >= 250_000:
        liquidity_score = 50

    else:
        liquidity_score = 30

    downside_momentum_score = clamp(
        100 + min(trend_pct, 0) * 5
    )

    risk_score = (
        volatility_score * 0.35
        + drawdown_score * 0.35
        + liquidity_score * 0.20
        + downside_momentum_score * 0.10
    )

    risk_score = round(
        clamp(risk_score),
        1
    )

    if risk_score >= 80:
        risk_signal = "LOW_RISK"

    elif risk_score >= 60:
        risk_signal = "MODERATE_RISK"

    elif risk_score >= 40:
        risk_signal = "ELEVATED_RISK"

    else:
        risk_signal = "HIGH_RISK"

    return {
        "ticker": ticker,

        "risk_score":
        risk_score,

        "risk_signal":
        risk_signal,

        "volatility_pct":
        round(volatility, 2),

        "max_drawdown_pct":
        max_drawdown,

        "trend_pct":
        round(trend_pct, 2),

        "average_dollar_volume":
        round(average_dollar_volume, 2),

        "components": {
            "volatility_score":
            round(volatility_score, 1),

            "drawdown_score":
            round(drawdown_score, 1),

            "liquidity_score":
            liquidity_score,

            "downside_momentum_score":
            round(downside_momentum_score, 1)
        },

        "data_quality":
        "LIVE"
    }
