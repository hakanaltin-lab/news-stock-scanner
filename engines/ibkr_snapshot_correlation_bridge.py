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
    if not isinstance(snapshot.get("order_status"),list) or not isinstance(snapshot.get("executions"),list) or not isinstance(snapshot.get("open_orders"),list):
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
        if item["perm_id"] not in seen and not any(
            isinstance(row,dict) and row.get("perm_id")==item["perm_id"]
            for row in snapshot["open_orders"]
        ):
            return {**blocked,"reason":"BROKER_CORRELATION_NOT_OBSERVED"}
    for item in mapping.values():
        matching=[row for row in rows+snapshot["open_orders"] if row.get("perm_id")==item["perm_id"]]
        # IBKR orderStatus has no account field. Broker-origin execution or
        # openOrder records can independently prove the account identity.
        evidence=[row for row in snapshot["executions"]+snapshot["open_orders"] if row.get("perm_id")==item["perm_id"]]
        if not evidence:
            return {**blocked,"reason":"BROKER_ACCOUNT_EVIDENCE_UNAVAILABLE"}
        if not any(row.get("order_id")==item["order_id"] and row.get("client_id")==item["client_id"] and row.get("account")==item["account"] for row in evidence):
            return {**blocked,"reason":"BROKER_IDENTITY_MISMATCH"}
        # Never silently accept contradictory broker-origin account/identity
        # rows for the same permanent ID, even if one matching row exists.
        if any(row.get("order_id")!=item["order_id"] or row.get("client_id")!=item["client_id"] or row.get("account")!=item["account"] for row in evidence):
            return {**blocked,"reason":"CONFLICTING_BROKER_IDENTITY"}
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
    # A broker order-status cumulative fill cannot be smaller than fills
    # observed in the same snapshot. Do not assert equality: reqExecutions
    # covers only its request window, not necessarily all historical fills.
    for item in mapping.values():
        relevant=[row for row in snapshot["executions"] if row["perm_id"]==item["perm_id"]]
        observed=sum(row["shares"] for row in relevant)
        statuses=[row for row in snapshot["order_status"] if row.get("perm_id")==item["perm_id"] and row.get("order_id")==item["order_id"] and row.get("client_id")==item["client_id"]]
        fills=[]
        for status in statuses:
            filled=status.get("filled")
            if type(filled) not in (int,float) or not math.isfinite(filled) or filled<0:
                return {**blocked,"reason":"INVALID_CUMULATIVE_FILL"}
            fills.append(filled)
        # orderStatus can emit intermediate cumulative fills (0, then 2).
        # Compare against the highest observed cumulative value, not every
        # intermediate callback; missing status history proves no quantity cap.
        if fills and observed>max(fills)+1e-7:
            return {**blocked,"reason":"EXECUTIONS_EXCEED_REPORTED_FILL"}
    # Broker status callbacks can repeat, but cumulative filled quantity
    # must never contradict the remaining quantity for the same order.
    for item in mapping.values():
        statuses=[row for row in snapshot["order_status"] if row.get("perm_id")==item["perm_id"]]
        for status in statuses:
            if status.get("order_id")!=item["order_id"] or status.get("client_id")!=item["client_id"]:
                return {**blocked,"reason":"CONFLICTING_ORDER_STATUS_IDENTITY"}
            remaining=status.get("remaining")
            if type(remaining) not in (int,float) or not math.isfinite(remaining) or remaining<0:
                return {**blocked,"reason":"INVALID_REMAINING_QUANTITY"}
            state=status.get("status")
            if state=="Filled" and (remaining>1e-7 or status["filled"]<=0):
                return {**blocked,"reason":"CONFLICTING_FILLED_STATUS"}
    return result
