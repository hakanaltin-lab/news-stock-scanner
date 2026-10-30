"""AURORA V8.9.8 Google Cloud provisioning contract tests."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provision_aurora_gcp.sh"

class GCPProvisioningContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_target_project_and_vm_are_pinned(self):
        self.assertIn('PROJECT_ID="project-ce9773ef-6814-469c-92b"', self.source)
        self.assertIn('VM_NAME="aurora-trading-vps"', self.source)
        self.assertIn('ZONE="europe-west3-a"', self.source)
        self.assertIn('REGION="europe-west3"', self.source)

    def test_machine_os_and_disk_contract(self):
        self.assertIn('MACHINE_TYPE="e2-medium"', self.source)
        self.assertIn('IMAGE_FAMILY="ubuntu-minimal-2204-lts"', self.source)
        self.assertIn('BOOT_DISK_SIZE="30GB"', self.source)
        self.assertIn('BOOT_DISK_TYPE="pd-standard"', self.source)

    def test_vm_creation_declares_exactly_one_network_interface(self):
        self.assertEqual(
            self.source.count('--network-interface="network=$VPC,subnet=$SUBNET,network-tier=PREMIUM"'),
            1,
        )
        self.assertIn("--network-interface=nic0", self.source)

    def test_iap_ssh_source_is_exact(self):
        self.assertIn('IAP_RANGE="35.235.240.0/20"', self.source)
        self.assertIn("--rules=tcp:22", self.source)
        self.assertNotIn("--allow=tcp:22 --source-ranges=0.0.0.0/0", self.source)

    def test_ibkr_and_vnc_public_ports_are_explicitly_denied(self):
        self.assertIn("--rules=tcp:4002,tcp:5902", self.source)
        self.assertIn("--action=DENY", self.source)
        self.assertNotIn("--allow=tcp:4002", self.source)
        self.assertNotIn("--allow=tcp:5902", self.source)

    def test_vm_has_no_service_account_or_oauth_scopes(self):
        self.assertIn("--no-service-account", self.source)
        self.assertIn("--no-scopes", self.source)

    def test_os_login_and_shielded_vm_are_required(self):
        self.assertIn('--metadata="enable-oslogin=TRUE"', self.source)
        self.assertIn("--shielded-secure-boot", self.source)
        self.assertIn("--shielded-vtpm", self.source)
        self.assertIn("--shielded-integrity-monitoring", self.source)
        self.assertIn("--deletion-protection", self.source)

    def test_ssh_password_and_root_login_are_disabled(self):
        self.assertIn("PasswordAuthentication no", self.source)
        self.assertIn("PermitRootLogin no", self.source)

    def test_existing_vm_network_attachment_is_self_healed(self):
        self.assertIn(
            "gcloud compute instances network-interfaces update",
            self.source,
        )
        self.assertIn(
            "--network-interface=nic0",
            self.source,
        )
        self.assertIn(
            '--network="$VPC"',
            self.source,
        )
        self.assertIn(
            '--subnetwork="$SUBNET"',
            self.source,
        )
        self.assertIn(
            'gcloud compute instances stop "$VM_NAME"',
            self.source,
        )
        self.assertIn(
            'gcloud compute instances start "$VM_NAME"',
            self.source,
        )

    def test_billing_check_matches_current_google_cloud_cli(self):
        self.assertIn(
            "gcloud beta billing projects describe",
            self.source,
        )

    def test_apply_flag_is_required_for_creation(self):
        self.assertIn('if [[ "${1:-}" == "--apply" ]]', self.source)
        self.assertIn("PLAN: resource creation commands are not executed.", self.source)

    def test_budget_guard_runs_before_paid_resource_work(self):
        self.assertIn("billingbudgets.googleapis.com", self.source)
        self.assertIn("scripts/gcp_budget_guard.py", self.source)
        self.assertIn("--currency TRY", self.source)
        self.assertIn("--amount 750", self.source)
        self.assertLess(
            self.source.index('log "Verify approved TRY 750 budget alert"'),
            self.source.index('log "Ensure custom VPC"'),
        )

    def test_provisioning_never_creates_or_edits_a_budget(self):
        self.assertNotIn("billing budgets create", self.source)
        self.assertNotIn("billing budgets update", self.source)
        self.assertNotIn("billing budgets delete", self.source)

if __name__ == "__main__":
    unittest.main()
