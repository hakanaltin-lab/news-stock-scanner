"""
AURORA AI CIO v3.1

L10 AI CIO Committee

L10.5 CIO Decision Engine v1.0

Purpose:
Combine committee opinions
and produce final CIO decision.

Inputs:
- Bull Case Score
- Bear Case Score
- Risk Decision
- Portfolio Decision

Output:
Final Investment Decision
"""


from datetime import datetime



class CIODecisionEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_risk_decision(
        self,
        risk_decision
    ):


        mapping = {


            "APPROVE":

            2,


            "APPROVE_WITH_LIMITS":

            1,


            "WATCH":

            0,


            "BLOCK":

            -3

        }


        return mapping.get(

            risk_decision,

            0

        )





    def evaluate_portfolio_fit(
        self,
        portfolio_decision
    ):


        mapping = {


            "PERFECT_FIT":

            2,


            "GOOD_FIT":

            1,


            "LIMITED_FIT":

            0,


            "NOT_SUITABLE":

            -2

        }


        return mapping.get(

            portfolio_decision,

            0

        )





    def calculate_cio_score(
        self,
        bull_score,
        bear_score,
        risk_score,
        portfolio_score
    ):


        return (

            bull_score

            -

            bear_score

            +

            risk_score

            +

            portfolio_score

        )





    def classify_decision(
        self,
        score
    ):


        if score >= 12:

            return "STRONG_BUY"



        elif score >= 7:

            return "BUY"



        elif score >= 3:

            return "HOLD"



        elif score >= 0:

            return "REDUCE"



        return "REJECT"





    def make_decision(
        self,
        symbol,
        bull_score,
        bear_score,
        risk_decision,
        portfolio_decision
    ):


        risk_score = self.evaluate_risk_decision(

            risk_decision

        )


        portfolio_score = self.evaluate_portfolio_fit(

            portfolio_decision

        )


        cio_score = self.calculate_cio_score(

            bull_score,

            bear_score,

            risk_score,

            portfolio_score

        )


        final_decision = self.classify_decision(

            cio_score

        )


        return {


            "engine":

            "L10.5 CIO Decision Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "symbol":

            symbol,


            "cio_score":

            cio_score,


            "final_decision":

            final_decision

        }
