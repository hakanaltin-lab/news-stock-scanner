import json

from engines.evidence_archive_engine import (
    run_daily_evidence_archive
)


if __name__ == "__main__":
    result, output_file, latest_file = (
        run_daily_evidence_archive()
    )

    print(
        json.dumps(
            {
                "status":
                result.get(
                    "status"
                ),

                "archive_date":
                result.get(
                    "archive_date"
                ),

                "ticker_count":
                (
                    result.get(
                        "universe",
                        {}
                    )
                    or
                    {}
                ).get(
                    "ticker_count"
                ),

                "coverage":
                result.get(
                    "coverage"
                ),

                "output_file":
                output_file,

                "latest_file":
                latest_file
            },
            indent=2
        )
    )
