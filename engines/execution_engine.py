"""
V6.4 Execution Engine Foundation

Purpose:
Convert investment decisions into executable trade plans.

Mode:
PAPER / MANUAL APPROVAL

Functions:
- Create trade plan
- Generate bracket order structure
- Validate execution readiness
- Prepare broker interface

"""


from datetime import datetime



def create_trade_plan(
        ticker,
        action,
        entry_price,
        stop_loss,
        target_price,
        confidence
):

    trade_plan = {

        "ticker": ticker,

        "action": action,

        "entry_price": entry_price,

        "stop_loss": stop_loss,

        "target_price": target_price,

        "confidence": confidence,

        "order_type":
        "LIMIT",

        "execution_mode":
        "MANUAL_APPROVAL",

        "created":
        datetime.utcnow().isoformat()

    }


    return trade_plan



def calculate_risk_reward(
        entry,
        stop,
        target
):

    risk = entry - stop

    reward = target - entry


    if risk <= 0:

        return 0


    return round(
        reward / risk,
        2
    )



def build_bracket_order(
        trade_plan
):

    rr = calculate_risk_reward(

        trade_plan["entry_price"],

        trade_plan["stop_loss"],

        trade_plan["target_price"]

    )


    bracket = {

        "symbol":
        trade_plan["ticker"],

        "side":
        trade_plan["action"],

        "entry":
        trade_plan["entry_price"],

        "stop_loss":
        trade_plan["stop_loss"],

        "take_profit":
        trade_plan["target_price"],

        "risk_reward":
        rr,

        "status":
        "READY"
        if rr >= 2
        else
        "REVIEW_REQUIRED"

    }


    return bracket



def approve_execution(
        bracket_order
):

    if bracket_order["status"] == "READY":

        return {

            "approved":
            True,

            "message":
            "Trade passed execution checks"

        }


    return {

        "approved":
        False,

        "message":
        "Risk reward below threshold"

    }



def generate_execution_report(
        trade_plans
):

    ready=[]

    review=[]


    for plan in trade_plans:


        bracket = build_bracket_order(
            plan
        )


        approval = approve_execution(
            bracket
        )


        if approval["approved"]:

            ready.append(
                bracket
            )

        else:

            review.append(
                bracket
            )


    return {

        "engine":
        "V6.4 Execution Engine",

        "generated":
        datetime.utcnow().isoformat(),

        "ready_orders":
        ready,

        "review_orders":
        review

    }
