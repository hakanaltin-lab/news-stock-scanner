"""
AURORA AI CIO v3.1

L5 Portfolio Engine

L5.4 Exposure Controller v1.0

Purpose:
Control portfolio exposure risk.

Controls:
- Sector Exposure
- Factor Exposure
- Theme Exposure
- Cash Level
- Concentration Risk

Output:
Exposure Quality Rating
"""


from datetime import datetime



class ExposureController:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_sector_exposure(
        self,
        sector_exposure
    ):


        if sector_exposure <= 25:

            return 2


        elif sector_exposure <= 40:

            return 1


        elif sector_exposure <= 60:

            return -1


        return -2





    def evaluate_factor_exposure(
        self,
        factor_exposure
    ):


        mapping = {


            "BALANCED":

            2,


            "MODERATE":

            1,


            "CONCENTRATED":

            -1,


            "EXTREME":

            -2

        }


        return mapping.get(

            factor_exposure,

            0

        )





    def evaluate_theme_exposure(
        self,
        theme_exposure
    ):


        mapping = {


            "DIVERSIFIED":

            2,


            "CONTROLLED":

            1,


            "CONCENTRATED":

            -1,


            "OVEREXPOSED":

            -2

        }


        return mapping.get(

            theme_exposure,

            0

        )





    def evaluate_cash_level(
        self,
        cash_percentage
    ):


        if cash_percentage >= 10:

            return 2


        elif cash_percentage >= 5:

            return 1


        elif cash_percentage < 2:

            return -1


        return 0





    def calculate_exposure_score(
        self,
        sector,
        factor,
        theme,
        cash
    ):


        return (

            sector

            +

            factor

            +

            theme

            +

            cash

        )





    def classify_exposure(
        self,
        score
    ):


        if score >= 6:

            return "OPTIMAL_EXPOSURE"



        elif score >= 3:

            return "BALANCED_EXPOSURE"



        elif score >= 0:

            return "OVEREXPOSED"



        return "CRITICAL_EXPOSURE"





    def analyze_exposure(
        self,
        sector_exposure,
        factor_exposure,
        theme_exposure,
        cash_percentage
    ):


        sector_score = self.evaluate_sector_exposure(

            sector_exposure

        )


        factor_score = self.evaluate_factor_exposure(

            factor_exposure

        )


        theme_score = self.evaluate_theme_exposure(

            theme_exposure

        )


        cash_score = self.evaluate_cash_level(

            cash_percentage

        )


        total_score = self.calculate_exposure_score(

            sector_score,

            factor_score,

            theme_score,

            cash_score

        )


        rating = self.classify_exposure(

            total_score

        )


        return {


            "engine":

            "L5.4 Exposure Controller v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "exposure_score":

            total_score,


            "exposure_rating":

            rating,


            "inputs":

            {

                "sector_exposure":

                sector_exposure,


                "factor_exposure":

                factor_exposure,


                "theme_exposure":

                theme_exposure,


                "cash_percentage":

                cash_percentage

            }

        }
