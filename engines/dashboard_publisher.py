"""
V7.1.6 CIO Dashboard Publisher

Purpose:
Convert scanner JSON output into
human readable HTML dashboard.

Output:
docs/daily_report.html
"""


import json
import os

from datetime import datetime



INPUT_FILE = "docs/latest.json"

OUTPUT_FILE = "docs/daily_report.html"




def load_report():

    if not os.path.exists(INPUT_FILE):

        return {}


    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)




def generate_html(report):


    portfolio = report.get(
        "portfolio",
        []
    )


    rows = ""


    for stock in portfolio:


        ticker = stock.get(
            "ticker",
            ""
        )


        signal = stock.get(
            "signal",
            ""
        )


        scores = stock.get(
            "scores",
            {}
        )


        alpha = scores.get(
            "alpha_score",
            0
        )


        rows += f"""

        <tr>

        <td>{ticker}</td>

        <td>{signal}</td>

        <td>{alpha}</td>

        </tr>

        """



    html = f"""

<!DOCTYPE html>

<html>

<head>

<title>
AI Trading CIO Dashboard
</title>


<style>

body {{

font-family: Arial;

margin:40px;

background:#f5f5f5;

}}


table {{

width:100%;

border-collapse:collapse;

background:white;

}}


td,th {{

padding:10px;

border:1px solid #ddd;

}}


</style>


</head>


<body>


<h1>
AI Trading CIO Dashboard
</h1>


<p>
Generated:
{datetime.utcnow().isoformat()}
</p>



<h2>
Portfolio Intelligence
</h2>


<table>


<tr>

<th>
Ticker
</th>


<th>
Signal
</th>


<th>
Alpha Score
</th>


</tr>


{rows}


</table>



</body>

</html>


"""


    return html





def publish_dashboard():


    report = load_report()


    html = generate_html(
        report
    )


    os.makedirs(
        "docs",
        exist_ok=True
    )



    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:


        file.write(
            html
        )


    print(
        "CIO Dashboard published"
    )





if __name__ == "__main__":

    publish_dashboard()
