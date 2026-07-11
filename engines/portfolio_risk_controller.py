"""
V6.7 Portfolio Risk Controller

Institutional portfolio risk management layer.

Functions:
- Position sizing
- Portfolio exposure control
- Sector concentration check
- Drawdown protection
- Trade approval gate
"""


from datetime import datetime


MAX_POSITION_SIZE = 0.10
MAX_PORTFOLIO_RISK = 0.20
MAX_SECTOR_EXPOSURE = 0.35
MAX_DRAWDOWN_LIMIT = -0.10



def calculate_position_size(
    portfolio_value,
    risk_level
):
    """
    Calculates maximum position size
    """

    if portfolio_value <= 0:
        return 0


    if risk_level == "HIGH":
        return portfolio_value * 0.03


    if risk_level == "MEDIUM":
        return portfolio_value * 0.05


    return portfolio_value * MAX_POSITION_SIZE




def check_sector_exposure(
    current_sector_exposure,
    new_position_sector
):
    """
    Controls sector concentration
    """

    exposure = current_sector_exposure.get(
        new_position_sector,
        0
    )


    if exposure >= MAX_SECTOR_EXPOSURE:

        return {

            "approved": False,

            "reason":
            "Sector exposure limit exceeded"

        }


    return {

        "approved": True,

        "reason":
        "Sector exposure acceptable"

    }




def check_drawdown(
    portfolio_return
):
    """
    Portfolio drawdown protection
    """

    if portfolio_return <= MAX_DRAWDOWN_LIMIT:

        return {

            "approved": False,

            "reason":
            "Portfolio drawdown protection activated"

        }


    return {

        "approved": True,

        "reason":
        "Drawdown within limits"

    }




def approve_trade(
    ticker,
    position_size,
    sector_check,
    drawdown_check
):
    """
    Final risk approval gate
    """


    approved = (

        position_size > 0

        and

        sector_check.get("approved")

        and

        drawdown_check.get("approved")

    )


    return {

        "ticker":
        ticker,


        "timestamp":
        datetime.utcnow().isoformat(),


        "approved":
        approved,


        "position_size":
        position_size,


        "risk_status":

        "APPROVED"
        if approved
        else
        "BLOCKED"

    }




def portfolio_risk_snapshot(
    portfolio_value,
    total_exposure,
    cash_position
):
    """
    Creates portfolio risk overview
    """


    return {

        "timestamp":
        datetime.utcnow().isoformat(),


        "portfolio_value":
        portfolio_value,


        "total_exposure":
        total_exposure,


        "cash_position":
        cash_position,


        "risk_state":

        "HEALTHY"
        if total_exposure < MAX_PORTFOLIO_RISK
        else
        "HIGH_RISK"

    }
