"""Exercise real Git races without network access or production repositories."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


PUBLISH_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/publish_sec_pit_evidence.sh"
SUMMARY = "data/sec_edgar_pit/latest_summary.json"
DASHBOARD = "docs/sec_archive_readiness.json"
FACT = "data/sec_edgar_pit/facts/AAA.json"


def git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def write(directory, path, value):
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value) + "\n")


def configure(directory):
    git(directory, "config", "user.name", "Offline publisher test")
    git(directory, "config", "user.email", "test@example.invalid")


class EvidencePublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.writer = self.root / "writer"
        self.runner = self.root / "runner"
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.root, "clone", str(self.remote), str(self.writer))
        configure(self.writer)
        for path in [SUMMARY, DASHBOARD]:
            write(self.writer, path, {"status": "DISABLED_MISSING_SEC_USER_AGENT"})
        git(self.writer, "add", ".")
        git(self.writer, "commit", "-m", "Initial blocked status")
        git(self.writer, "push", "origin", "main")
        git(self.root, "clone", str(self.remote), str(self.runner))
        configure(self.runner)
        for path in [SUMMARY, DASHBOARD]:
            write(self.runner, path, {"status": "COMPLETE_WITH_GAPS", "usable_ticker_count": 514})
        write(self.runner, FACT, {"ticker": "AAA", "facts": [{"value": 123}]})

    def advance_main(self, marker="concurrent-report.json"):
        write(self.writer, marker, {"preserve": True})
        for path in [SUMMARY, DASHBOARD]:
            write(self.writer, path, {"status": "DISABLED_MISSING_SEC_USER_AGENT", "newer_checkout": True})
        git(self.writer, "add", ".")
        git(self.writer, "commit", "-m", "Concurrent report update")
        git(self.writer, "push", "origin", "main")

    def publish(self):
        return subprocess.run(
            ["bash", str(PUBLISH_SCRIPT)], cwd=self.runner,
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        ).stdout

    def assert_remote_evidence(self):
        summary = json.loads(git(self.remote, "show", "main:" + SUMMARY))
        self.assertEqual(summary["usable_ticker_count"], 514)
        self.assertEqual(json.loads(git(self.remote, "show", "main:" + FACT))["ticker"], "AAA")
        self.assertEqual(git(self.runner, "status", "--porcelain"), "")

    def test_old_checkout_publishes_without_rebasing_generated_json(self):
        self.advance_main()
        output = self.publish()
        self.assertIn("published successfully", output)
        self.assert_remote_evidence()
        self.assertEqual(json.loads(git(self.remote, "show", "main:concurrent-report.json")), {"preserve": True})

    def test_push_race_retries_and_preserves_both_writers(self):
        # Advance the remote between the publisher's fetch and its first push.
        hook = self.runner / ".git/hooks/pre-push"
        flag = self.root / "race-happened"
        writer = shlex.quote(str(self.writer))
        marker = shlex.quote(str(flag))
        hook.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + "if [ ! -f " + marker + " ]; then\n"
            + "  touch " + marker + "\n"
            + "  printf '%s\\n' '{\"preserve\":true}' > "
            + shlex.quote(str(self.writer / "push-race.json")) + "\n"
            + "  git -C " + writer + " add push-race.json\n"
            + "  git -C " + writer + " commit -m 'Push race'\n"
            + "  git -C " + writer + " push origin main\n"
            + "  exit 1\nfi\n"
        )
        hook.chmod(0o755)
        output = self.publish()
        self.assertIn("publish attempt 2", output)
        self.assert_remote_evidence()
        self.assertEqual(json.loads(git(self.remote, "show", "main:push-race.json")), {"preserve": True})

    def test_no_change_does_not_create_an_extra_commit(self):
        self.publish()
        first = git(self.remote, "rev-parse", "main")
        output = self.publish()
        self.assertIn("already current", output)
        self.assertEqual(git(self.remote, "rev-parse", "main"), first)


if __name__ == "__main__":
    unittest.main()
