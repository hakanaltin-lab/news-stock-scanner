"""
V8.2 CIO Connector Layer

Purpose:
Connect Autonomous CIO Brain outputs
with dashboard and reporting systems.

Flow:

V8.0 CIO Brain
        ↓
V8.2 CIO Connector
        ↓
cio_output.json
        ↓
Dashboard
"""


import json

from datetime import datetime



OUTPUT_FILE = "docs/cio_output.json"




def format_cio_output(
    cio_result
):
    """
    Converts CIO decision into dashboard format
    """

    return {

        "engine":
        "V8.2 CIO Connector",


        "timestamp":
        datetime.utcnow().isoformat(),


        "decision":

        {


            "ticker":

            cio_result.get(
                "ticker"
            ),


            "cio_score":

            cio_result.get(
                "cio_score",
                0
            ),


            "final_decision":

            cio_result.get(
                "final_decision",
                "NO_DECISION"
            ),


            "investment_thesis":

            cio_result.get(
                "investment_thesis",
                ""
            )

        }

    }





def save_cio_output(
    cio_result
):
    """
    Saves CIO output for dashboard
    """


    output = format_cio_output(
        cio_result
    )


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:


        json.dump(

            output,

            file,

            indent=4

        )


    return output





def load_cio_output():
    """
    Reads latest CIO decision
    """


    try:

        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8"
        ) as file:


            return json.load(
                file
            )


    except FileNotFoundError:


        return {


            "status":

            "NO_CIO_OUTPUT"

        }





def generate_dashboard_signal(
    cio_output
):
    """
    Creates simple dashboard signal
    """


    decision = cio_output.get(
        "decision",
        {}
    ).get(
        "final_decision",
        ""
    )



    if decision in [
        "ACCUMULATE",
        "BUY_REDUCED"
    ]:

        return "GREEN"



    if decision == "WATCH":

        return "YELLOW"



    return "RED"
