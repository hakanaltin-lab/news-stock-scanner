"""AURORA V8.9.10 one-command bootstrap safety tests."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provision_and_bootstrap_aurora.sh"

class OneCommandBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_target_is_pinned(self):
        self.assertIn('PROJECT_ID="project-ce9773ef-6814-469c-92b"', self.source)
        self.assertIn('ZONE="europe-west3-a"', self.source)
        self.assertIn('VM_NAME="aurora-trading-vps"', self.source)

    def test_calls_approved_provisioning_with_apply(self):
        self.assertIn("provision_aurora_gcp.sh", self.source)
        self.assertIn('bash "$PROVISION_SCRIPT" --apply', self.source)

    def test_remote_access_is_iap_only(self):
        self.assertGreaterEqual(self.source.count("--tunnel-through-iap"), 2)
        self.assertNotIn("--ssh-flag=-L 4002", self.source)

    def test_bootstrap_keeps_broker_disabled(self):
        self.assertIn('grep -qx "AURORA_IBKR_ENABLED=false"', self.source)
        self.assertIn('grep -qx "AURORA_IBKR_MARKET_DATA_ENABLED=false"', self.source)
        self.assertIn('grep -qx "AURORA_IBKR_MODE=PAPER"', self.source)
        self.assertIn('grep -qx "AURORA_IBKR_PORT=4002"', self.source)

    def test_public_private_ports_are_rejected(self):
        self.assertIn("TCP/$port is publicly bound", self.source)
        self.assertIn("4002 5902", self.source)

    def test_no_credentials_or_order_submission(self):
        lowered = self.source.lower()
        for token in [
            "placeorder(",
            "submit_order(",
            "ibkr_password=",
            "ibkr_username=",
            "aurora_ibkr_mode=live",
            "aurora_run_mode=paper_enabled",
        ]:
            self.assertNotIn(token, lowered)

if __name__ == "__main__":
    unittest.main()
