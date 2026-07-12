"""
V8.9 Alpha Ranking & Opportunity Prioritization Engine

Purpose:
Rank investment opportunities using
multi-factor alpha analysis.

Functions:
- Fundamental scoring
- Earnings momentum scoring
- Catalyst scoring
- Technical scoring
- Risk reward scoring
- Opportunity ranking
"""


from datetime import datetime



def calculate_alpha_score(
    fundamental_score,
    earnings_score,
    catalyst_score,
    technical_score,
    risk_reward_score
):
    """
    Multi factor alpha calculation
    """


    score = (

        fundamental_score * 0.35

        +

        earnings_score * 0.25

        +

        catalyst_score * 0.20

        +

        technical_score * 0.10

        +

        risk_reward_score * 0.10

    )


    return round(score)





def classify_opportunity(
    alpha_score
):
    """
    Converts score into CIO action
    """


    if alpha_score >= 90:

        return "ACCUMULATE"



    elif alpha_score >= 80:

        return "BUY_DIP"



    elif alpha_score >= 70:

        return "WATCH"



    else:

        return "AVOID"





def rank_opportunities(
    opportunities
):
    """
    Rank investment candidates
    """


    ranked = []



    for opportunity in opportunities:


        score = calculate_alpha_score(

            opportunity.get(
                "fundamental_score",
                0
            ),

            opportunity.get(
                "earnings_score",
                0
            ),

            opportunity.get(
                "catalyst_score",
                0
            ),

            opportunity.get(
                "technical_score",
                0
            ),

            opportunity.get(
                "risk_reward_score",
                0
            )

        )



        ranked.append(

            {

            "ticker":

            opportunity.get(
                "ticker"
            ),


            "alpha_score":

            score,


            "recommendation":

            classify_opportunity(
                score
            )

            }

        )



    ranked.sort(

        key=lambda x:

        x["alpha_score"],

        reverse=True

    )


    return ranked





def generate_alpha_report(
    ranked_opportunities
):
    """
    Creates CIO alpha report
    """


    return {


        "engine":

        "V8.9 Alpha Ranking Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "top_opportunities":

        ranked_opportunities,


        "status":

        "READY"

    }
