"""
AURORA AI CIO v3.1

L1 Market Regime Engine

Risk Appetite Engine v1.0

Purpose:
Measure investor willingness
to take market risk.

Outputs:
- RISK_SEEKING
- NEUTRAL
- RISK_AVERSION
- PANIC
"""


from datetime import datetime



class RiskAppetiteEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_vix_sentiment(
        self,
        vix_level
    ):
        """
        Evaluates fear level.
        """


        if vix_level <= 15:

            return 2


        elif vix_level <= 25:

            return 0


        elif vix_level <= 35:

            return -1


        return -2





    def evaluate_equity_flow(
        self,
        equity_flow
    ):
        """
        Evaluates equity money flow.
        """


        if equity_flow == "INFLOW":

            return 1


        elif equity_flow == "OUTFLOW":

            return -1


        return 0





    def evaluate_safe_haven_demand(
        self,
        safe_haven_demand
    ):
        """
        Evaluates defensive behavior.
        """


        if safe_haven_demand == "LOW":

            return 1


        elif safe_haven_demand == "HIGH":

            return -1


        return 0





    def evaluate_credit_appetite(
        self,
        credit_condition
    ):
        """
        Evaluates credit risk appetite.
        """


        if credit_condition == "HEALTHY":

            return 1


        elif credit_condition == "STRESSED":

            return -1


        return 0





    def calculate_score(
        self,
        vix_score,
        flow_score,
        safe_haven_score,
        credit_score
    ):

        return (

            vix_score

            +

            flow_score

            +

            safe_haven_score

            +

            credit_score

        )





    def classify_risk_appetite(
        self,
        score
    ):
        """
        Final risk appetite classification.
        """


        if score >= 3:

            return "RISK_SEEKING"



        elif score <= -3:

            return "PANIC"



        elif score < 0:

            return "RISK_AVERSION"



        return "NEUTRAL"





    def analyze_risk_appetite(
        self,
        vix_level,
        equity_flow,
        safe_haven_demand,
        credit_condition
    ):
        """
        Main risk appetite engine.
        """


        vix_score = self.evaluate_vix_sentiment(

            vix_level

        )


        flow_score = self.evaluate_equity_flow(

            equity_flow

        )


        safe_haven_score = self.evaluate_safe_haven_demand(

            safe_haven_demand

        )


        credit_score = self.evaluate_credit_appetite(

            credit_condition

        )


        total_score = self.calculate_score(

            vix_score,

            flow_score,

            safe_haven_score,

            credit_score

        )


        appetite = self.classify_risk_appetite(

            total_score

        )


        return {


            "engine":

            "L1.5 Risk Appetite Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "risk_appetite_score":

            total_score,


            "risk_appetite":

            appetite,


            "inputs":

            {

                "vix":

                vix_level,


                "equity_flow":

                equity_flow,


                "safe_haven":

                safe_haven_demand,


                "credit":

                credit_condition

            }

        }
