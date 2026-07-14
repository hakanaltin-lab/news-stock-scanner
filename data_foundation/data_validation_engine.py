"""
AURORA AI CIO v3.1

L0 Data Foundation

Data Validation Engine v1.0

Purpose:
Validate data integrity before
AI analysis.

Controls:
- Price anomalies
- Outliers
- Duplicate data
- Source conflicts
- Confidence scoring
"""


from datetime import datetime



def check_price_anomaly(
    current_price,
    previous_price,
    threshold=20
):
    """
    Detects abnormal price movements.
    """

    if previous_price == 0:

        return "INVALID"


    change = (

        abs(current_price - previous_price)

        /

        previous_price

    ) * 100


    if change >= threshold:

        return "ANOMALY"


    return "NORMAL"





def check_duplicate_data(
    records
):
    """
    Detects duplicate records.
    """

    if len(records) != len(set(records)):

        return "DUPLICATE_FOUND"


    return "CLEAN"





def check_outlier(
    value,
    average_value,
    tolerance=3
):
    """
    Detects extreme deviations.
    """


    if average_value == 0:

        return "INVALID"


    deviation = abs(

        value - average_value

    ) / average_value



    if deviation > tolerance:

        return "OUTLIER"



    return "NORMAL"





def check_source_conflict(
    source_values
):
    """
    Compares multiple data sources.
    """


    if len(set(source_values)) > 1:

        return "SOURCE_CONFLICT"


    return "CONSISTENT"





def calculate_confidence_score(
    checks
):
    """
    Calculates overall data confidence.
    """


    score = 100



    for check in checks:


        if check in [

            "ANOMALY",

            "OUTLIER",

            "DUPLICATE_FOUND",

            "SOURCE_CONFLICT"

        ]:

            score -= 20



    return max(

        0,

        score

    )





def run_data_validation(
    current_price,
    previous_price,
    records,
    value,
    average_value,
    source_values
):
    """
    Main validation engine.
    """


    price_check = check_price_anomaly(

        current_price,

        previous_price

    )


    duplicate_check = check_duplicate_data(

        records

    )


    outlier_check = check_outlier(

        value,

        average_value

    )


    source_check = check_source_conflict(

        source_values

    )


    confidence = calculate_confidence_score(

        [

            price_check,

            duplicate_check,

            outlier_check,

            source_check

        ]

    )



    if confidence >= 80:

        decision = "APPROVED"


    elif confidence >= 50:

        decision = "REVIEW"


    else:

        decision = "REJECT"



    return {


        "engine":

        "L0.3 Data Validation Engine v1.0",


        "timestamp":

        datetime.utcnow().isoformat(),


        "price_check":

        price_check,


        "duplicate_check":

        duplicate_check,


        "outlier_check":

        outlier_check,


        "source_check":

        source_check,


        "confidence_score":

        confidence,


        "decision":

        decision

    }
