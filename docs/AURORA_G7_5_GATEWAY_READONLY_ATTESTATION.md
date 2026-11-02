# AURORA G7.5 — Independent Gateway Read-Only Attestation

G7.5 converts the IB Gateway/TWS **Read-Only API** setting from a software
declaration into a separately reviewed, cryptographically signed runtime
attestation.

This gate does **not** enable Paper orders or LIVE trading.

## Trust boundary

AURORA cannot create a positive attestation for itself.

Production verification uses fixed paths only:

- policy: `/etc/aurora/gateway-readonly-attestation-policy.json`
- reviewer public key: `/etc/aurora/gateway-readonly-reviewer-ed25519.pem`
- signed artifact: `/var/lib/aurora/gateway-readonly-attestation/latest.json`

There are intentionally no environment-variable or command-line path overrides
for the production verifier.

The policy and reviewer public key must be root-owned, regular files, located
under a root-owned non-writable parent directory, and not group/world writable.
Symlinks are rejected. The signed artifact may be produced outside the VPS but
must not be world-writable or a symlink.

## Separation of duties

The reviewer private Ed25519 key must never be copied to the AURORA VPS, GitHub
repository, runtime environment, shell history, or ChatGPT conversation.

An independent reviewer should:

1. inspect the live IB Gateway/TWS API configuration on the approved Paper VPS;
2. confirm API socket port `4002` and the **Read-Only API** setting are enabled;
3. capture sanitized evidence without credentials or raw account identifiers;
4. hash that evidence with SHA-256;
5. create the attestation artifact for the exact deployed Git commit and VPS;
6. sign the canonical JSON payload using the reviewer private Ed25519 key;
7. provide only the signed artifact to the AURORA operator.

A separate administrator installs the reviewer public key and the root-owned
policy. The operator cannot replace the trusted reviewer key through AURORA
environment variables.

## Signed fields

The signature covers every artifact field except `signature_b64`, using
canonical JSON with sorted keys and compact separators.

The verifier requires:

- schema version 2;
- canonical UUIDv4 attestation ID;
- attestation type `IBKR_GATEWAY_API_READ_ONLY_V3`;
- decision `ATTESTED`;
- the exact reviewer ID pinned by policy;
- an exact 40-character Git SHA matching the currently checked-out commit;
- a clean tracked Git working tree;
- VPS instance `aurora-trading-vps`;
- zone `europe-west3-a`;
- GCP project `project-ce9773ef-6814-469c-92b`;
- the immutable numeric GCE instance ID pinned in both policy and signed artifact;
- live link-local GCE metadata matching project, VM name, zone and instance ID;
- broker mode `PAPER`;
- Gateway port `4002`;
- `read_only_api_enabled=true`;
- a non-zero SHA-256 evidence hash;
- an attestation freshness window within policy;
- a valid detached Ed25519 signature from the pinned reviewer public key.

Any unknown field, missing field, duplicate JSON key, malformed timestamp,
expired/future evidence, key mismatch, dirty repository, invalid signature,
GCE metadata mismatch/unavailability, or filesystem trust failure blocks the
attestation.

G7.7 reads only four non-secret attributes from the fixed link-local endpoint
`169.254.169.254`: project ID, instance name, zone and numeric instance ID.
Proxy use and redirects are disabled; service-account/token metadata is never
requested.

## Policy

Start from
`config/gateway_readonly_attestation_policy.example.json`, replace the
placeholder reviewer information, and independently verify the public-key
SHA-256 before installation.

The example uses an eight-hour maximum attestation age. The verifier refuses
policy windows longer than 24 hours.

The example file in Git is **not** trusted policy. Production trust begins only
after an administrator installs the reviewed file at the fixed `/etc/aurora`
path with root ownership.

## Artifact

Start from
`docs/gateway_readonly_attestation_artifact.example.json`.

The example is deliberately invalid and must never be treated as evidence.

The reviewer should sign the canonical payload off the trading VPS. AURORA uses
`/usr/bin/openssl` for Ed25519 verification only; the private signing key is
never required by AURORA.

## Verification

On the VPS:

```bash
cd ~/aurora/news-stock-scanner
python scripts/verify_gateway_readonly_attestation.py
```

A verified result returns exit code 0 and:

```text
status = VERIFIED
gateway_read_only_configuration_independently_attested = true
```

Every other result returns exit code 2 and keeps the attestation false.

The normal G2 probe calls the same fixed-path verifier automatically. The
G0-G3 readiness summary and G0-G4 completion gate independently call the same
verifier again and require the cryptographic attestation digest to match the
attestation embedded in G2 evidence. Editing G2 JSON, changing its boolean
flags, or recomputing downstream proof hashes cannot substitute for the signed
fixed-path artifact.

If the broker diagnostics are otherwise healthy but the signed attestation is
absent or invalid, G2 remains:

```text
readiness = NOT_READY
next_milestone = INDEPENDENT_GATEWAY_READ_ONLY_ATTESTATION
paper_order_submission_allowed = false
live_execution_allowed = false
```

## Revocation and renewal

Replacing or removing the root-owned reviewer public key/policy immediately
invalidates future verification. Expired artifacts are rejected. A new Git
commit also invalidates the previous artifact because the signed Git SHA must
match the deployed clean checkout.

After any IB Gateway/TWS configuration change, Gateway reinstall, reviewer-key
rotation, or security incident, obtain a new independent attestation before
continuing.

G7.5 validates evidence only. It does not authorize a Paper broker order,
automatic promotion, or real-money trading.


## G7.10 signed G0/G1 proof binding

The V3 signed attestation adds `g0_runtime_proof_sha256`. The independent
reviewer must copy this value from the sanitized reviewer handoff request into
the artifact before signing. The field is part of the canonical Ed25519-signed
payload.

At verification time AURORA reads only the fixed
`runtime/gcp/latest.json` path under the deployed repository, parses it with
duplicate-key rejection, computes the same canonical SHA-256, and requires an
exact match with the signed V3 field. A missing, malformed, stale/replaced or
different G0/G1 proof therefore blocks the Gateway attestation.

This does not authorize Paper or LIVE orders.
