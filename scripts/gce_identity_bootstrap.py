#!/usr/bin/env python3
"""Print sanitized, read-only GCE runtime identity for policy bootstrap.

This command:
- reads only non-secret GCE project/name/zone/instance-id metadata;
- never reads service-account, token, credential, or user-data metadata;
- never writes policy or attestation files;
- never authorizes Paper or LIVE orders.
"""

import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engines.gce_runtime_identity import read_gce_runtime_identity


def build_bootstrap_identity():
    identity = read_gce_runtime_identity()
    verified = (
        isinstance(identity, dict)
        and identity.get("status") == "VERIFIED"
        and identity.get("verified") is True
    )

    return {
        "engine": "AURORA G7.9 Safe GCE Identity Bootstrap",
        "status": "VERIFIED" if verified else "BLOCKED",
        "verified": verified,
        "project_id": identity.get("project_id") if verified else None,
        "instance_name": identity.get("instance_name") if verified else None,
        "zone": identity.get("zone") if verified else None,
        "instance_id": identity.get("instance_id") if verified else None,
        "failure_reasons": (
            []
            if verified
            else list(identity.get("failure_reasons") or ["GCE_RUNTIME_IDENTITY_UNVERIFIED"])
        ),
        "policy_write_allowed": False,
        "attestation_write_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
    }


def main():
    result = build_bootstrap_identity()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
