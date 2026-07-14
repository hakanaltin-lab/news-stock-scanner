"""
AURORA AI CIO v3.1

L6 Independent Risk Authority

Kill Switch Controller v1.0

Purpose:
Emergency protection layer.

Controls:
- Trading halt
- Order cancellation
- Execution freeze
- Human override
- Recovery mode
"""


from datetime import datetime



SYSTEM_STATUS = "ACTIVE"



def activate_kill_switch(
    trigger_reason,
    severity
):
    """
    Activates emergency protection.
    """


    global SYSTEM_STATUS


    SYSTEM_STATUS = "HALTED"


    return {


        "engine":

        "L6.7 Kill Switch Controller v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "status":

        SYSTEM_STATUS,


        "trigger_reason":

        trigger_reason,


        "severity":

        severity,


        "actions":

        [

            "CANCEL_PENDING_ORDERS",

            "FREEZE_NEW_TRADES",

            "REQUIRE_HUMAN_APPROVAL"

        ]

    }





def deactivate_kill_switch(
    approved_by
):
    """
    Restores system after human approval.
    """


    global SYSTEM_STATUS


    SYSTEM_STATUS = "ACTIVE"


    return {


        "engine":

        "L6.7 Kill Switch Controller v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "status":

        SYSTEM_STATUS,


        "recovery_approved_by":

        approved_by,


        "action":

        "RESUME_OPERATIONS"

    }





def check_emergency_condition(
    risk_status
):
    """
    Determines if emergency action is required.
    """


    critical_conditions = [


        "EMERGENCY_HALT",

        "BLOCK",

        "SYSTEM_FAILURE",

        "EXTREME_MARKET_EVENT"

    ]



    if risk_status in critical_conditions:


        return activate_kill_switch(

            risk_status,

            "CRITICAL"

        )



    return {


        "status":

        SYSTEM_STATUS,


        "action":

        "NO_ACTION_REQUIRED"

    }





def get_system_status():
    """
    Returns current system state.
    """


    return {


        "timestamp":

        datetime.utcnow().isoformat(),


        "system_status":

        SYSTEM_STATUS

    }
