"""
AURORA AI CIO v3.1

L10 AI CIO Committee

L10.2 Bear Case Analyst v1.0

Purpose:
Analyze investment downside risks.

Evaluates:
- Downside Risk
- Competition
- Valuation Risk
- Macro Risk

Output:
Bear Case Score
"""


from datetime import datetime



class BearCaseAnalyst:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_downside(
        self,
        downside
    ):


        mapping = {


            "LOW":

            0,


            "MEDIUM":

            1,


            "HIGH":

            2,


            "EXTREME":

            3

        }


        return mapping.get(

            downside,

            0

        )





    def evaluate_competition(
        self,
        competition
    ):


        mapping = {


            "LOW":

            0,


            "MODERATE":

            1,


            "HIGH":

            2,


            "SEVERE":

            3

        }


        return mapping.get(

            competition,

            0

        )





    def evaluate_valuation(
        self,
        valuation
    ):


        mapping = {


            "ATTRACTIVE":

            0,


            "FAIR":

            1,


            "EXPENSIVE":

            2,


            "EXTREME":

            3

        }


        return mapping.get(

            valuation,

            0

        )





    def evaluate_macro(
        self,
        macro
    ):


        mapping = {


            "FAVORABLE":

            0,


            "NEUTRAL":

            1,


            "NEGATIVE":

            2,


            "CRITICAL":

            3

        }


        return mapping.get(

            macro,

            0

        )





    def calculate_bear_score(
        self,
        downside_score,
        competition_score,
        valuation_score,
        macro_score
    ):


        return (

            downside_score

            +

            competition_score

            +

            valuation_score

            +

            macro_score

        )





    def classify_bear_case(
        self,
        score
    ):


        if score <= 2:

            return "LOW_RISK_DOWNSIDE"



        elif score <= 5:

            return "MODERATE_RISK"



        elif score <= 8:

            return "HIGH_RISK"



        return "THESIS_FAILURE"





    def analyze(
        self,
        symbol,
        downside,
        competition,
        valuation,
        macro
    ):


        downside_score = self.evaluate_downside(

            downside

        )


        competition_score = self.evaluate_competition(

            competition

        )


        valuation_score = self.evaluate_valuation(

            valuation

        )


        macro_score = self.evaluate_macro(

            macro

        )


        bear_score = self.calculate_bear_score(

            downside_score,

            competition_score,

            valuation_score,

            macro_score

        )


        conclusion = self.classify_bear_case(

            bear_score

        )


        return {


            "engine":

            "L10.2 Bear Case Analyst v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "symbol":

            symbol,


            "bear_score":

            bear_score,


            "bear_case":

            conclusion

        }
