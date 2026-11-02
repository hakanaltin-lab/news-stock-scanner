"""Sanitized G0/G1 runtime proof must enforce the full cloud contract."""

import unittest

from scripts.gcp_runtime_proof import evaluate_gcp_runtime_proof


def vm():
    return {
        "name": "aurora-trading-vps",
        "id": "1234567890123456789",
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
        self.assertEqual(
            result["gce_instance_id"],
            "1234567890123456789",
        )
        self.assertTrue(
            result["checks"]["vm_instance_id_valid"]
        )
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

    def test_malformed_top_level_cloud_payloads_fail_closed(self):
        cases = (
            ([], rules(), budget()),
            ("invalid", rules(), budget()),
            (vm(), "invalid", budget()),
            (vm(), [None], budget()),
            (vm(), rules(), []),
        )
        for vm_payload, firewall_payload, budget_payload in cases:
            with self.subTest(
                vm_type=type(vm_payload).__name__,
                firewall_type=type(firewall_payload).__name__,
                budget_type=type(budget_payload).__name__,
            ):
                result = evaluate_gcp_runtime_proof(
                    vm_payload,
                    firewall_payload,
                    budget_payload,
                )
                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertIn(
                    "source_payloads_valid",
                    result["failure_reasons"],
                )

    def test_malformed_nested_vm_payloads_do_not_raise(self):
        candidate = vm()
        candidate["metadata"] = []
        candidate["tags"] = "invalid"
        candidate["networkInterfaces"] = "invalid"

        result = evaluate_gcp_runtime_proof(
            candidate,
            rules(),
            budget(),
        )

        self.assertEqual(
            result["status"],
            "BLOCKED",
        )
        self.assertIn(
            "vm_hardened",
            result["failure_reasons"],
        )
        self.assertIn(
            "network_contract",
            result["failure_reasons"],
        )

    def test_missing_or_invalid_immutable_instance_id_blocks(self):
        for value in (
            None,
            "",
            "0",
            "000123456",
            "abc123456",
            "12345",
            True,
        ):
            with self.subTest(value=value):
                candidate = vm()
                if value is None:
                    candidate.pop("id")
                else:
                    candidate["id"] = value

                result = evaluate_gcp_runtime_proof(
                    candidate,
                    rules(),
                    budget(),
                )

                self.assertEqual(
                    result["status"],
                    "BLOCKED",
                )
                self.assertIn(
                    "vm_instance_id_valid",
                    result["failure_reasons"],
                )
                self.assertIsNone(
                    result["gce_instance_id"]
                )

    def test_integer_instance_id_is_canonicalized_without_loss(self):
        candidate = vm()
        candidate["id"] = 1234567890123456789
        result = evaluate_gcp_runtime_proof(
            candidate,
            rules(),
            budget(),
        )
        self.assertEqual(
            result["status"],
            "G0_G1_VERIFIED",
        )
        self.assertEqual(
            result["gce_instance_id"],
            "1234567890123456789",
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
