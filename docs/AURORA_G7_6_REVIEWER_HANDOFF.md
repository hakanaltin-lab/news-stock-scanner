# AURORA G7.6 — Operator / Independent Reviewer Handoff

G7.6 prepares the approved Paper VPS for a human review of the IB Gateway/TWS
**Read-Only API** setting. It does not create an attestation, does not sign
anything, and does not authorize a Paper or LIVE order.

## Purpose

After G7.5, AURORA accepts Read-Only attestation only from an independently
signed Ed25519 artifact. G7.6 gives the operator and reviewer a sanitized
handoff request that is cryptographically and operationally bound to the
reviewer trust root and deployed code, while keeping the final decision outside
AURORA.

Run on the approved VPS from the repository root:

```bash
python scripts/gateway_readonly_attestation_handoff.py
```

Exit code 0 means only:

```text
status = READY_FOR_INDEPENDENT_REVIEW
ready_for_independent_review = true
attestation_verified = false
gateway_read_only_configuration_independently_attested = false
```

It never means G2 is ready and never authorizes an order.

## What the preflight verifies

The preflight uses the same fixed production trust paths as G7.5 and refuses
environment or CLI path overrides. It requires:

- root-controlled reviewer policy and public-key files;
- the reviewer public-key fingerprint to match the policy;
- public-key material only — reviewer private-key material is rejected;
- policy instance exactly `aurora-trading-vps`;
- policy zone exactly `europe-west3-a`;
- policy project exactly `project-ce9773ef-6814-469c-92b`;
- policy immutable numeric GCE instance ID;
- runtime hostname matching the approved instance;
- live link-local GCE metadata matching project, instance name, zone and
  immutable instance ID;
- a valid current Git SHA;
- no tracked Git modifications;
- a fresh `runtime/gcp/latest.json` G0/G1 proof showing the approved project,
  `aurora-trading-vps`, `europe-west3-a`, the hardened VM/network contract,
  IAP SSH rule and public denial of ports 4002/5902;
- all G0/G1 order-permission flags still false;
- system OpenSSL available;
- a valid policy freshness window and clock-skew limit.

The output contains no broker account ID, balance, credential, service-account
token, or order authorization. The G0/G1 proof remains a preflight input, not Gateway Read-Only
evidence; the independent reviewer must still inspect the Gateway/TWS setting
directly. G7.8 additionally binds the handoff to the immutable GCE instance ID from the sanitized G0/G1 control-plane proof; this must match both root policy and live GCE metadata.

## Handoff request is deliberately not an attestation

The generated `handoff_request` uses a distinct schema:

```text
request_schema_version = 3
request_type = IBKR_GATEWAY_READ_ONLY_REVIEW_REQUEST_V3
operator_asserts_gateway_read_only = false
requires_human_gateway_configuration_review = true
signed_attestation_required = true
```

The G7.5 attestation verifier rejects this request even if someone attempts to
feed it back as an attestation. It has no `decision=ATTESTED`, no evidence
hash, and no reviewer signature.

## G7.11 / G8.2 / G8.3 runtime-bound unsigned reviewer package

After the G7.10 handoff reports `READY_FOR_INDEPENDENT_REVIEW`, first run the
G2 diagnostic on the approved VPS in `READ_ONLY` mode. Before an independent
attestation exists, the probe is expected to return a non-zero exit code while
still writing sanitized runtime evidence when every non-attestation diagnostic
check is healthy.

The pre-review evidence must show:

- a real connected IBKR Paper session on `127.0.0.1:4002`;
- the official TWS API available;
- exactly one allowlisted Paper account represented only by its fingerprint;
- all managed-account, account-summary, position and open-order reads complete;
- G8.1 broker-mutation hard blocks active;
- non-binding `reqAllOpenOrders()` observation;
- a non-zero API client ID;
- `diagnostic_read_only_ready=true`;
- the independent Gateway Read-Only attestation as the **only** required
  failure;
- the exact deployed Git SHA matching the reviewer handoff;
- live GCE metadata matching the same approved project, VM name, zone and
  immutable instance ID as the handoff;
- the exact same canonical G0/G1 runtime proof digest used by the handoff;
- evidence no more than five minutes old.

Then run:

```bash
python scripts/gateway_review_package.py
```

The CLI now prints a sanitized
`IBKR_GATEWAY_READ_ONLY_REVIEW_PACKAGE_V3`. It cryptographically digests the
fresh G2 diagnostic proof and includes only a sanitized diagnostic summary,
the exact V3 handoff request, and an `unsigned_artifact_template` with
deployment identity and the signed-target `g0_runtime_proof_sha256`
prefilled. The full G2 proof is not copied into the reviewer package.

The legacy V1 handoff-only builder remains available for offline compatibility
testing but is no longer the installed CLI path.

AURORA deliberately leaves the security-sensitive reviewer fields unset:

- `attestation_id`;
- `decision` remains `REVIEW_REQUIRED`;
- `captured_at_utc` and `expires_at_utc`;
- `read_only_api_enabled`;
- reviewer evidence SHA-256;
- `signature_b64`.

Even if the unsigned template is fed directly to the production verifier and a
caller falsely claims the signature is valid, it remains BLOCKED. The builder
does not write files, invoke OpenSSL, access a private key, or authorize any
order.

## Independent reviewer procedure

The independent reviewer should use the handoff request and unsigned review
package only to identify the deployment being reviewed. The reviewer then independently verifies the
Gateway/TWS API configuration on the approved VPS, including the Read-Only API
setting, Paper mode, loopback API endpoint and port 4002.

The reviewer captures sanitized evidence, computes its SHA-256, completes the
V3 artifact only after the independent review, preserves the exact prefilled
Git SHA/VPS/G0 proof digest, and signs it **off the trading VPS** with the
reviewer private Ed25519 key.

Never copy the reviewer private key to the AURORA VPS, repository, GitHub,
shell history, runtime files, or ChatGPT conversation.

## Operator installation after review

Only the signed artifact is returned to the operator. The operator installs it
at:

```text
/var/lib/aurora/gateway-readonly-attestation/latest.json
```

The reviewer public key and reviewed policy remain at their G7.5 fixed
root-controlled paths.

Then run:

```bash
python scripts/verify_gateway_readonly_attestation.py
```

Only `status=VERIFIED` from that verifier can satisfy the cryptographic
attestation gate. The G2 probe, G0-G3 readiness bundle and G0-G4 completion
gate reverify the same artifact independently.

## Safety boundary

G7.6 is administrative readiness only. Throughout this workflow:

- broker submission remains disabled;
- Paper order submission remains disabled;
- LIVE execution remains disabled;
- automatic promotion remains disabled;
- real-money trading remains disabled.

No order should be placed merely to prove Read-Only configuration.


## G7.10 handoff-to-signature binding

The V3 handoff includes the canonical `g0_runtime_proof_sha256`. The reviewer
must transfer that exact digest into the V3 Gateway Read-Only attestation
artifact before signing. The production verifier independently recomputes the
digest from the fixed deployed G0/G1 proof path and rejects any mismatch.


## G7.11 safety invariant

The unsigned review package is convenience data only. It is not an attestation,
cannot satisfy the V3 verifier, and cannot change any AURORA execution
permission. The independent reviewer remains the only party that can turn a
reviewed V3 payload into a valid signed artifact.


## G7.12 fail-closed workflow status

Run:

```bash
python scripts/gateway_review_workflow_status.py
```

This command is diagnostic only and prints one sanitized workflow stage plus one
next safe action. It never writes policy, reviewer artifacts or runtime proofs,
and it never enables Paper or LIVE execution.

Expected progression:

```text
RUNTIME_IDENTITY
-> TRUST_AND_HANDOFF
-> FRESH_G2_DIAGNOSTIC
-> REVIEW_PACKAGE_V3
-> INDEPENDENT_REVIEW
-> SIGNED_ATTESTATION_VERIFIED
```

If the runtime-bound package is not ready, the workflow returns
`RUN_FRESH_G2_DIAGNOSTIC_PRE_REVIEW`. A valid signed attestation remains
authoritative even if the five-minute pre-review G2 diagnostic window expires
during the human review.

At the final stage, the next action is only
`RUN_G2_PAPER_READ_ONLY_PROBE`; order submission remains disabled. Missing or
true execution-permission flags in any upstream preparation result force
`SAFETY_INVARIANT` and stop progression.


G7.12 CLI exit semantics are fail-closed: exit code `0` is returned only when
the signed independent attestation is VERIFIED and the next action is the G2
Paper read-only probe. Waiting for review and every blocked state return a
non-zero exit code, so shell automation cannot treat pending human review as a
passed gate.

## G8.3 deployment provenance binding

G8.3 prevents a fresh G2 diagnostic generated on a different VM or against a
different G0/G1 network proof from being reused for this deployment. The G2
probe records only sanitized provenance:

- approved GCP project ID;
- approved VM name and zone;
- immutable numeric GCE instance ID read from the link-local metadata service;
- canonical SHA-256 of the fixed `runtime/gcp/latest.json` proof.

The reviewer-package builder requires those values to match the G7.10 handoff
exactly. A cross-VM instance ID, changed G0/G1 proof digest, unverified metadata
identity, malformed provenance, or any execution-permission regression blocks
the package before independent review. This provenance binding is defense in
depth; it does not replace the independent human inspection of the Gateway/TWS
Read-Only setting and does not authorize any order.

