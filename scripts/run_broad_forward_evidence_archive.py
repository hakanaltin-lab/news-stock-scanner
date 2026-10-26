import json

from engines.broad_forward_evidence_archive_engine import (
    run_broad_forward_evidence_archive
)


if __name__ == "__main__":
    (
        result,
        daily_file,
        summary_file
    ) = run_broad_forward_evidence_archive()

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

                "universe":
                result.get(
                    "universe"
                ),

                "coverage":
                result.get(
                    "coverage"
                ),

                "daily_file":
                daily_file,

                "summary_file":
                summary_file
            },
            indent=2
        )
    )
