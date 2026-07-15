"""
AURORA AI CIO v3.1

L2 Research Pods

L2.4 Sentiment AI v1.0

Purpose:
Analyze market sentiment.

Inputs:
- News sentiment
- Analyst revisions
- Social sentiment
- Investor psychology

Output:
Sentiment Rating
"""


from datetime import datetime



class SentimentAI:


    def __init__(self):

        self.status = "ACTIVE"



    def evaluate_news_sentiment(
        self,
        news_sentiment
    ):

        mapping = {


            "VERY_POSITIVE":

            2,


            "POSITIVE":

            1,


            "NEUTRAL":

            0,


            "NEGATIVE":

            -1,


            "VERY_NEGATIVE":

            -2

        }


        return mapping.get(

            news_sentiment,

            0

        )





    def evaluate_analyst_activity(
        self,
        analyst_action
    ):

        mapping = {


            "UPGRADES":

            1,


            "STABLE":

            0,


            "DOWNGRADES":

            -1

        }


        return mapping.get(

            analyst_action,

            0

        )





    def evaluate_social_sentiment(
        self,
        social_sentiment
    ):

        mapping = {


            "BULLISH":

            1,


            "NEUTRAL":

            0,


            "BEARISH":

            -1

        }


        return mapping.get(

            social_sentiment,

            0

        )





    def evaluate_investor_psychology(
        self,
        psychology
    ):

        mapping = {


            "OPTIMISTIC":

            1,


            "BALANCED":

            0,


            "FEARFUL":

            -1,


            "PANIC":

            -2

        }


        return mapping.get(

            psychology,

            0

        )





    def calculate_sentiment_score(
        self,
        news,
        analyst,
        social,
        psychology
    ):

        return (

            news

            +

            analyst

            +

            social

            +

            psychology

        )





    def classify_sentiment(
        self,
        score
    ):

        if score >= 4:

            return "STRONG_POSITIVE"



        elif score >= 2:

            return "POSITIVE"



        elif score <= -4:

            return "STRONG_NEGATIVE"



        elif score <= -2:

            return "NEGATIVE"



        return "NEUTRAL"





    def analyze_sentiment(
        self,
        news_sentiment,
        analyst_action,
        social_sentiment,
        investor_psychology
    ):

        news_score = self.evaluate_news_sentiment(

            news_sentiment

        )


        analyst_score = self.evaluate_analyst_activity(

            analyst_action

        )


        social_score = self.evaluate_social_sentiment(

            social_sentiment

        )


        psychology_score = self.evaluate_investor_psychology(

            investor_psychology

        )


        total_score = self.calculate_sentiment_score(

            news_score,

            analyst_score,

            social_score,

            psychology_score

        )


        rating = self.classify_sentiment(

            total_score

        )


        return {


            "engine":

            "L2.4 Sentiment AI v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "sentiment_score":

            total_score,


            "sentiment_rating":

            rating,


            "inputs":

            {

                "news":

                news_sentiment,


                "analyst":

                analyst_action,


                "social":

                social_sentiment,


                "psychology":

                investor_psychology

            }

        }
