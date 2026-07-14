"""
V10.6.3 Portfolio Master Controller

Purpose:
Central orchestration layer for portfolio management.

Functions:
- Combine portfolio decisions
- Aggregate positions
- Evaluate portfolio health
- Generate CIO portfolio output
"""


from datetime import datetime





def evaluate_position_status(
    allocation_status
):
    """
    Converts allocation result into status
    """


    if allocation_status == "APPROVED":

        return "READY"



    elif allocation_status == "LIMITED":

        return "REVIEW"



    return "BLOCKED"





def calculate_portfolio_health(
    positions,
    risk_status
):
    """
    Calculates overall portfolio condition
    """


    if not positions:

        return "NO_POSITIONS"



    if risk_status == "CONTROLLED":

        return "HEALTHY"



    if risk_status == "ELEVATED":

        return "MONITOR"



    return "RESTRICTED"





def assemble_portfolio(
    positions
):
    """
    Builds portfolio allocation summary
    """


    total_weight = sum(

        position.get(

            "target_weight_percent",

            0

        )

        for position in positions

    )



    return {


        "positions":

        positions,


        "number_of_positions":

        len(positions),


        "total_weight":

        total_weight

    }





def generate_portfolio_master_output(
    portfolio_name,
    positions,
    risk_status,
    allocation_status
):
    """
    Main portfolio controller
    """


    portfolio_summary = assemble_portfolio(

        positions

    )


    portfolio_health = calculate_portfolio_health(

        positions,

        risk_status

    )


    return {


        "engine":

        "V10.6.3 Portfolio Master Controller",


        "timestamp":

        datetime.utcnow().isoformat(),


        "portfolio_name":

        portfolio_name,


        "portfolio":

        portfolio_summary,


        "risk_status":

        risk_status,


        "allocation_status":

        allocation_status,


        "portfolio_health":

        portfolio_health,


        "system_status":

        evaluate_position_status(

            allocation_status

        )

    }
