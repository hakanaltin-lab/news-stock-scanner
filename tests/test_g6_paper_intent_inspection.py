import json
from engines.g6_paper_intent_inspection import intent_fingerprint, inspect_intent

def test_missing_journal_blocks(tmp_path):
    result = inspect_intent("DU_PAPER", {"symbol": "AAPL", "quantity": 1}, tmp_path / "missing.json")
    assert result["status"] == "BLOCKED"
    assert result["broker_submission_allowed"] is False

def test_duplicate_blocks(tmp_path):
    order = {"symbol": "AAPL", "quantity": 1, "side": "BUY"}
    fingerprint = intent_fingerprint("DU_PAPER", order)
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps([{"fingerprint": fingerprint}]))
    result = inspect_intent("DU_PAPER", order, journal)
    assert result["reason"] == "DUPLICATE_INTENT"
    assert result["broker_submission_allowed"] is False

def test_new_intent_never_authorizes_submission(tmp_path):
    journal = tmp_path / "journal.json"
    journal.write_text("[]")
    result = inspect_intent("DU_PAPER", {"symbol": "AAPL", "quantity": 1}, journal)
    assert result["status"] == "INSPECTED_ONLY"
    assert result["broker_submission_allowed"] is False

def test_malformed_journal_blocks(tmp_path):
    journal = tmp_path / "journal.json"
    journal.write_text('{"unexpected": true}')
    assert inspect_intent("DU_PAPER", {"symbol": "AAPL"}, journal)["status"] == "BLOCKED"
