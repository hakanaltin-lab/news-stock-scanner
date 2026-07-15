"""
AURORA AI CIO v3.1

L2 Research Pods

L2.1 Fundamental AI v1.0

Purpose:
Analyze company fundamental quality.

Inputs:
- Revenue Growth
- Margin Quality
- Free Cash Flow
- Balance Sheet
- ROIC
- Valuation

Output:
Fundamental Quality Rating
"""


from datetime import datetime



class FundamentalAI:


    def __init__(self):

        self.status = "ACTIVE"



    def evaluate_growth(
        self,
        revenue_growth
    ):

        if revenue_growth >= 20:

            return 2


        elif revenue_growth >= 10:

            return 1


        elif revenue_growth < 0:

            return -1


        return 0





    def evaluate_margin(
        self,
        operating_margin
    ):

        if operating_margin >= 25:

            return 2


        elif operating_margin >= 10:

            return 1


        elif operating_margin < 0:

            return -1


        return 0





    def evaluate_cash_flow(
        self,
        free_cash_flow
    ):

        if free_cash_flow == "STRONG":

            return 2


        elif free_cash_flow == "POSITIVE":

            return 1


        elif free_cash_flow == "NEGATIVE":

            return -1


        return 0





    def evaluate_balance_sheet(
        self,
        debt_level
    ):

        if debt_level == "LOW":

            return 2


        elif debt_level == "NORMAL":

            return 1


        elif debt_level == "HIGH":

            return -1


        return 0





    def evaluate_roic(
        self,
        roic
    ):

        if roic >= 20:

            return 2


        elif roic >= 10:

            return 1


        elif roic < 0:

            return -1


        return 0





    def evaluate_valuation(
        self,
        valuation
    ):

        if valuation == "ATTRACTIVE":

            return 1


        elif valuation == "EXPENSIVE":

            return -1


        return 0





    def calculate_quality_score(
        self,
        growth,
        margin,
        cashflow,
        balance,
        roic,
        valuation
    ):

        return (

            growth

            +

            margin

            +

            cashflow

            +

            balance

            +

            roic

            +

            valuation

        )





    def classify_quality(
        self,
        score
    ):

        if score >= 8:

            return "EXCELLENT"


        elif score >= 5:

            return "STRONG"


        elif score >= 2:

            return "AVERAGE"


        elif score < 0:

            return "RISKY"


        return "WEAK"





    def analyze_company(
        self,
        revenue_growth,
        operating_margin,
        free_cash_flow,
        debt_level,
        roic,
        valuation
    ):

        growth_score = self.evaluate_growth(
            revenue_growth
        )


        margin_score = self.evaluate_margin(
            operating_margin
        )


        cashflow_score = self.evaluate_cash_flow(
            free_cash_flow
        )


        balance_score = self.evaluate_balance_sheet(
            debt_level
        )


        roic_score = self.evaluate_roic(
            roic
        )


        valuation_score = self.evaluate_valuation(
            valuation
        )


        total_score = self.calculate_quality_score(
            growth_score,
            margin_score,
            cashflow_score,
            balance_score,
            roic_score,
            valuation_score
        )


        rating = self.classify_quality(
            total_score
        )


        return {


            "engine":

            "L2.1 Fundamental AI v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "fundamental_score":

            total_score,


            "quality_rating":

            rating,


            "inputs":

            {

                "revenue_growth":

                revenue_growth,


                "operating_margin":

                operating_margin,


                "free_cash_flow":

                free_cash_flow,


                "debt_level":

                debt_level,


                "roic":

                roic,


                "valuation":

                valuation

            }

        }
