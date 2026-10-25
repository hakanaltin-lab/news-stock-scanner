"""
V7.9 AURORA Strategic Market Engine

Purpose:
- Separate long-horizon position management from intraday entry timing
- Use daily 3M / 6M / 12M evidence for existing portfolio decisions
- Measure long-term trend, drawdown, volatility and relative strength vs SPY
- Produce a strategic market score and strategic risk score

Intraday 15-minute data remains outside this engine and should only be used
for tactical entry timing.

This engine does not send broker orders.
"""

from functools import lru_cache
import math

import pandas as pd
import yfinance as yf


MIN_OBSERVATIONS = 120


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pct_return(series, sessions):
    clean = series.dropna()

    if len(clean) <= sessions:
        return None

    start = safe_float(
        clean.iloc[-sessions - 1],
        None
    )

    end = safe_float(
        clean.iloc[-1],
        None
    )

    if (
        start is None
        or
        end is None
        or
        start <= 0
    ):
        return None

    return (
        end
        /
        start
        -
        1
    ) * 100


def calculate_sma(series, window):
    clean = series.dropna()

    if len(clean) < window:
        return None

    return safe_float(
        clean.tail(
            window
        ).mean(),
        None
    )


def calculate_max_drawdown(series, sessions=None):
    clean = series.dropna()

    if sessions:
        clean = clean.tail(
            sessions
        )

    if clean.empty:
        return 0.0

    running_peak = clean.cummax()

    drawdown = (
        clean
        /
        running_peak
        -
        1
    ) * 100

    return abs(
        safe_float(
            drawdown.min(),
            0.0
        )
    )


def calculate_annualized_volatility(series, sessions=60):
    clean = (
        series
        .dropna()
        .pct_change()
        .dropna()
        .tail(
            sessions
        )
    )

    if len(clean) < 20:
        return None

    return (
        safe_float(
            clean.std(),
            0.0
        )
        *
        math.sqrt(
            252
        )
        *
        100
    )


@lru_cache(maxsize=128)
def fetch_daily_close(ticker):
    try:
        history = yf.Ticker(
            ticker
        ).history(
            period="18mo",
            interval="1d",
            auto_adjust=True
        )

        if history is None or history.empty:
            return None

        close = history.get(
            "Close"
        )

        if close is None:
            return None

        close = close.dropna()

        if len(close) < MIN_OBSERVATIONS:
            return None

        return close

    except Exception:
        return None


def score_trend(
    last_price,
    sma50,
    sma100,
    sma200,
    return_3m,
    return_6m,
    return_12m,
    rs_3m,
    rs_6m
):
    score = 0.0

    if (
        sma50 is not None
        and
        last_price > sma50
    ):
        score += 12

    if (
        sma100 is not None
        and
        last_price > sma100
    ):
        score += 13

    if (
        sma200 is not None
        and
        last_price > sma200
    ):
        score += 20

    if (
        return_3m is not None
        and
        return_3m > 0
    ):
        score += 10

    if (
        return_6m is not None
        and
        return_6m > 0
    ):
        score += 15

    if (
        return_12m is not None
        and
        return_12m > 0
    ):
        score += 10

    if (
        rs_3m is not None
        and
        rs_3m > 0
    ):
        score += 8

    if (
        rs_6m is not None
        and
        rs_6m > 0
    ):
        score += 12

    return round(
        min(
            100,
            max(
                0,
                score
            )
        ),
        1
    )


def score_risk(
    max_drawdown_6m,
    max_drawdown_12m,
    volatility_60d
):
    score = 100.0

    drawdown_6m_penalty = min(
        35,
        max_drawdown_6m
        *
        1.4
    )

    drawdown_12m_penalty = min(
        25,
        max_drawdown_12m
        *
        0.8
    )

    volatility_penalty = min(
        30,
        max(
            0,
            (
                safe_float(
                    volatility_60d,
                    20
                )
                -
                18
            )
            *
            0.9
        )
    )

    score -= (
        drawdown_6m_penalty
        +
        drawdown_12m_penalty
        +
        volatility_penalty
    )

    return round(
        min(
            100,
            max(
                0,
                score
            )
        ),
        1
    )


def classify_trend(
    trend_score,
    last_price,
    sma200,
    return_6m
):
    above_200 = (
        sma200 is not None
        and
        last_price > sma200
    )

    if (
        trend_score >= 75
        and
        above_200
        and
        safe_float(
            return_6m,
            0
        )
        > 0
    ):
        return "STRONG_UPTREND"

    if (
        trend_score >= 55
        and
        (
            above_200
            or
            safe_float(
                return_6m,
                0
            )
            > 0
        )
    ):
        return "HEALTHY"

    if (
        trend_score < 35
        and
        not above_200
        and
        safe_float(
            return_6m,
            0
        )
        < 0
    ):
        return "DOWNTREND"

    return "MIXED"


def analyze_strategic_market(ticker):
    close = fetch_daily_close(
        ticker
    )

    spy_close = fetch_daily_close(
        "SPY"
    )

    if close is None:
        return {
            "engine":
            "V7.9 Strategic Market Engine",

            "ticker":
            ticker,

            "data_quality":
            "NO_DATA",

            "strategic_trend_score":
            50.0,

            "strategic_risk_score":
            50.0,

            "strategic_signal":
            "UNKNOWN",

            "metrics":
            {}
        }

    last_price = safe_float(
        close.iloc[-1]
    )

    return_3m = pct_return(
        close,
        63
    )

    return_6m = pct_return(
        close,
        126
    )

    return_12m = pct_return(
        close,
        252
    )

    spy_3m = (
        pct_return(
            spy_close,
            63
        )
        if spy_close is not None
        else None
    )

    spy_6m = (
        pct_return(
            spy_close,
            126
        )
        if spy_close is not None
        else None
    )

    rs_3m = (
        return_3m
        -
        spy_3m
        if (
            return_3m is not None
            and
            spy_3m is not None
        )
        else None
    )

    rs_6m = (
        return_6m
        -
        spy_6m
        if (
            return_6m is not None
            and
            spy_6m is not None
        )
        else None
    )

    sma50 = calculate_sma(
        close,
        50
    )

    sma100 = calculate_sma(
        close,
        100
    )

    sma200 = calculate_sma(
        close,
        200
    )

    max_drawdown_6m = (
        calculate_max_drawdown(
            close,
            126
        )
    )

    max_drawdown_12m = (
        calculate_max_drawdown(
            close,
            252
        )
    )

    volatility_60d = (
        calculate_annualized_volatility(
            close,
            60
        )
    )

    trend_score = score_trend(
        last_price=last_price,
        sma50=sma50,
        sma100=sma100,
        sma200=sma200,
        return_3m=return_3m,
        return_6m=return_6m,
        return_12m=return_12m,
        rs_3m=rs_3m,
        rs_6m=rs_6m
    )

    risk_score = score_risk(
        max_drawdown_6m,
        max_drawdown_12m,
        volatility_60d
    )

    strategic_signal = classify_trend(
        trend_score,
        last_price,
        sma200,
        return_6m
    )

    return {
        "engine":
        "V7.9 Strategic Market Engine",

        "ticker":
        ticker,

        "last_market_date":
        str(
            close.index[-1].date()
            if hasattr(
                close.index[-1],
                "date"
            )
            else
            close.index[-1]
        ),

        "strategic_trend_score":
        trend_score,

        "strategic_risk_score":
        risk_score,

        "strategic_signal":
        strategic_signal,

        "metrics": {
            "last_price":
            round(
                last_price,
                2
            ),

            "return_3m_pct":
            (
                round(
                    return_3m,
                    2
                )
                if return_3m is not None
                else None
            ),

            "return_6m_pct":
            (
                round(
                    return_6m,
                    2
                )
                if return_6m is not None
                else None
            ),

            "return_12m_pct":
            (
                round(
                    return_12m,
                    2
                )
                if return_12m is not None
                else None
            ),

            "spy_return_3m_pct":
            (
                round(
                    spy_3m,
                    2
                )
                if spy_3m is not None
                else None
            ),

            "spy_return_6m_pct":
            (
                round(
                    spy_6m,
                    2
                )
                if spy_6m is not None
                else None
            ),

            "relative_strength_3m_pct":
            (
                round(
                    rs_3m,
                    2
                )
                if rs_3m is not None
                else None
            ),

            "relative_strength_6m_pct":
            (
                round(
                    rs_6m,
                    2
                )
                if rs_6m is not None
                else None
            ),

            "sma50":
            (
                round(
                    sma50,
                    2
                )
                if sma50 is not None
                else None
            ),

            "sma100":
            (
                round(
                    sma100,
                    2
                )
                if sma100 is not None
                else None
            ),

            "sma200":
            (
                round(
                    sma200,
                    2
                )
                if sma200 is not None
                else None
            ),

            "above_sma50":
            (
                last_price > sma50
                if sma50 is not None
                else None
            ),

            "above_sma100":
            (
                last_price > sma100
                if sma100 is not None
                else None
            ),

            "above_sma200":
            (
                last_price > sma200
                if sma200 is not None
                else None
            ),

            "max_drawdown_6m_pct":
            round(
                max_drawdown_6m,
                2
            ),

            "max_drawdown_12m_pct":
            round(
                max_drawdown_12m,
                2
            ),

            "volatility_60d_annualized_pct":
            (
                round(
                    volatility_60d,
                    2
                )
                if volatility_60d is not None
                else None
            )
        },

        "data_quality":
        "DAILY_3M_12M"
    }
