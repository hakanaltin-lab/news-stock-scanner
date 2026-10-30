"""Sanitized G0/G1 runtime proof must enforce the full cloud contract."""

import unittest

from scripts.gcp_runtime_proof import evaluate_gcp_runtime_proof


def vm():
    return {
        "name": "aurora-trading-vps",
        "zone": "projects/p/zones/europe-west3-a",
        "machineType": "projects/p/zones/europe-west3-a/machineTypes/e2-medium",
        "status": "RUNNING",
        "deletionProtection": True,
        "shieldedInstanceConfig": {
            "enableSecureBoot": True,
            "enableVtpm": True,
            "enableIntegrityMonitoring": True,
        },
        "metadata": {"items": [{"key": "enable-oslogin", "value": "TRUE"}]},
        "serviceAccounts": [],
        "tags": {"items": ["aurora-admin"]},
        "networkInterfaces": [{
            "network": "projects/p/global/networks/aurora-vpc",
            "subnetwork": "projects/p/regions/europe-west3/subnetworks/aurora-eu3-subnet",
            "accessConfigs": [{}],
        }],
    }


def rules(extra=None):
    items = [
        {
            "name": "aurora-allow-iap-ssh",
            "network": "projects/p/global/networks/aurora-vpc",
            "direction": "INGRESS",
            "priority": 1000,
            "sourceRanges": ["35.235.240.0/20"],
            "targetTags": ["aurora-admin"],
            "allowed": [{"IPProtocol": "tcp", "ports": ["22"]}],
        },
        {
            "name": "aurora-deny-public-private-ports",
            "network": "projects/p/global/networks/aurora-vpc",
            "direction": "INGRESS",
            "priority": 900,
            "sourceRanges": ["0.0.0.0/0"],
            "targetTags": ["aurora-admin"],
            "denied": [{"IPProtocol": "tcp", "ports": ["4002", "5902"]}],
        },
    ]
    return items + list(extra or [])


def budget():
    return {
        "status": "PASS",
        "expected_currency": "TRY",
        "expected_amount": "750",
        "paid_resource_creation_allowed": True,
    }


class GCPRuntimeProofTests(unittest.TestCase):
    def test_exact_contract_passes_without_exposing_ip(self):
        result = evaluate_gcp_runtime_proof(vm(), rules(), budget())
        self.assertEqual(result["status"], "G0_G1_VERIFIED")
        self.assertTrue(result["external_ip_present"])
        self.assertNotIn("natIP", result)
        self.assertFalse(result["paper_order_submission_allowed"])

    def test_budget_or_vm_mismatch_blocks(self):
        bad_budget = budget()
        bad_budget["expected_amount"] = "751"
        bad_vm = vm()
        bad_vm["machineType"] = "projects/p/zones/z/machineTypes/e2-large"
        self.assertIn(
            "budget_guard_passed",
            evaluate_gcp_runtime_proof(vm(), rules(), bad_budget)["failure_reasons"],
        )
        self.assertIn(
            "vm_identity",
            evaluate_gcp_runtime_proof(bad_vm, rules(), budget())["failure_reasons"],
        )

    def test_public_sensitive_allow_rule_blocks(self):
        public = {
            "name": "bad-public-allow",
            "network": "projects/p/global/networks/aurora-vpc",
            "direction": "INGRESS",
            "priority": 800,
            "sourceRanges": ["0.0.0.0/0"],
            "targetTags": ["aurora-admin"],
            "allowed": [{"IPProtocol": "tcp", "ports": ["22", "4002"]}],
        }
        result = evaluate_gcp_runtime_proof(vm(), rules([public]), budget())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "no_public_allow_for_sensitive_ports",
            result["failure_reasons"],
        )
        self.assertEqual(result["public_sensitive_allow_rules"][0]["ports"], [22, 4002])

    def test_missing_or_weakened_firewall_rules_block(self):
        self.assertIn(
            "iap_ssh_only_rule",
            evaluate_gcp_runtime_proof(vm(), rules()[1:], budget())["failure_reasons"],
        )
        weakened = rules()
        weakened[1]["priority"] = 1100
        self.assertIn(
            "public_private_ports_denied",
            evaluate_gcp_runtime_proof(vm(), weakened, budget())["failure_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
