"""Read-only correlation validation; never submits broker orders."""
def verify_correlations(local, snapshot, mapping):
    base={"status":"BLOCKED","paper_order_submission_allowed":False,"live_trading_allowed":False}
    if not all(isinstance(x,dict) for x in (local,snapshot,mapping)):
        return {**base,"reason":"INVALID_INPUT"}
    guard=snapshot.get("paper_account_guard") or {}
    accounts=guard.get("verified_account_fingerprints")
    if guard.get("paper_account_verified") is not True or not isinstance(accounts,list) or len(accounts)!=1:
        return {**base,"reason":"UNVERIFIED_ACCOUNT"}
    if not local or set(local)!=set(mapping):
        return {**base,"reason":"MISSING_MAPPING"}
    seen=set()
    for key,order in local.items():
        item=mapping.get(key)
        if not isinstance(order,dict) or not isinstance(item,dict):
            return {**base,"reason":"INVALID_MAPPING"}
        if item.get("account")!=accounts[0] or order.get("account")!=accounts[0]:
            return {**base,"reason":"ACCOUNT_MISMATCH"}
        if order.get("idempotency_key")!=key:
            return {**base,"reason":"IDEMPOTENCY_MISMATCH"}
        for field,minimum in (("perm_id",1),("order_id",0),("client_id",0)):
            value=item.get(field)
            if type(value) is not int or value<minimum:
                return {**base,"reason":"INVALID_"+field.upper()}
        identity=(accounts[0],item["perm_id"])
        if identity in seen:
            return {**base,"reason":"DUPLICATE_PERM_ID"}
        seen.add(identity)
    return {**base,"status":"CORRELATIONS_VERIFIED","reason":"READ_ONLY_DIAGNOSTIC_ONLY"}
