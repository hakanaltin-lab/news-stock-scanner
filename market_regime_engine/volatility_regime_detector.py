"""
AURORA AI CIO v3.1

L1 Market Regime Engine

Volatility Regime Detector v1.0

Purpose:
Detect volatility environment.

Outputs:
- LOW_VOLATILITY
- NORMAL_VOLATILITY
- HIGH_VOLATILITY
- VOLATILITY_SPIKE
"""


from datetime import datetime



class VolatilityRegimeDetector:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_vix_level(
        self,
        vix_value
    ):
        """
        Classifies VIX level.
        """


        if vix_value >= 35:

            return "EXTREME"


        elif vix_value >= 25:

            return "HIGH"


        elif vix_value <= 15:

            return "LOW"


        return "NORMAL"





    def detect_volatility_change(
        self,
        current_vix,
        previous_vix
    ):
        """
        Detects volatility expansion.
        """


        if previous_vix == 0:

            return "UNKNOWN"


        change = (

            (current_vix - previous_vix)

            /

            previous_vix

        ) * 100


        if change >= 30:

            return "VOLATILITY_SPIKE"


        elif change >= 10:

            return "VOLATILITY_EXPANDING"


        elif change <= -10:

            return "VOLATILITY_COMPRESSING"


        return "STABLE"





    def determine_regime(
        self,
        vix_level,
        volatility_change
    ):
        """
        Final volatility regime.
        """


        if volatility_change == "VOLATILITY_SPIKE":

            return "VOLATILITY_SPIKE"



        if vix_level in [

            "EXTREME",

            "HIGH"

        ]:

            return "HIGH_VOLATILITY"



        if vix_level == "LOW":

            return "LOW_VOLATILITY"



        return "NORMAL_VOLATILITY"





    def analyze_volatility(
        self,
        current_vix,
        previous_vix
    ):
        """
        Main volatility engine.
        """


        vix_level = self.evaluate_vix_level(

            current_vix

        )


        volatility_change = self.detect_volatility_change(

            current_vix,

            previous_vix

        )


        regime = self.determine_regime(

            vix_level,

            volatility_change

        )


        return {


            "engine":

            "L1.2 Volatility Regime Detector v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "current_vix":

            current_vix,


            "vix_level":

            vix_level,


            "volatility_change":

            volatility_change,


            "volatility_regime":

            regime

        }
