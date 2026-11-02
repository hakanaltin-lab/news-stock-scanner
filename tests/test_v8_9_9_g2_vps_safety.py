"""AURORA V8.9.9 G2 VPS deployment safety contract tests."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class G2VPSSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = read("scripts/bootstrap_aurora_g2_vps.sh")
        cls.vnc = read("scripts/start_aurora_vnc_local.sh")
        cls.configure = read("scripts/configure_aurora_g2_runtime.sh")
        cls.api_install = read("scripts/install_ibkr_official_api.sh")
        cls.gateway_download = read("scripts/download_ibgateway_stable.sh")
        cls.gateway_launch = read("scripts/launch_ibgateway_vnc.sh")
        cls.probe = read("scripts/run_aurora_g2_readonly.sh")
        cls.pre_review = read("scripts/run_aurora_g2_pre_review.sh")
        cls.all_scripts = "\n".join([
            cls.bootstrap, cls.vnc, cls.configure, cls.api_install,
            cls.gateway_download, cls.gateway_launch, cls.probe,
            cls.pre_review,
        ])

    def test_bootstrap_defaults_to_read_only_and_disabled_broker(self):
        self.assertIn("AURORA_RUN_MODE=READ_ONLY", self.bootstrap)
        self.assertIn("AURORA_IBKR_ENABLED=false", self.bootstrap)
        self.assertIn("AURORA_IBKR_MODE=PAPER", self.bootstrap)
        self.assertIn("AURORA_IBKR_HOST=127.0.0.1", self.bootstrap)
        self.assertIn("AURORA_IBKR_PORT=4002", self.bootstrap)
        self.assertIn("AURORA_IBKR_MARKET_DATA_ENABLED=false", self.bootstrap)

    def test_vnc_is_forced_to_localhost(self):
        self.assertIn("-localhost yes", self.vnc)
        self.assertIn("127\\.0\\.0\\.1", self.vnc)
        self.assertNotIn("0.0.0.0:5902", self.vnc)

    def test_gateway_download_is_official_stable_linux_x64(self):
        self.assertIn("download2.interactivebrokers.com", self.gateway_download)
        self.assertIn("ibgateway/stable-standalone", self.gateway_download)
        self.assertIn("ibgateway-stable-standalone-linux-x64.sh", self.gateway_download)

    def test_official_api_installer_requires_vendor_zip_name(self):
        self.assertIn("twsapi_macunix", self.api_install)
        self.assertIn("pip install", self.api_install)
        self.assertNotIn("pip install ibapi", self.api_install)

    def test_runtime_account_input_is_hidden_and_validated(self):
        self.assertIn("read -rs PAPER_ACCOUNT", self.configure)
        self.assertIn("^DU[[:alnum:]]+$", self.configure)
        self.assertNotIn("echo $PAPER_ACCOUNT", self.configure)

    def test_probe_requires_exact_paper_loopback_endpoint(self):
        self.assertIn('AURORA_RUN_MODE:-}" == "READ_ONLY"', self.probe)
        self.assertIn('AURORA_IBKR_MODE:-}" == "PAPER"', self.probe)
        self.assertIn('AURORA_IBKR_HOST:-}" == "127.0.0.1"', self.probe)
        self.assertIn('AURORA_IBKR_PORT:-}" == "4002"', self.probe)
        self.assertIn("IBKR TCP/4002 is publicly bound", self.probe)

    def test_strict_runner_does_not_source_runtime_env(self):
        self.assertNotIn('source "$ENV_FILE"', self.probe)
        self.assertIn('stat -c %a "$ENV_FILE"', self.probe)
        self.assertIn('stat -c %h "$ENV_FILE"', self.probe)
        self.assertIn('verify_gateway_readonly_attestation.py', self.probe)
        self.assertIn('g2_post_review_status.py', self.probe)
        self.assertIn('AURORA_EVIDENCE_RUN_ID', self.probe)
        self.assertIn(
            'export AURORA_IBKR_PROBE_OUTPUT="$FIXED_G2_OUTPUT"',
            self.probe,
        )
        self.assertLess(
            self.probe.index("verify_gateway_readonly_attestation.py"),
            self.probe.index("scripts/ibkr_paper_probe.py"),
        )

    def test_pre_review_runner_does_not_source_runtime_env(self):
        self.assertNotIn('source "$ENV_FILE"', self.pre_review)
        self.assertIn('stat -c %a "$ENV_FILE"', self.pre_review)
        self.assertIn('stat -c %h "$ENV_FILE"', self.pre_review)
        self.assertIn('AURORA_EVIDENCE_RUN_ID', self.pre_review)
        self.assertIn('g2_pre_review_status.py', self.pre_review)
        self.assertIn('[[ "$probe_rc" -eq 2 ]]', self.pre_review)
        self.assertNotIn('cat "$ENV_FILE"', self.pre_review)
        self.assertNotIn('echo "$AURORA_IBKR_PAPER_ACCOUNT_ALLOWLIST"', self.pre_review)

    def test_pre_review_runner_forces_fixed_evidence_output(self):
        self.assertIn(
            'FIXED_G2_OUTPUT="$REPO_DIR/runtime/ibkr_paper_read_only/latest.json"',
            self.pre_review,
        )
        self.assertIn(
            'export AURORA_IBKR_PROBE_OUTPUT="$FIXED_G2_OUTPUT"',
            self.pre_review,
        )

    def test_no_script_contains_order_submission_path(self):
        forbidden = [
            "placeOrder(",
            "submit_order(",
            "AURORA_RUN_MODE=PAPER_ENABLED",
            "AURORA_IBKR_MODE=LIVE",
            "AURORA_IBKR_PORT=4001",
        ]
        for token in forbidden:
            self.assertNotIn(token, self.all_scripts)

    def test_scripts_do_not_open_public_firewall_ports(self):
        forbidden = [
            "ufw allow 4002",
            "ufw allow 5902",
            "--allow=tcp:4002",
            "--allow=tcp:5902",
            "0.0.0.0/0:4002",
            "0.0.0.0/0:5902",
        ]
        for token in forbidden:
            self.assertNotIn(token, self.all_scripts)

    def test_credentials_are_never_requested_or_stored(self):
        lowered = self.all_scripts.lower()
        self.assertNotIn("ibkr_password=", lowered)
        self.assertNotIn("ibkr_username=", lowered)
        self.assertNotIn("tws_password=", lowered)

if __name__ == "__main__":
    unittest.main()
