"""
V6.0 Decision Engine

Purpose:
Convert intelligence scores into portfolio actions.

Outputs:
- action
- entry zone
- stop loss
- target
- confidence
- risk reward
"""


def generate_decision(
    alpha_score,
    market_score,
    catalyst_score,
    risk_score,
    price
):

    decision = {
        "action": "WATCH",
        "confidence": 0,
        "entry_zone": None,
        "stop_loss": None,
        "target_price": None,
        "risk_reward": None
    }


    # Strong bullish setup

    if alpha_score >= 80 and risk_score >= 60:

        decision["action"] = "BUY"

        decision["confidence"] = min(
            95,
            alpha_score
        )

        decision["entry_zone"] = {
            "low": round(price * 0.97,2),
            "high": round(price * 1.01,2)
        }

        decision["stop_loss"] = round(
            price * 0.92,
            2
        )

        decision["target_price"] = round(
            price * 1.20,
            2
        )


    # Accumulate zone

    elif alpha_score >= 65:

        decision["action"] = "ACCUMULATE"

        decision["confidence"] = alpha_score

        decision["entry_zone"] = {
            "low": round(price * 0.95,2),
            "high": round(price,2)
        }

        decision["stop_loss"] = round(
            price * 0.90,
            2
        )

        decision["target_price"] = round(
            price * 1.15,
            2
        )


    # Neutral

    elif alpha_score >= 45:

        decision["action"] = "WATCH"

        decision["confidence"] = alpha_score


    # Weak setup

    else:

        decision["action"] = "AVOID"

        decision["confidence"] = (
            100 - alpha_score
        )


    # Risk reward calculation

    if (
        decision["target_price"]
        and decision["stop_loss"]
    ):

        upside = (
            decision["target_price"]
            - price
        )

        downside = (
            price
            - decision["stop_loss"]
        )

        if downside > 0:

            decision["risk_reward"] = round(
                upside / downside,
                2
            )


    return decision
