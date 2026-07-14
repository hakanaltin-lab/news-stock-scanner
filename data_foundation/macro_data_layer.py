"""
AURORA AI CIO v3.1

L0 Data Foundation

Macro Data Layer v1.0

Purpose:
Standardize macroeconomic data.

Controls:
- Interest rates
- Inflation
- GDP
- Employment
- Central bank policy
- Liquidity environment
"""


from datetime import datetime



class MacroDataLayer:


    def __init__(
        self,
        source="MACRO_DATA_PROVIDER"
    ):

        self.source = source

        self.status = "INITIALIZED"





    def create_macro_snapshot(
        self,
        interest_rate,
        inflation_rate,
        gdp_growth,
        unemployment_rate,
        fed_policy,
        liquidity_condition
    ):
        """
        Creates standardized macro snapshot.
        """


        snapshot = {


            "timestamp":

            datetime.utcnow().isoformat(),


            "source":

            self.source,


            "interest_rate":

            interest_rate,


            "inflation_rate":

            inflation_rate,


            "gdp_growth":

            gdp_growth,


            "unemployment_rate":

            unemployment_rate,


            "fed_policy":

            fed_policy,


            "liquidity_condition":

            liquidity_condition

        }


        return snapshot





    def evaluate_macro_environment(
        self,
        snapshot
    ):
        """
        Classifies macro environment.
        """


        score = 0



        # Inflation impact

        if snapshot["inflation_rate"] < 3:

            score += 1


        else:

            score -= 1



        # Interest rate impact

        if snapshot["interest_rate"] < 4:

            score += 1


        else:

            score -= 1



        # Growth impact

        if snapshot["gdp_growth"] > 2:

            score += 1


        else:

            score -= 1



        # Liquidity

        if snapshot["liquidity_condition"] == "EASY":

            score += 1


        else:

            score -= 1




        if score >= 3:

            return "RISK_ON"



        elif score <= -2:

            return "RISK_OFF"



        return "NEUTRAL"





    def get_macro_status(self):

        return {


            "engine":

            "L0.7 Macro Data Layer v1.0",


            "source":

            self.source,


            "status":

            self.status,


            "timestamp":

            datetime.utcnow().isoformat()

        }
