"""
AURORA AI CIO v3.1

L4 Simulation Twin

L4.1 Backtest Engine v1.0

Purpose:
Simulate historical strategy performance.

Metrics:
- Total Return
- Sharpe Ratio
- Maximum Drawdown
- Win Rate
- Profit Factor
- Trade Count
"""


from datetime import datetime



class BacktestEngine:


    def __init__(self):

        self.status = "ACTIVE"





    def calculate_total_return(
        self,
        initial_capital,
        final_capital
    ):

        if initial_capital == 0:

            return 0


        return (

            (

                final_capital

                -

                initial_capital

            )

            /

            initial_capital

        ) * 100





    def calculate_win_rate(
        self,
        winning_trades,
        total_trades
    ):

        if total_trades == 0:

            return 0


        return (

            winning_trades

            /

            total_trades

        ) * 100





    def calculate_profit_factor(
        self,
        gross_profit,
        gross_loss
    ):

        if gross_loss == 0:

            return 0


        return (

            gross_profit

            /

            gross_loss

        )





    def calculate_max_drawdown(
        self,
        peak_value,
        lowest_value
    ):

        if peak_value == 0:

            return 0


        return (

            (

                peak_value

                -

                lowest_value

            )

            /

            peak_value

        ) * 100





    def evaluate_sharpe(
        self,
        sharpe_ratio
    ):


        if sharpe_ratio >= 2:

            return "EXCELLENT"


        elif sharpe_ratio >= 1:

            return "ACCEPTABLE"


        return "WEAK"





    def classify_strategy(
        self,
        total_return,
        sharpe_ratio,
        max_drawdown
    ):


        if (

            total_return >= 20

            and

            sharpe_ratio >= 1.5

            and

            max_drawdown <= 15

        ):

            return "APPROVED"



        elif (

            total_return > 0

            and

            sharpe_ratio >= 1

        ):

            return "REVIEW"



        return "REJECT"





    def run_backtest(
        self,
        initial_capital,
        final_capital,
        winning_trades,
        total_trades,
        gross_profit,
        gross_loss,
        peak_value,
        lowest_value,
        sharpe_ratio
    ):


        total_return = self.calculate_total_return(

            initial_capital,

            final_capital

        )


        win_rate = self.calculate_win_rate(

            winning_trades,

            total_trades

        )


        profit_factor = self.calculate_profit_factor(

            gross_profit,

            gross_loss

        )


        max_drawdown = self.calculate_max_drawdown(

            peak_value,

            lowest_value

        )


        sharpe_quality = self.evaluate_sharpe(

            sharpe_ratio

        )


        strategy_status = self.classify_strategy(

            total_return,

            sharpe_ratio,

            max_drawdown

        )


        return {


            "engine":

            "L4.1 Backtest Engine v1.0",


            "timestamp":

            datetime.utcnow().isoformat(),


            "performance":

            {

                "total_return_percent":

                total_return,


                "win_rate_percent":

                win_rate,


                "profit_factor":

                profit_factor,


                "max_drawdown_percent":

                max_drawdown,


                "sharpe_ratio":

                sharpe_ratio

            },


            "sharpe_quality":

            sharpe_quality,


            "strategy_status":

            strategy_status

        }
