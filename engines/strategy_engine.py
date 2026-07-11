"""
V6.9 Strategy Engine

Adaptive investment strategy selection layer.

Strategies:
- Momentum
- Growth
- Value
- Mean Reversion
- Event Driven

Selects the most suitable strategy
based on market conditions and signals.
"""


from datetime import datetime



def select_strategy(
    market_regime,
    momentum_score,
    growth_score,
    valuation_score,
    catalyst_score
):
    """
    Selects optimal investment strategy
    """


    strategies = {

        "Momentum":
        momentum_score,

        "Growth":
        growth_score,

        "Value":
        valuation_score,

        "Event Driven":
        catalyst_score

    }


    selected = max(
        strategies,
        key=strategies.get
    )


    confidence = strategies[selected]


    if market_regime == "BEAR":

        if selected == "Momentum":

            selected = "Value"


    return {

        "timestamp":
        datetime.utcnow().isoformat(),

        "selected_strategy":
        selected,

        "confidence":
        confidence,

        "available_scores":
        strategies,

        "market_regime":
        market_regime

    }




def strategy_parameters(
    strategy
):
    """
    Returns strategy behavior
    """


    if strategy == "Momentum":

        return {

            "holding_period":
            "SHORT_TERM",

            "risk_level":
            "HIGH",

            "entry_style":
            "BREAKOUT"

        }



    if strategy == "Growth":

        return {

            "holding_period":
            "MEDIUM_TERM",

            "risk_level":
            "MEDIUM",

            "entry_style":
            "ACCUMULATION"

        }



    if strategy == "Value":

        return {

            "holding_period":
            "LONG_TERM",

            "risk_level":
            "LOW",

            "entry_style":
            "DISCOUNT_ENTRY"

        }



    if strategy == "Event Driven":

        return {

            "holding_period":
            "EVENT_WINDOW",

            "risk_level":
            "MEDIUM",

            "entry_style":
            "CATALYST_ENTRY"

        }



    return {

        "holding_period":
        "UNKNOWN",

        "risk_level":
        "UNKNOWN",

        "entry_style":
        "NONE"

    }




def strategy_snapshot(
    strategy_data
):
    """
    Creates strategy intelligence report
    """


    return {

        "engine":
        "V6.9",

        "timestamp":
        datetime.utcnow().isoformat(),

        "strategy":
        strategy_data.get(
            "selected_strategy"
        ),

        "confidence":
        strategy_data.get(
            "confidence"
        )

    }
