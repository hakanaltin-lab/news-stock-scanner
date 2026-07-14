"""
V10.5 Analyst Consensus Intelligence Engine

Purpose:
Analyze Wall Street analyst sentiment and
convert consensus changes into CIO signals.

Functions:
- Rating analysis
- Price target analysis
- EPS revision analysis
- Consensus scoring
- CIO impact signal
"""


from datetime import datetime



def analyze_rating_action(
    action
):
    """
    Evaluates analyst rating changes
    """


    if action == "UPGRADE":

        return 20


    elif action == "DOWNGRADE":

        return -20


    elif action == "INITIATION":

        return 10


    return 0





def analyze_price_target_change(
    previous_target,
    new_target
):
    """
    Calculates target price revision
    """


    if previous_target == 0:

        return 0



    return round(

        (

            (new_target - previous_target)

            /

            previous_target

        ) * 100,

        2

    )





def analyze_eps_revision(
    previous_eps,
    new_eps
):
    """
    Calculates EPS estimate revision
    """


    if previous_eps == 0:

        return 0



    return round(

        (

            (new_eps - previous_eps)

            /

            previous_eps

        ) * 100,

        2

    )





def calculate_consensus_score(
    rating_score,
    target_change,
    eps_revision
):
    """
    Creates analyst consensus score
    """


    score = 50



    score += rating_score



    if target_change >= 10:

        score += 15


    elif target_change <= -10:

        score -= 15



    if eps_revision >= 10:

        score += 15


    elif eps_revision <= -10:

        score -= 15



    return max(

        0,

        min(

            100,

            score

        )

    )





def determine_consensus_signal(
    score
):
    """
    Converts score into signal
    """


    if score >= 80:

        return "STRONG_POSITIVE"


    elif score >= 60:

        return "POSITIVE"


    elif score >= 40:

        return "NEUTRAL"


    return "NEGATIVE"





def analyze_analyst_consensus(
    ticker,
    rating_action,
    previous_target,
    new_target,
    previous_eps,
    new_eps
):
    """
    Main analyst consensus engine
    """


    rating_score = analyze_rating_action(

        rating_action

    )


    target_change = analyze_price_target_change(

        previous_target,

        new_target

    )


    eps_revision = analyze_eps_revision(

        previous_eps,

        new_eps

    )


    consensus_score = calculate_consensus_score(

        rating_score,

        target_change,

        eps_revision

    )



    return {


        "engine":

        "V10.5 Analyst Consensus Intelligence Engine",


        "timestamp":

        datetime.utcnow().isoformat(),


        "ticker":

        ticker,


        "rating_action":

        rating_action,


        "price_target_change_percent":

        target_change,


        "eps_revision_percent":

        eps_revision,


        "consensus_score":

        consensus_score,


        "consensus_signal":

        determine_consensus_signal(

            consensus_score

        )

    }
