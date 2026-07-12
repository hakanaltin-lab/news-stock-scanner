"""
V10.1 Live Market Data Connector Layer

Purpose:
Normalize live market information
for AI CIO Operating System.

Functions:
- Price data processing
- Volume intelligence
- Market status detection
- Data normalization
"""


from datetime import datetime



def calculate_volume_signal(
    current_volume,
    average_volume
):
    """
    Detects unusual volume activity
    """


    if average_volume == 0:

        return {


            "volume_change":

            0,


            "signal":

            "UNKNOWN"

        }



    volume_change = round(

        (

            (current_volume - average_volume)

            /

            average_volume

        ) * 100,

        2

    )



    if volume_change >= 100:

        signal = "ACCUMULATION"



    elif volume_change >= 50:

        signal = "HIGH_INTEREST"



    else:

        signal = "NORMAL"



    return {


        "volume_change":

        volume_change,


        "signal":

        signal

    }





def calculate_price_change(
    previous_price,
    current_price
):
    """
    Calculates price movement
    """


    if previous_price == 0:

        return 0



    return round(

        (

            (current_price - previous_price)

            /

            previous_price

        ) * 100,

        2

    )





def normalize_market_data(
    ticker,
    current_price,
    previous_price,
    current_volume,
    average_volume,
    market_status="OPEN"
):
    """
    Creates normalized market data object
    """


    volume_data = calculate_volume_signal(

        current_volume,

        average_volume

    )


    price_change = calculate_price_change(

        previous_price,

        current_price

    )



    return {


        "engine":

        "V10.1 Live Market Data Connector",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "price":

        current_price,


        "daily_change_percent":

        price_change,


        "volume":

        volume_data,


        "market_status":

        market_status

    }





def validate_market_feed(
    market_data
):
    """
    Checks data quality
    """


    required_fields = [

        "ticker",

        "price",

        "market_status"

    ]



    for field in required_fields:


        if field not in market_data:

            return {

                "status":

                "INVALID_DATA",

                "missing":

                field

            }



    return {


        "status":

        "VALID"


    }
