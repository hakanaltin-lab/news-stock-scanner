"""
AURORA AI CIO v3.1

L8 Monitoring Engine

L8.2 Risk Monitor v1.0

Purpose:
Monitor portfolio risk conditions.

Tracks:
- Exposure
- Concentration
- Volatility
- Drawdown

Output:
Risk Status
"""


from datetime import datetime



class RiskMonitor:


    def __init__(self):

        self.status = "ACTIVE"





    def evaluate_exposure(
        self,
        exposure_percentage
    ):


        if exposure_percentage <= 50:

            return 2


        elif exposure_percentage <= 75:

            return 1


        elif exposure_percentage <= 90:

            return -1


        return -2





    def evaluate_volatility(
        self,
        volatility
    ):


        mapping = {


            "LOW":

            2,


            "NORMAL":

            1,


            "HIGH":

            -1,


            "EXTREME":

            -2

        }


        return mapping.get(

            volatility,

            0

        )





    def evaluate_drawdown(
        self,
        drawdown
    ):


        if drawdown <= 5:

            return 2


        elif drawdown <= 15:

            return 1


        elif drawdown <= 25:

            return -1


        return -2





    def calculate_risk_score(
        self,
        exposure_score,
        volatility_score,
        drawdown_score
    ):


        return (

            exposure_score

            +

            volatility_score

            +

            drawdown_score

        )





    def classify_risk(
        self,
        score
    ):


        if score >= 4:

            return "SAFE"



        elif score >= 1:

            return "WATCH"



        elif score >= -2:

            return "WARNING"



        return "CRITICAL"





    def analyze_risk(
        self,
        exposure_percentage,
        volatility,
        drawdown
    ):


        exposure_score = self.evaluate_exposure(

            exposure_percentage

        )


        volatility_score = self.evaluate_volatility(

            volatility

        )


        drawdown_score = self.evaluate_drawdown(

            drawdown

        )


        risk_score = self.calculate_risk_score(

            exposure_score,

            volatility_score,

            drawdown_score

        )


        risk_status = self.classify_risk(

            risk_score

        )


        return {


            "engine":

            "L8.2 Risk Monitor v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "risk_score":

            risk_score,


            "risk_status":

            risk_status,


            "inputs":

            {

                "exposure_percentage":

                exposure_percentage,


                "volatility":

                volatility,


                "drawdown":

                drawdown

            }

        }
