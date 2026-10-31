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
    # The completion callback covers this reqExecutions response only,
    # not all historical executions or broker-wide order history.
    if complete.get("executions") is not True:
        return {**blocked,"reason":"EXECUTION_COMPLETENESS_UNPROVEN"}
    if snapshot.get("order_submission_hard_blocked") is not True or snapshot.get("live_trading_allowed") is not False:
        return {**blocked,"reason":"ORDER_SAFETY_GUARD_UNPROVEN"}
    config=snapshot.get("config")
    if not isinstance(config,dict) or config.get("mode")!="PAPER" or config.get("endpoint_safe") is not True or config.get("read_only") is not True:
        return {**blocked,"reason":"UNSAFE_BROKER_ENDPOINT"}
    return verify_correlations(local_orders,snapshot,mapping)
