from concurrent.futures import ThreadPoolExecutor
from engines.g6_paper_intent_reservation import (
    initialize_paper_intent_database, reserve_paper_intent
)

def test_atomic_duplicate_reservation(tmp_path):
    database = tmp_path / "paper.sqlite"
    initialize_paper_intent_database(database)
    order = {"symbol": "AAPL", "side": "BUY", "quantity": 1}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            lambda _: reserve_paper_intent("DU_PAPER", order, database),
            range(8),
        ))
    assert sum(r["status"] == "RESERVED_OFFLINE" for r in results) == 1
    assert all(r["broker_submission_allowed"] is False for r in results)

def test_uninitialized_database_fails_closed(tmp_path):
    result = reserve_paper_intent("DU_PAPER", {"symbol": "AAPL"}, tmp_path / "absent.db")
    assert result["status"] == "BLOCKED"
    assert result["broker_submission_allowed"] is False

def test_distinct_accounts_have_distinct_reservations(tmp_path):
    database = tmp_path / "paper.sqlite"
    initialize_paper_intent_database(database)
    order = {"symbol": "AAPL", "side": "BUY", "quantity": 1}
    first = reserve_paper_intent("DU_PAPER_1", order, database)
    second = reserve_paper_intent("DU_PAPER_2", order, database)
    assert first["status"] == second["status"] == "RESERVED_OFFLINE"
    assert first["fingerprint"] != second["fingerprint"]
