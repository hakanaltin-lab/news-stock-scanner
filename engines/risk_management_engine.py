"""
V6.3 Risk Management Engine

Purpose:
Portfolio risk control layer.

Functions:
- Position sizing
- Stop loss calculation
- Risk/reward validation
- Portfolio exposure control

"""


from datetime import datetime



def calculate_position_size(
        capital,
        risk_percent,
        entry_price,
        stop_loss
):

    risk_amount = (
        capital *
        risk_percent
        /
        100
    )


    loss_per_share = (
        entry_price -
        stop_loss
    )


    if loss_per_share <= 0:
        return 0


    shares = (
        risk_amount /
        loss_per_share
    )


    return int(shares)



def calculate_stop_loss(
        entry_price,
        risk_percent=5
):

    stop = (

        entry_price *
        (1 - risk_percent/100)

    )

    return round(stop,2)



def validate_trade_risk(
        entry,
        target,
        stop
):

    risk = (
        entry -
        stop
    )

    reward = (
        target -
        entry
    )


    if risk <= 0:
        return {
            "approved":False,
            "reason":
            "Invalid stop"
        }


    rr = reward/risk


    return {

        "approved":
        rr >= 2,

        "risk_reward":
        round(rr,2),

        "status":
        "ACCEPTED"
        if rr >=2
        else
        "REJECTED"

    }



def generate_risk_report(
        trades
):

    approved=[]

    rejected=[]


    for trade in trades:

        result = validate_trade_risk(
            trade["entry"],
            trade["target"],
            trade["stop"]
        )


        if result["approved"]:
            approved.append(
                trade
            )

        else:
            rejected.append(
                trade
            )


    return {

        "engine":
        "V6.3 Risk Management Engine",

        "generated":
        datetime.utcnow().isoformat(),

        "approved_trades":
        approved,

        "rejected_trades":
        rejected

    }
