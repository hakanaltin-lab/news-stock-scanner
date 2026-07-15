"""
AURORA AI CIO v3.1

L5 Portfolio Engine

L5.3 Correlation Engine v1.0

Purpose:
Analyze portfolio hidden correlation risk.

Inputs:
- Average Correlation
- Sector Overlap
- Factor Overlap
- Theme Concentration

Output:
Diversification Quality
"""


from datetime import datetime



class CorrelationEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_correlation(
        self,
        average_correlation
    ):


        if average_correlation <= 0.30:

            return 2


        elif average_correlation <= 0.60:

            return 1


        elif average_correlation <= 0.80:

            return -1


        return -2





    def evaluate_sector_overlap(
        self,
        sector_overlap
    ):


        mapping = {


            "LOW":

            2,


            "MEDIUM":

            1,


            "HIGH":

            -2

        }


        return mapping.get(

            sector_overlap,

            0

        )





    def evaluate_factor_overlap(
        self,
        factor_overlap
    ):


        mapping = {


            "LOW":

            2,


            "MEDIUM":

            1,


            "HIGH":

            -2

        }


        return mapping.get(

            factor_overlap,

            0

        )





    def evaluate_theme_concentration(
        self,
        theme_concentration
    ):


        mapping = {


            "LOW":

            2,


            "MEDIUM":

            1,


            "HIGH":

            -2

        }


        return mapping.get(

            theme_concentration,

            0

        )





    def calculate_diversification_score(
        self,
        correlation,
        sector,
        factor,
        theme
    ):


        return (

            correlation

            +

            sector

            +

            factor

            +

            theme

        )





    def classify_diversification(
        self,
        score
    ):


        if score >= 6:

            return "WELL_DIVERSIFIED"



        elif score >= 3:

            return "ACCEPTABLE"



        elif score >= 0:

            return "HIGH_CORRELATION"



        return "HIDDEN_RISK"





    def analyze_portfolio(
        self,
        average_correlation,
        sector_overlap,
        factor_overlap,
        theme_concentration
    ):


        correlation_score = self.evaluate_correlation(

            average_correlation

        )


        sector_score = self.evaluate_sector_overlap(

            sector_overlap

        )


        factor_score = self.evaluate_factor_overlap(

            factor_overlap

        )


        theme_score = self.evaluate_theme_concentration(

            theme_concentration

        )


        total_score = self.calculate_diversification_score(

            correlation_score,

            sector_score,

            factor_score,

            theme_score

        )


        rating = self.classify_diversification(

            total_score

        )


        return {


            "engine":

            "L5.3 Correlation Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "diversification_score":

            total_score,


            "diversification_rating":

            rating,


            "inputs":

            {

                "average_correlation":

                average_correlation,


                "sector_overlap":

                sector_overlap,


                "factor_overlap":

                factor_overlap,


                "theme_concentration":

                theme_concentration

            }

        }
