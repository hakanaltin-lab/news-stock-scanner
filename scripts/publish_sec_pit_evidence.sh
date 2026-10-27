#!/usr/bin/env bash
set -euo pipefail

# A rerun may collect evidence on an older checkout. Preserve its output before
# advancing to current main; rebasing generated JSON causes avoidable conflicts.
cd "$(git rev-parse --show-toplevel)"
test -f data/sec_edgar_pit/latest_summary.json
test -f docs/sec_archive_readiness.json

SEC_PUBLISH_TMP="$(mktemp -d)"
trap 'rm -rf "$SEC_PUBLISH_TMP"' EXIT
mkdir -p "$SEC_PUBLISH_TMP/data" "$SEC_PUBLISH_TMP/docs"
cp -a data/sec_edgar_pit "$SEC_PUBLISH_TMP/data/"
cp docs/sec_archive_readiness.json "$SEC_PUBLISH_TMP/docs/"

for attempt in 1 2 3; do
  echo "SEC evidence publish attempt $attempt"
  git fetch origin main
  git reset --hard origin/main

  mkdir -p data docs
  cp -a "$SEC_PUBLISH_TMP/data/sec_edgar_pit" data/
  cp "$SEC_PUBLISH_TMP/docs/sec_archive_readiness.json" docs/
  git add -- data/sec_edgar_pit docs/sec_archive_readiness.json

  if git diff --cached --quiet; then
    echo "SEC evidence is already current"
    exit 0
  fi

  git commit -m "Update SEC EDGAR point-in-time evidence"
  if git push origin HEAD:main; then
    echo "SEC evidence published successfully"
    exit 0
  fi
  echo "Main advanced during publishing; retrying on the latest head"
done

echo "SEC evidence publishing failed after three attempts; use the workflow artifact"
exit 1
