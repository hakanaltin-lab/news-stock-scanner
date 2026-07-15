"""
AURORA AI CIO v3.1

L2 Research Pods

L2.3 Macro AI v1.0

Purpose:
Analyze macroeconomic environment impact.

Inputs:
- Fed Policy
- Interest Rates
- Inflation
- GDP Growth
- Economic Cycle
- Sector Rotation

Output:
Macro Environment Rating
"""


from datetime import datetime



class MacroAI:


    def __init__(self):

        self.status = "ACTIVE"



    def evaluate_fed_policy(
        self,
        fed_policy
    ):

        if fed_policy == "EASING":

            return 2


        elif fed_policy == "NEUTRAL":

            return 0


        elif fed_policy == "TIGHTENING":

            return -2


        return 0





    def evaluate_rates(
        self,
        rate_environment
    ):

        if rate_environment == "LOW":

            return 2


        elif rate_environment == "STABLE":

            return 1


        elif rate_environment == "HIGH":

            return -1


        return 0





    def evaluate_inflation(
        self,
        inflation_environment
    ):

        if inflation_environment == "CONTROLLED":

            return 1


        elif inflation_environment == "RISING":

            return -1


        elif inflation_environment == "HIGH":

            return -2


        return 0





    def evaluate_growth(
        self,
        gdp_growth
    ):

        if gdp_growth == "STRONG":

            return 2


        elif gdp_growth == "STABLE":

            return 1


        elif gdp_growth == "WEAK":

            return -1


        elif gdp_growth == "RECESSION":

            return -2


        return 0





    def evaluate_cycle(
        self,
        economic_cycle
    ):

        mapping = {


            "EXPANSION":

            2,


            "MID_CYCLE":

            1,


            "SLOWDOWN":

            -1,


            "RECESSION":

            -2

        }


        return mapping.get(

            economic_cycle,

            0

        )





    def evaluate_sector_rotation(
        self,
        sector_position
    ):

        if sector_position == "FAVORABLE":

            return 1


        elif sector_position == "UNFAVORABLE":

            return -1


        return 0





    def calculate_macro_score(
        self,
        fed,
        rates,
        inflation,
        growth,
        cycle,
        sector
    ):

        return (

            fed

            +

            rates

            +

            inflation

            +

            growth

            +

            cycle

            +

            sector

        )





    def classify_macro(
        self,
        score
    ):

        if score >= 7:

            return "STRONG_TAILWIND"


        elif score >= 3:

            return "TAILWIND"


        elif score <= -7:

            return "STRONG_HEADWIND"


        elif score <= -3:

            return "HEADWIND"


        return "NEUTRAL"





    def analyze_macro(
        self,
        fed_policy,
        rate_environment,
        inflation_environment,
        gdp_growth,
        economic_cycle,
        sector_position
    ):


        fed_score = self.evaluate_fed_policy(

            fed_policy

        )


        rate_score = self.evaluate_rates(

            rate_environment

        )


        inflation_score = self.evaluate_inflation(

            inflation_environment

        )


        growth_score = self.evaluate_growth(

            gdp_growth

        )


        cycle_score = self.evaluate_cycle(

            economic_cycle

        )


        sector_score = self.evaluate_sector_rotation(

            sector_position

        )


        total_score = self.calculate_macro_score(

            fed_score,

            rate_score,

            inflation_score,

            growth_score,

            cycle_score,

            sector_score

        )


        rating = self.classify_macro(

            total_score

        )


        return {


            "engine":

            "L2.3 Macro AI v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "macro_score":

            total_score,


            "macro_rating":

            rating,


            "inputs":

            {

                "fed_policy":

                fed_policy,


                "rates":

                rate_environment,


                "inflation":

                inflation_environment,


                "growth":

                gdp_growth,


                "cycle":

                economic_cycle,


                "sector_rotation":

                sector_position

            }

        }
