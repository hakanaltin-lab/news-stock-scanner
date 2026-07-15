"""
AURORA AI CIO v3.1

L3 Alpha Generation Engine

L3.1 Opportunity Scanner v1.0

Purpose:
Scan investment universe and identify opportunities.

Inputs:
- Liquidity
- Market Cap
- Growth
- Momentum
- Volatility

Output:
Opportunity Priority
"""


from datetime import datetime



class OpportunityScanner:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_liquidity(
        self,
        liquidity
    ):

        mapping = {


            "HIGH":

            2,


            "MEDIUM":

            1,


            "LOW":

            -1

        }


        return mapping.get(

            liquidity,

            0

        )





    def evaluate_market_cap(
        self,
        market_cap
    ):

        mapping = {


            "LARGE_CAP":

            2,


            "MID_CAP":

            1,


            "SMALL_CAP":

            0,


            "MICRO_CAP":

            -1

        }


        return mapping.get(

            market_cap,

            0

        )





    def evaluate_growth(
        self,
        growth
    ):

        mapping = {


            "HIGH":

            2,


            "MODERATE":

            1,


            "LOW":

            0,


            "NEGATIVE":

            -1

        }


        return mapping.get(

            growth,

            0

        )





    def evaluate_momentum(
        self,
        momentum
    ):

        mapping = {


            "STRONG":

            2,


            "POSITIVE":

            1,


            "NEUTRAL":

            0,


            "WEAK":

            -1

        }


        return mapping.get(

            momentum,

            0

        )





    def evaluate_volatility(
        self,
        volatility
    ):

        mapping = {


            "CONTROLLED":

            1,


            "NORMAL":

            0,


            "EXTREME":

            -1

        }


        return mapping.get(

            volatility,

            0

        )





    def calculate_opportunity_score(
        self,
        liquidity,
        market_cap,
        growth,
        momentum,
        volatility
    ):

        return (

            liquidity

            +

            market_cap

            +

            growth

            +

            momentum

            +

            volatility

        )





    def classify_opportunity(
        self,
        score
    ):


        if score >= 7:

            return "HIGH_PRIORITY"



        elif score >= 4:

            return "MEDIUM_PRIORITY"



        elif score >= 1:

            return "LOW_PRIORITY"



        return "IGNORE"





    def scan_opportunity(
        self,
        liquidity,
        market_cap,
        growth,
        momentum,
        volatility
    ):


        liquidity_score = self.evaluate_liquidity(

            liquidity

        )


        cap_score = self.evaluate_market_cap(

            market_cap

        )


        growth_score = self.evaluate_growth(

            growth

        )


        momentum_score = self.evaluate_momentum(

            momentum

        )


        volatility_score = self.evaluate_volatility(

            volatility

        )


        total_score = self.calculate_opportunity_score(

            liquidity_score,

            cap_score,

            growth_score,

            momentum_score,

            volatility_score

        )


        priority = self.classify_opportunity(

            total_score

        )


        return {


            "engine":

            "L3.1 Opportunity Scanner v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "opportunity_score":

            total_score,


            "priority":

            priority,


            "inputs":

            {

                "liquidity":

                liquidity,


                "market_cap":

                market_cap,


                "growth":

                growth,


                "momentum":

                momentum,


                "volatility":

                volatility

            }

        }
