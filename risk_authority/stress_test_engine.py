"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Stress Testing Engine v1.0

Purpose:
Simulate extreme market scenarios
and measure portfolio resilience.

Scenarios:
- Market crash
- Sector shock
- Interest rate shock
- Liquidity crisis
- Single asset collapse
"""


from datetime import datetime



def calculate_scenario_impact(
    portfolio_value,
    shock_percentage
):
    """
    Calculates estimated portfolio loss.
    """

    loss_amount = (

        portfolio_value

        *

        abs(shock_percentage)

        /

        100

    )

    return round(
        loss_amount,
        2
    )





def evaluate_scenario_severity(
    shock_percentage
):
    """
    Determines stress severity.
    """

    shock = abs(shock_percentage)


    if shock >= 30:

        return "CRITICAL"


    elif shock >= 20:

        return "HIGH"


    elif shock >= 10:

        return "MEDIUM"


    return "LOW"





def determine_stress_action(
    severity
):
    """
    CRO action recommendation.
    """

    if severity == "CRITICAL":

        return "BLOCK_AND_REDUCE"


    elif severity == "HIGH":

        return "REDUCE_EXPOSURE"


    elif severity == "MEDIUM":

        return "REVIEW"


    return "ACCEPT"





def run_stress_test(
    scenario_name,
    portfolio_value,
    shock_percentage
):
    """
    Executes single stress scenario.
    """


    loss_amount = calculate_scenario_impact(

        portfolio_value,

        shock_percentage

    )


    severity = evaluate_scenario_severity(

        shock_percentage

    )


    action = determine_stress_action(

        severity

    )


    return {


        "engine":

        "L6.5 Stress Testing Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "scenario":

        scenario_name,


        "portfolio_value":

        portfolio_value,


        "shock_percentage":

        shock_percentage,


        "estimated_loss":

        loss_amount,


        "severity":

        severity,


        "risk_action":

        action

    }





def run_multiple_stress_tests(
    portfolio_value,
    scenarios
):
    """
    Runs multiple crisis simulations.
    """


    results = []


    for scenario in scenarios:


        result = run_stress_test(

            scenario["name"],

            portfolio_value,

            scenario["shock"]

        )


        results.append(result)



    return results
