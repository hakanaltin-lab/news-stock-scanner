"""
AURORA AI CIO v3.1

L0 Data Foundation

Data Quality Gate v1.0

Purpose:
Validate incoming data before
AI analysis and decision making.

Controls:
- Missing data
- Data freshness
- Source reliability
- Data integrity
- Bias warnings
"""


from datetime import datetime



def check_missing_data(
    data
):
    """
    Checks missing values.
    """


    if not data:

        return "INVALID"


    missing_fields = []


    for key, value in data.items():

        if value is None:

            missing_fields.append(key)



    if missing_fields:

        return {

            "status": "WARNING",

            "missing_fields": missing_fields

        }



    return {

        "status": "VALID",

        "missing_fields": []

    }





def check_data_freshness(
    data_timestamp,
    max_age_minutes=60
):
    """
    Checks if data is fresh enough.
    """


    current_time = datetime.utcnow()


    age = (

        current_time - data_timestamp

    ).total_seconds() / 60



    if age <= max_age_minutes:

        return "FRESH"


    return "STALE"





def check_source_reliability(
    source_score
):
    """
    Validates data source quality.

    Score:
    0-100
    """


    if source_score >= 90:

        return "HIGH"


    elif source_score >= 70:

        return "MEDIUM"


    return "LOW"





def check_survivorship_bias(
    dataset_type
):
    """
    Detects possible backtest bias.
    """


    biased_sources = [

        "CURRENT_ONLY_DATABASE",

        "TODAY_COMPONENTS_ONLY"

    ]


    if dataset_type in biased_sources:

        return "BIAS_WARNING"



    return "CLEAN"





def run_quality_check(
    data,
    data_timestamp,
    source_score,
    dataset_type
):
    """
    Main Data Quality Gate.
    """


    missing_check = check_missing_data(

        data

    )


    freshness = check_data_freshness(

        data_timestamp

    )


    reliability = check_source_reliability(

        source_score

    )


    bias_check = check_survivorship_bias(

        dataset_type

    )



    overall_status = "APPROVED"



    if (

        missing_check["status"] == "WARNING"

        or

        freshness == "STALE"

        or

        reliability == "LOW"

        or

        bias_check == "BIAS_WARNING"

    ):

        overall_status = "REVIEW"



    return {


        "engine":

        "L0.1 Data Quality Gate v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "overall_status":

        overall_status,


        "missing_check":

        missing_check,


        "freshness":

        freshness,


        "source_reliability":

        reliability,


        "survivorship_bias_check":

        bias_check

    }
