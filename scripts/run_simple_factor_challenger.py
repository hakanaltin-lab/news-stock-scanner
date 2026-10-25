import json

from engines.simple_factor_challenger_engine import (
    run_simple_factor_challenger
)


if __name__ == "__main__":
    result = run_simple_factor_challenger()

    print(
        json.dumps(
            {
                "status":
                result.get(
                    "status"
                ),

                "overall_verdict":
                result.get(
                    "overall_verdict"
                ),

                "sp500_verdict":
                (
                    result.get(
                        "sp500",
                        {}
                    )
                    or
                    {}
                ).get(
                    "verdict"
                ),

                "nasdaq100_verdict":
                (
                    result.get(
                        "nasdaq100",
                        {}
                    )
                    or
                    {}
                ).get(
                    "verdict"
                )
            },
            indent=2
        )
    )
