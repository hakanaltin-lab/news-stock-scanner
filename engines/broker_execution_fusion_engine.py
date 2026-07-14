"""
V10.8.1 Broker Execution Fusion Engine

Purpose:
Connect AI CIO decisions with broker execution workflow.

Functions:
- Decision validation
- Risk gate
- Order preparation
- Execution lifecycle tracking
"""


from datetime import datetime



def validate_execution_request(
    ticker,
    action,
    risk_status,
    cash_available
):
    """
    Final execution validation
    """


    if action not in [

        "BUY",

        "SELL"

    ]:

        return {

            "status": "REJECTED",

            "reason": "INVALID_ACTION"

        }



    if risk_status != "APPROVED":

        return {

            "status": "REJECTED",

            "reason": "RISK_NOT_APPROVED"

        }



    if cash_available <= 0 and action == "BUY":

        return {

            "status": "REJECTED",

            "reason": "INSUFFICIENT_CASH"

        }



    return {

        "status": "EXECUTION_READY",

        "ticker": ticker

    }





def create_execution_order(
    ticker,
    action,
    quantity,
    order_type="LIMIT"
):
    """
    Creates broker ready order
    """


    return {


        "ticker":

        ticker,


        "side":

        action,


        "quantity":

        quantity,


        "order_type":

        order_type,


        "execution_state":

        "CREATED"

    }





def update_execution_state(
    order,
    new_state
):
    """
    Updates execution lifecycle
    """


    valid_states = [

        "CREATED",

        "VALIDATED",

        "SUBMITTED",

        "FILLED",

        "CANCELLED"

    ]



    if new_state in valid_states:

        order["execution_state"] = new_state



    order["timestamp"] = datetime.utcnow().isoformat()



    return order





def generate_execution_feedback(
    order
):
    """
    Sends execution result back to CIO
    """


    return {


        "engine":

        "V10.8.1 Broker Execution Fusion Engine",


        "ticker":

        order["ticker"],


        "execution_state":

        order["execution_state"],


        "portfolio_update_required":

        True,


        "dashboard_update_required":

        True

    }
