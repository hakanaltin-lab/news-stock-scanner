"""
V6.4 Normalized Market Scoring Engine

Purpose:
- Convert market data into a true 0-100 score
- Score percentage momentum
- Score VWAP positioning
- Score volume confirmation

Higher market_score = stronger technical setup
"""


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


def calculate_momentum_score(
    momentum_pct
):

    """
    -10% or worse -> near 0
    0%             -> 50
    +10% or better -> near 100
    """

    score = (
        50
        + momentum_pct * 5
    )

    return clamp(
        score
    )


def calculate_vwap_score(
    vwap_distance_pct
):

    """
    -5% below VWAP -> near 0
    At VWAP        -> 50
    +5% above      -> near 100
    """

    score = (
        50
        + vwap_distance_pct * 10
    )

    return clamp(
        score
    )


def calculate_volume_confirmation_score(
    momentum_pct,
    vwap_distance_pct,
    volume_ratio
):

    """
    Rising volume confirms the prevailing direction.

    Strong price + strong volume:
        positive confirmation

    Weak price + strong volume:
        negative confirmation
    """

    volume_ratio = max(
        0,
        min(
            volume_ratio,
            5
        )
    )


    bullish = (
        momentum_pct > 0
        and vwap_distance_pct > 0
    )


    bearish = (
        momentum_pct < 0
        and vwap_distance_pct < 0
    )


    if bullish:

        score = (
            50
            + (
                volume_ratio - 1
            ) * 25
        )

        return clamp(
            score,
            35,
            100
        )


    if bearish:

        score = (
            50
            - (
                volume_ratio - 1
            ) * 25
        )

        return clamp(
            score,
            0,
            65
        )


    return 50


def calculate_market_score(
    snapshot
):

    momentum_pct = snapshot.get(
        "momentum_pct",
        0
    )


    vwap_distance_pct = snapshot.get(
        "vwap_distance_pct",
        0
    )


    volume_ratio = snapshot.get(
        "volume_ratio",
        1
    )


    momentum_score = (
        calculate_momentum_score(
            momentum_pct
        )
    )


    vwap_score = (
        calculate_vwap_score(
            vwap_distance_pct
        )
    )


    volume_score = (
        calculate_volume_confirmation_score(
            momentum_pct,
            vwap_distance_pct,
            volume_ratio
        )
    )


    market_score = (

        momentum_score * 0.50

        + vwap_score * 0.30

        + volume_score * 0.20

    )


    return round(
        clamp(
            market_score
        ),
        1
    )
