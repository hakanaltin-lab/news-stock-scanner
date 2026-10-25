"""
V7.4 AURORA Market Regime Engine

Purpose:
- Detect the broad US equity market regime
- Use SPY as the primary market anchor
- Use QQQ and IWM for breadth / risk-appetite confirmation
- Use VIX as a volatility stress signal
- Produce a regime policy for capital allocation

Regimes:
- BULL
- NORMAL
- BEAR
- HIGH_VOLATILITY

Important:
- Regime logic is deterministic.
- This engine does not send broker orders.
- It tightens risk in weak regimes and only adjusts sizing/cash policy
  in strong regimes; it does not convert weak setups into BUY signals.
"""

from datetime import datetime, timezone

import numpy as np
import yfinance as yf


MARKET_TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "VIX": "^VIX"
}


REGIME_POLICIES = {
    "BULL": {
        "minimum_cash_reserve_pct": 10.0,
        "position_size_multiplier": 1.10,
        "max_new_position_weight_pct": 6.0,
        "buy_alpha_min": 72.0,
        "accumulate_alpha_min": 64.0,
        "minimum_risk_score": 55.0
    },
    "NORMAL": {
        "minimum_cash_reserve_pct": 20.0,
        "position_size_multiplier": 1.00,
        "max_new_position_weight_pct": 5.0,
        "buy_alpha_min": 75.0,
        "accumulate_alpha_min": 65.0,
        "minimum_risk_score": 60.0
    },
    "BEAR": {
        "minimum_cash_reserve_pct": 35.0,
        "position_size_multiplier": 0.75,
        "max_new_position_weight_pct": 4.0,
        "buy_alpha_min": 82.0,
        "accumulate_alpha_min": 75.0,
        "minimum_risk_score": 70.0
    },
    "HIGH_VOLATILITY": {
        "minimum_cash_reserve_pct": 45.0,
        "position_size_multiplier": 0.60,
        "max_new_position_weight_pct": 3.0,
        "buy_alpha_min": 88.0,
        "accumulate_alpha_min": 80.0,
        "minimum_risk_score": 75.0
    }
}


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percentage_return(series, periods):
    if series is None or len(series) <= periods:
        return 0.0

    start = safe_float(
        series.iloc[-(periods + 1)]
    )

    end = safe_float(
        series.iloc[-1]
    )

    if start <= 0:
        return 0.0

    return (
        end / start - 1
    ) * 100


def moving_average(series, window):
    if series is None or len(series) < window:
        return 0.0

    return safe_float(
        series.tail(window).mean()
    )


def realized_volatility(series, window=20):
    if series is None or len(series) < window + 1:
        return 0.0

    returns = (
        series.pct_change()
        .dropna()
        .tail(window)
    )

    if returns.empty:
        return 0.0

    return safe_float(
        returns.std()
        *
        np.sqrt(252)
        *
        100
    )


def fetch_daily_history(ticker):
    try:
        history = yf.Ticker(
            ticker
        ).history(
            period="1y",
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

        return close.dropna()

    except Exception:
        return None


def build_asset_metrics(ticker):
    close = fetch_daily_history(
        ticker
    )

    if close is None or close.empty:
        return {
            "ticker": ticker,
            "status": "NO_DATA"
        }

    last_price = safe_float(
        close.iloc[-1]
    )

    sma20 = moving_average(
        close,
        20
    )

    sma50 = moving_average(
        close,
        50
    )

    sma200 = moving_average(
        close,
        200
    )

    return_5d = percentage_return(
        close,
        5
    )

    return_20d = percentage_return(
        close,
        20
    )

    return_60d = percentage_return(
        close,
        60
    )

    vol20 = realized_volatility(
        close,
        20
    )

    market_date = None

    try:
        market_date = (
            close.index[-1]
            .date()
            .isoformat()
        )
    except Exception:
        market_date = None

    return {
        "ticker": ticker,
        "status": "OK",
        "market_date": market_date,
        "last_price": round(
            last_price,
            2
        ),
        "return_5d_pct": round(
            return_5d,
            2
        ),
        "return_20d_pct": round(
            return_20d,
            2
        ),
        "return_60d_pct": round(
            return_60d,
            2
        ),
        "sma20": round(
            sma20,
            2
        ),
        "sma50": round(
            sma50,
            2
        ),
        "sma200": round(
            sma200,
            2
        ),
        "above_sma20": (
            last_price > sma20
            if sma20 > 0
            else False
        ),
        "above_sma50": (
            last_price > sma50
            if sma50 > 0
            else False
        ),
        "above_sma200": (
            last_price > sma200
            if sma200 > 0
            else False
        ),
        "realized_volatility_20d_pct": round(
            vol20,
            2
        )
    }


def calculate_regime_score(
    spy,
    qqq,
    iwm,
    vix
):
    score = 0.0

    # Primary SPY trend: 45 points
    if spy.get("above_sma20"):
        score += 10

    if spy.get("above_sma50"):
        score += 15

    if spy.get("above_sma200"):
        score += 20

    # SPY momentum: 25 points
    if safe_float(
        spy.get("return_20d_pct")
    ) > 0:
        score += 10

    if safe_float(
        spy.get("return_60d_pct")
    ) > 0:
        score += 15

    # Breadth / risk appetite: 20 points
    for asset in [qqq, iwm]:
        if asset.get("above_sma50"):
            score += 5

        if safe_float(
            asset.get("return_20d_pct")
        ) > 0:
            score += 5

    # Volatility environment: 10 points
    vix_level = safe_float(
        vix.get("last_price")
    )

    if vix_level <= 0:
        score += 5
    elif vix_level < 20:
        score += 10
    elif vix_level < 25:
        score += 7
    elif vix_level < 30:
        score += 4

    return round(
        max(
            0,
            min(
                100,
                score
            )
        ),
        1
    )


def classify_regime(
    regime_score,
    spy,
    qqq,
    iwm,
    vix
):
    vix_level = safe_float(
        vix.get("last_price")
    )

    spy_20d = safe_float(
        spy.get("return_20d_pct")
    )

    spy_60d = safe_float(
        spy.get("return_60d_pct")
    )

    spy_realized_vol = safe_float(
        spy.get(
            "realized_volatility_20d_pct"
        )
    )

    high_volatility = (
        vix_level >= 30
        or
        spy_realized_vol >= 30
        or
        (
            vix_level >= 25
            and
            spy_20d <= -5
        )
    )

    if high_volatility:
        return "HIGH_VOLATILITY"

    bear_structure = (
        not spy.get("above_sma200")
        and
        spy_20d < 0
        and
        spy_60d < 0
    )

    if (
        bear_structure
        or
        regime_score < 40
    ):
        return "BEAR"

    breadth_confirmations = sum([
        1 if qqq.get("above_sma50") else 0,
        1 if safe_float(
            qqq.get("return_20d_pct")
        ) > 0 else 0,
        1 if iwm.get("above_sma50") else 0,
        1 if safe_float(
            iwm.get("return_20d_pct")
        ) > 0 else 0
    ])

    bull_structure = (
        spy.get("above_sma20")
        and
        spy.get("above_sma50")
        and
        spy.get("above_sma200")
        and
        spy_20d > 0
        and
        spy_60d > 0
        and
        breadth_confirmations >= 3
        and
        (
            vix_level <= 0
            or
            vix_level < 25
        )
        and
        regime_score >= 70
    )

    if bull_structure:
        return "BULL"

    return "NORMAL"


def build_reasons(
    regime,
    spy,
    qqq,
    iwm,
    vix
):
    reasons = []

    if spy.get("above_sma200"):
        reasons.append(
            "SPY is above its 200-day trend"
        )
    else:
        reasons.append(
            "SPY is below its 200-day trend"
        )

    spy_20d = safe_float(
        spy.get("return_20d_pct")
    )

    spy_60d = safe_float(
        spy.get("return_60d_pct")
    )

    reasons.append(
        "SPY 20D momentum "
        +
        (
            "positive"
            if spy_20d > 0
            else
            "negative"
        )
    )

    reasons.append(
        "SPY 60D momentum "
        +
        (
            "positive"
            if spy_60d > 0
            else
            "negative"
        )
    )

    breadth_positive = sum([
        1 if qqq.get("above_sma50") else 0,
        1 if iwm.get("above_sma50") else 0
    ])

    reasons.append(
        f"QQQ/IWM above SMA50: {breadth_positive}/2"
    )

    vix_level = safe_float(
        vix.get("last_price")
    )

    if vix_level > 0:
        reasons.append(
            f"VIX level: {round(vix_level, 2)}"
        )

    if regime in [
        "BEAR",
        "HIGH_VOLATILITY"
    ]:
        reasons.append(
            "Defensive capital policy activated"
        )

    elif regime == "BULL":
        reasons.append(
            "Risk-on capital policy activated"
        )

    else:
        reasons.append(
            "Balanced capital policy activated"
        )

    return reasons


def analyze_market_regime():
    spy = build_asset_metrics(
        MARKET_TICKERS["SPY"]
    )

    qqq = build_asset_metrics(
        MARKET_TICKERS["QQQ"]
    )

    iwm = build_asset_metrics(
        MARKET_TICKERS["IWM"]
    )

    vix = build_asset_metrics(
        MARKET_TICKERS["VIX"]
    )

    valid_core_assets = [
        item
        for item in [
            spy,
            qqq,
            iwm
        ]
        if item.get("status") == "OK"
    ]

    if not valid_core_assets:
        regime = "NORMAL"
        regime_score = 50.0
        data_quality = "FALLBACK"
    else:
        regime_score = calculate_regime_score(
            spy,
            qqq,
            iwm,
            vix
        )

        regime = classify_regime(
            regime_score,
            spy,
            qqq,
            iwm,
            vix
        )

        data_quality = "LAST_MARKET_SESSION"

    policy = dict(
        REGIME_POLICIES[
            regime
        ]
    )

    market_date = (
        spy.get("market_date")
        or
        qqq.get("market_date")
        or
        iwm.get("market_date")
    )

    return {
        "engine":
        "V7.4 Market Regime Engine",

        "timestamp":
        datetime.now(
            timezone.utc
        ).isoformat(),

        "market_date":
        market_date,

        "regime":
        regime,

        "regime_score":
        regime_score,

        "data_quality":
        data_quality,

        "policy":
        policy,

        "metrics": {
            "SPY": spy,
            "QQQ": qqq,
            "IWM": iwm,
            "VIX": vix
        },

        "reasons":
        build_reasons(
            regime,
            spy,
            qqq,
            iwm,
            vix
        )
    }
