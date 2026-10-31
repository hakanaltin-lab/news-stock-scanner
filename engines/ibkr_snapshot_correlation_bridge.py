"""Read-only diagnostic bridge from IBKR snapshots to the correlation guard.

No order submission, no inferred account/order identity.
"""
from engines.ibkr_correlation_guard import verify_correlations

def diagnose_snapshot(snapshot, local_orders, mapping):
    blocked={"status":"BLOCKED","reason":"UNTRUSTED_SNAPSHOT","paper_order_submission_allowed":False,"live_trading_allowed":False}
    if not isinstance(snapshot,dict):
        return blocked
    if snapshot.get("status")!="CONNECTED":
        return {**blocked,"reason":"SNAPSHOT_NOT_CONNECTED"}
    complete=snapshot.get("requests_complete")
    if not isinstance(complete,dict) or not all(complete.get(k) is True for k in ("managed_accounts","account_summary","positions","open_orders")):
        return {**blocked,"reason":"INCOMPLETE_SNAPSHOT"}
    if not isinstance(snapshot.get("order_status"),list) or not isinstance(snapshot.get("executions"),list):
        return {**blocked,"reason":"MISSING_BROKER_ROWS"}
    # The current gateway does not provide a completion event for reqExecutions.
    # Therefore execution evidence cannot be considered complete or trusted.
    if complete.get("executions") is not True:
        return {**blocked,"reason":"EXECUTION_COMPLETENESS_UNPROVEN"}
    return verify_correlations(local_orders,snapshot,mapping)
