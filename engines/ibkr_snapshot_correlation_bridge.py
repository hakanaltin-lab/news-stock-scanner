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
    result=verify_correlations(local_orders,snapshot,mapping)
    if result.get("status")!="CORRELATIONS_VERIFIED":
        return result
    # A supplied mapping is not broker evidence: require observed permanent IDs.
    rows=snapshot.get("order_status")+snapshot.get("executions")
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            return {**blocked,"reason":"INVALID_BROKER_ROW"}
        perm_id=row.get("perm_id")
        if type(perm_id) is not int or perm_id<=0:
            return {**blocked,"reason":"BROKER_PERM_ID_MISSING"}
        seen.add(perm_id)
    for item in mapping.values():
        if item["perm_id"] not in seen:
            return {**blocked,"reason":"BROKER_CORRELATION_NOT_OBSERVED"}
    for item in mapping.values():
        matching=[row for row in rows if row["perm_id"]==item["perm_id"]]
        if not any(row.get("order_id")==item["order_id"] and row.get("client_id")==item["client_id"] and row.get("account")==item["account"] for row in matching):
            return {**blocked,"reason":"BROKER_IDENTITY_MISMATCH"}
    # Reconcile observed execution quantities without assuming history completeness.
    # Empty executions remain a valid read-only snapshot (no observed fills).
    import math
    execution_ids=set()
    for row in snapshot["executions"]:
        if not isinstance(row,dict):
            return {**blocked,"reason":"INVALID_EXECUTION_ROW"}
        exec_id=row.get("execution_id")
        shares=row.get("shares")
        if not isinstance(exec_id,str) or not exec_id.strip() or exec_id in execution_ids:
            return {**blocked,"reason":"INVALID_OR_DUPLICATE_EXECUTION_ID"}
        execution_ids.add(exec_id)
        if type(shares) not in (int,float) or not math.isfinite(shares) or shares<=0:
            return {**blocked,"reason":"INVALID_EXECUTION_QUANTITY"}
        if not any(row.get("perm_id")==item["perm_id"] and row.get("order_id")==item["order_id"] and row.get("client_id")==item["client_id"] and row.get("account")==item["account"] for item in mapping.values()):
            return {**blocked,"reason":"UNMATCHED_EXECUTION_IDENTITY"}
    return result
