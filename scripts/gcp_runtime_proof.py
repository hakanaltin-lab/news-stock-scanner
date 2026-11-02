#!/usr/bin/env python3
"""Create a sanitized G0/G1 proof from read-only gcloud JSON snapshots."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


PROJECT_ID = "project-ce9773ef-6814-469c-92b"
ZONE = "europe-west3-a"
VM_NAME = "aurora-trading-vps"
MACHINE_TYPE = "e2-medium"
VPC = "aurora-vpc"
SUBNET = "aurora-eu3-subnet"
NETWORK_TAG = "aurora-admin"
IAP_RANGE = "35.235.240.0/20"
IAP_RULE = "aurora-allow-iap-ssh"
DENY_RULE = "aurora-deny-public-private-ports"


def _canonical_instance_id(value):
    if isinstance(value, bool):
        return None

    if not isinstance(value, (str, int)):
        return None

    text = str(value).strip()

    if (
        not text.isdigit()
        or len(text) < 6
        or len(text) > 30
        or text[0] == "0"
    ):
        return None

    return text


def _suffix(value, expected):
    return str(value or "").endswith("/" + expected)


def _port_is_allowed(rule, port):
    for item in rule.get("allowed") or []:
        protocol = str(item.get("IPProtocol") or "").lower()
        if protocol == "all":
            return True
        if protocol != "tcp":
            continue
        ports = item.get("ports")
        if not ports:
            return True
        for value in ports:
            text = str(value)
            if "-" in text:
                start, end = text.split("-", 1)
                try:
                    if int(start) <= port <= int(end):
                        return True
                except ValueError:
                    continue
            elif text == str(port):
                return True
    return False


def _public_allow_rules(firewall_rules):
    exposed = []
    for rule in firewall_rules or []:
        if str(rule.get("direction") or "INGRESS").upper() != "INGRESS":
            continue
        if rule.get("disabled") is True:
            continue
        sources = rule.get("sourceRanges") or ["0.0.0.0/0"]
        if "0.0.0.0/0" not in sources and "::/0" not in sources:
            continue
        tags = set(rule.get("targetTags") or [])
        if tags and NETWORK_TAG not in tags:
            continue
        ports = [
            port
            for port in (22, 4002, 5902)
            if _port_is_allowed(rule, port)
        ]
        if ports:
            exposed.append({
                "name": rule.get("name"),
                "ports": ports,
            })
    return exposed


def evaluate_gcp_runtime_proof(vm, firewall_rules, budget_proof):
    source_payloads_valid = (
        isinstance(vm, dict)
        and isinstance(firewall_rules, list)
        and all(
            isinstance(item, dict)
            for item in firewall_rules
        )
        and isinstance(budget_proof, dict)
    )

    vm = vm if isinstance(vm, dict) else {}
    firewall_rules = (
        firewall_rules
        if isinstance(firewall_rules, list)
        and all(
            isinstance(item, dict)
            for item in firewall_rules
        )
        else []
    )
    budget_proof = (
        budget_proof
        if isinstance(budget_proof, dict)
        else {}
    )

    rules_by_name = {
        item.get("name"): item
        for item in firewall_rules
    }
    iap = rules_by_name.get(IAP_RULE) or {}
    deny = rules_by_name.get(DENY_RULE) or {}

    metadata_block = (
        vm.get("metadata")
        if isinstance(vm.get("metadata"), dict)
        else {}
    )
    metadata_items = (
        metadata_block.get("items")
        if isinstance(metadata_block.get("items"), list)
        else []
    )
    metadata = {
        item.get("key"): item.get("value")
        for item in metadata_items
        if isinstance(item, dict)
    }

    tags_block = (
        vm.get("tags")
        if isinstance(vm.get("tags"), dict)
        else {}
    )
    tag_items = (
        tags_block.get("items")
        if isinstance(tags_block.get("items"), list)
        else []
    )
    tags = set(
        item
        for item in tag_items
        if isinstance(item, str)
    )

    network_interfaces = vm.get("networkInterfaces")
    nic = (
        network_interfaces[0]
        if isinstance(network_interfaces, list)
        and network_interfaces
        and isinstance(network_interfaces[0], dict)
        else {}
    )
    gce_instance_id = _canonical_instance_id(
        vm.get("id")
    )

    checks = {
        "source_payloads_valid": source_payloads_valid,
        "budget_guard_passed": (
            budget_proof.get("status") == "PASS"
            and budget_proof.get("paid_resource_creation_allowed") is True
            and budget_proof.get("expected_currency") == "TRY"
            and budget_proof.get("expected_amount") == "750"
        ),
        "vm_identity": (
            vm.get("name") == VM_NAME
            and _suffix(vm.get("zone"), ZONE)
            and _suffix(vm.get("machineType"), MACHINE_TYPE)
        ),
        "vm_instance_id_valid": (
            gce_instance_id is not None
        ),
        "vm_running": vm.get("status") == "RUNNING",
        "vm_hardened": (
            vm.get("deletionProtection") is True
            and (vm.get("shieldedInstanceConfig") or {}).get(
                "enableSecureBoot"
            ) is True
            and (vm.get("shieldedInstanceConfig") or {}).get(
                "enableVtpm"
            ) is True
            and (vm.get("shieldedInstanceConfig") or {}).get(
                "enableIntegrityMonitoring"
            ) is True
            and metadata.get("enable-oslogin") == "TRUE"
            and vm.get("serviceAccounts", []) == []
        ),
        "network_contract": (
            _suffix(nic.get("network"), VPC)
            and _suffix(nic.get("subnetwork"), SUBNET)
            and NETWORK_TAG in tags
        ),
        "iap_ssh_only_rule": (
            str(iap.get("direction") or "").upper() == "INGRESS"
            and iap.get("disabled") is not True
            and iap.get("priority") == 1000
            and iap.get("sourceRanges") == [IAP_RANGE]
            and set(iap.get("targetTags") or []) == {NETWORK_TAG}
            and _suffix(iap.get("network"), VPC)
            and _port_is_allowed(iap, 22)
            and not _port_is_allowed(iap, 4002)
            and not _port_is_allowed(iap, 5902)
        ),
        "public_private_ports_denied": (
            str(deny.get("direction") or "").upper() == "INGRESS"
            and deny.get("disabled") is not True
            and deny.get("priority") == 900
            and deny.get("sourceRanges") == ["0.0.0.0/0"]
            and set(deny.get("targetTags") or []) == {NETWORK_TAG}
            and _suffix(deny.get("network"), VPC)
            and any(
                str(item.get("IPProtocol") or "").lower() == "tcp"
                and set(item.get("ports") or []) == {"4002", "5902"}
                for item in deny.get("denied") or []
            )
        ),
        "no_public_allow_for_sensitive_ports": not _public_allow_rules(
            firewall_rules
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "engine": "AURORA V8.9.20 G0-G1 Runtime Proof",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "zone": ZONE,
        "vm_name": VM_NAME,
        "gce_instance_id": (
            gce_instance_id
            if gce_instance_id is not None
            else None
        ),
        "status": "G0_G1_VERIFIED" if not failures else "BLOCKED",
        "checks": checks,
        "failure_reasons": failures,
        "external_ip_present": bool(nic.get("accessConfigs")),
        "public_sensitive_allow_rules": _public_allow_rules(firewall_rules),
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
    }


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(target.parent),
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, target)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--vm-json", required=True)
    parser.add_argument("--firewall-json", required=True)
    parser.add_argument("--budget-proof", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = evaluate_gcp_runtime_proof(
        _read_json(args.vm_json),
        _read_json(args.firewall_json),
        _read_json(args.budget_proof),
    )
    _write_atomic(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "G0_G1_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
