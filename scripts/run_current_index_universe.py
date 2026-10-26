import json

from engines.current_index_universe_engine import (
    build_current_index_universe,
    write_snapshot
)


if __name__ == "__main__":
    result = build_current_index_universe()

    dated_file, latest_file = write_snapshot(
        result
    )

    print(
        json.dumps(
            {
                "status":
                result.get(
                    "status"
                ),

                "snapshot_date_utc":
                result.get(
                    "snapshot_date_utc"
                ),

                "counts":
                result.get(
                    "counts"
                ),

                "dated_file":
                dated_file,

                "latest_file":
                latest_file
            },
            indent=2
        )
    )
