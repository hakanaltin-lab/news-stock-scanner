"""
AURORA AI CIO v3.1

L9 Learning Engine

L9.2 Signal Learning Engine v1.0

Purpose:
Learn which investment signals
generate successful outcomes.

Tracks:
- Signal Performance
- Success Rate
- Signal Quality

Output:
Signal Intelligence Score
"""


from datetime import datetime



class SignalLearningEngine:


    def __init__(self):

        self.status = "ACTIVE"

        self.signal_memory = {}





    def record_signal(
        self,
        signal_name,
        signal_type,
        outcome
    ):


        if signal_name not in self.signal_memory:


            self.signal_memory[signal_name] = {


                "type":

                signal_type,


                "wins":

                0,


                "losses":

                0,


                "total":

                0

            }



        self.signal_memory[signal_name]["total"] += 1



        if outcome == "WIN":

            self.signal_memory[signal_name]["wins"] += 1


        elif outcome == "LOSS":

            self.signal_memory[signal_name]["losses"] += 1



        return self.signal_memory[signal_name]





    def calculate_signal_success(
        self,
        signal_name
    ):


        if signal_name not in self.signal_memory:

            return 0


        data = self.signal_memory[signal_name]


        if data["total"] == 0:

            return 0


        return (

            data["wins"]

            /

            data["total"]

        ) * 100





    def classify_signal(
        self,
        success_rate
    ):


        if success_rate >= 70:

            return "HIGH_VALUE_SIGNAL"



        elif success_rate >= 50:

            return "USEFUL_SIGNAL"



        elif success_rate >= 30:

            return "WEAK_SIGNAL"



        return "NEGATIVE_SIGNAL"





    def analyze_signal(
        self,
        signal_name
    ):


        success_rate = self.calculate_signal_success(

            signal_name

        )


        classification = self.classify_signal(

            success_rate

        )


        return {


            "engine":

            "L9.2 Signal Learning Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "signal":

            signal_name,


            "success_rate":

            success_rate,


            "classification":

            classification

        }
