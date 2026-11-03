# AURORA G8.24 — Signed Independent Offline Materializer Attestation

G8.24 verifies a separately signed Ed25519 reviewer attestation for the exact
G8.22 offline order-request materializer package handed off by G8.23.

A successful verification advances only the review state. It does not enable a
broker connection, IBKR Order object creation, Paper submission, LIVE execution,
automatic promotion or real-money trading.

## Bound evidence

The verifier binds the signed artifact to:

- the exact G8.23 canonical review request;
- the exact G8.22 design contract;
- the exact tracked materializer source;
- the exact tracked bounded CLI source;
- reviewer identity and public-key fingerprint;
- reviewer evidence digest and validity window.

It independently re-runs the G8.23 source/design safety policy and rejects
repository dirtiness, signature/key mismatch, expiry, schema expansion, source
or design tamper, and any permission regression.

## Fixed trust roots

```text
/etc/aurora/offline-materializer-review-policy.json
/etc/aurora/offline-materializer-reviewer-ed25519.pem
/var/lib/aurora/offline-materializer-review-attestation/latest.json
```

The verifier never contains a private-key signing path.

## Runtime output

```text
runtime/aurora_g6_offline_materializer_attestation/latest.json
```

## Next gate

```text
IBKR_ORDER_OBJECT_MATERIALIZER_DESIGN_REQUIRED
```

This next gate remains non-executable by default.
