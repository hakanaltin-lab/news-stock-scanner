"""G8.23 non-attesting handoff for independent offline materializer review."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json

from engines.paper_adapter_implementation_candidate_review import PERMISSION_FLAGS


ENGINE_VERSION = "AURORA G8.23 Offline Materializer Review Handoff"
REQUEST_TYPE = "AURORA_OFFLINE_ORDER_REQUEST_MATERIALIZER_REVIEW_REQUEST_V1"
ATTESTATION_TYPE = "AURORA_OFFLINE_ORDER_REQUEST_MATERIALIZER_REVIEW_V1"
SIGNATURE_ALGORITHM = "ED25519"
NEXT_GATE = "SIGNED_INDEPENDENT_OFFLINE_ORDER_REQUEST_MATERIALIZER_ATTESTATION_REQUIRED"

DESIGN_FIELDS = {
    "schema_version",
    "design_id",
    "candidate_attestation_required",
    "candidate_attestation_next_gate",
    "accepted_order_type",
    "accepted_time_in_force",
    "accepted_sides",
    "symbol_pattern",
    "quantity_min",
    "quantity_max",
    "limit_price_scale_max",
    "outside_rth_allowed",
    "fractional_quantity_allowed",
    "market_order_allowed",
    "sell_requires_reduce_only",
    "sell_requires_position_coverage",
    "raw_account_id_allowed",
    "credentials_allowed",
    "ibkr_import_allowed",
    "network_allowed",
    *PERMISSION_FLAGS,
    "next_gate",
}

FORBIDDEN_IMPORT_PREFIXES = (
    "ibapi",
    "ib_insync",
    "socket",
    "requests",
    "urllib",
    "http.client",
    "websocket",
)
FORBIDDEN_CALL_NAMES = {
    "placeOrder",
    "cancelOrder",
    "reqGlobalCancel",
    "submit_order",
    "connect_broker",
    "createOrder",
    "urlopen",
}
REQUIRED_MATERIALIZER_MARKER_COUNTS = {
    "broker_request_materialized": 3,
    "broker_order_object_created": 3,
    "network_accessed": 2,
    "transmit": 3,
}


def canonical_json_sha256(payload):
    if not isinstance(payload, dict):
        return None
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(raw).hexdigest()


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(name in payload and payload.get(name) is False for name in PERMISSION_FLAGS)
    )


def _validate_design(design):
    return (
        isinstance(design, dict)
        and set(design) == DESIGN_FIELDS
        and design.get("schema_version") == 1
        and design.get("design_id")
        == "AURORA_G8_22_OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_V1"
        and design.get("candidate_attestation_required") is True
        and design.get("candidate_attestation_next_gate")
        == "OFFLINE_ORDER_REQUEST_MATERIALIZER_DESIGN_REQUIRED"
        and design.get("accepted_order_type") == "LMT"
        and design.get("accepted_time_in_force") == "DAY"
        and design.get("accepted_sides") == ["BUY", "SELL"]
        and design.get("symbol_pattern") == "^[A-Z][A-Z0-9.-]{0,11}$"
        and design.get("quantity_min") == 1
        and design.get("quantity_max") == 100000
        and design.get("limit_price_scale_max") == 4
        and design.get("outside_rth_allowed") is False
        and design.get("fractional_quantity_allowed") is False
        and design.get("market_order_allowed") is False
        and design.get("sell_requires_reduce_only") is True
        and design.get("sell_requires_position_coverage") is True
        and design.get("raw_account_id_allowed") is False
        and design.get("credentials_allowed") is False
        and design.get("ibkr_import_allowed") is False
        and design.get("network_allowed") is False
        and _permissions_false(design)
        and design.get("next_gate")
        == "INDEPENDENT_OFFLINE_ORDER_REQUEST_MATERIALIZER_REVIEW_REQUIRED"
    )


def _import_names(tree):
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.append(node.module or "")
    return values


def _call_names(tree):
    values = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            values.append(func.id)
        elif isinstance(func, ast.Attribute):
            values.append(func.attr)
    return values


def _offline_safety_markers_valid(tree):
    observed = {
        name: []
        for name in REQUIRED_MATERIALIZER_MARKER_COUNTS
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value in observed
            ):
                observed[key.value].append(value)

    return all(
        len(observed[name]) == expected_count
        and all(
            isinstance(value, ast.Constant)
            and value.value is False
            for value in observed[name]
        )
        for name, expected_count
        in REQUIRED_MATERIALIZER_MARKER_COUNTS.items()
    )


def _has_unique_sync_entrypoint(tree, name):
    definitions = [
        node
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == name
    ]
    return (
        len(definitions) == 1
        and isinstance(definitions[0], ast.FunctionDef)
    )


def _validate_source(source, *, materializer):
    if not isinstance(source, str) or not source.strip():
        return False, "SOURCE_UNAVAILABLE"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, "SOURCE_SYNTAX_INVALID"

    imports = _import_names(tree)
    if any(
        name == prefix or name.startswith(prefix + ".")
        for name in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    ):
        return False, "BROKER_OR_NETWORK_IMPORT_FORBIDDEN"

    calls = set(_call_names(tree))
    if calls.intersection(FORBIDDEN_CALL_NAMES):
        return False, "BROKER_OR_NETWORK_CALL_FORBIDDEN"

    lowered = source.lower()
    if "private_key" in lowered or "signature_b64 =" in lowered:
        return False, "SIGNING_PATH_FORBIDDEN"

    if materializer:
        if not _has_unique_sync_entrypoint(
            tree,
            "materialize_offline_order_request",
        ):
            return False, "MATERIALIZER_ENTRYPOINT_MISSING"
        if not _offline_safety_markers_valid(tree):
            return False, "OFFLINE_SAFETY_MARKER_MISSING"
    else:
        if not _has_unique_sync_entrypoint(
            tree,
            "build_installed_offline_request",
        ):
            return False, "CLI_ENTRYPOINT_MISSING"

    return True, None


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "status": "BLOCKED",
        "reason": reason,
        "ready_for_independent_materializer_review": False,
        "design_revalidated": False,
        "materializer_source_revalidated": False,
        "cli_source_revalidated": False,
        "operator_asserts_materializer_safe": False,
        "design_sha256": None,
        "materializer_source_sha256": None,
        "cli_source_sha256": None,
        "review_request_sha256": None,
        "review_request": None,
        "unsigned_attestation_template": None,
        "independent_materializer_review_required": True,
        "signed_materializer_attestation_required": True,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": "REPAIR_OFFLINE_MATERIALIZER_REVIEW_HANDOFF",
    }


def evaluate_materializer_review_handoff(
    design,
    materializer_source,
    cli_source,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime) and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not _validate_design(design):
        return _blocked("MATERIALIZER_DESIGN_INVALID")

    materializer_ok, materializer_reason = _validate_source(
        materializer_source,
        materializer=True,
    )
    if not materializer_ok:
        return _blocked(materializer_reason or "MATERIALIZER_SOURCE_INVALID")

    cli_ok, cli_reason = _validate_source(cli_source, materializer=False)
    if not cli_ok:
        return _blocked(cli_reason or "MATERIALIZER_CLI_SOURCE_INVALID")

    design_sha256 = canonical_json_sha256(design)
    materializer_source_sha256 = hashlib.sha256(
        materializer_source.encode("utf-8")
    ).hexdigest()
    cli_source_sha256 = hashlib.sha256(cli_source.encode("utf-8")).hexdigest()
    if not design_sha256:
        return _blocked("MATERIALIZER_DESIGN_DIGEST_UNAVAILABLE")

    request = {
        "request_schema_version": 1,
        "request_type": REQUEST_TYPE,
        "requested_control": ATTESTATION_TYPE,
        "generated_at_utc": now.isoformat(),
        "design_sha256": design_sha256,
        "materializer_source_sha256": materializer_source_sha256,
        "cli_source_sha256": cli_source_sha256,
        "operator_asserts_materializer_safe": False,
        "requires_human_materializer_review": True,
        "signed_materializer_attestation_required": True,
        **{name: False for name in PERMISSION_FLAGS},
    }
    review_request_sha256 = canonical_json_sha256(request)
    if not review_request_sha256:
        return _blocked("MATERIALIZER_REVIEW_REQUEST_DIGEST_UNAVAILABLE")

    template = {
        "schema_version": 1,
        "attestation_type": ATTESTATION_TYPE,
        "materializer_review_id": None,
        "decision": "REVIEW_REQUIRED",
        "reviewer_id": None,
        "captured_at_utc": None,
        "expires_at_utc": None,
        "review_request_sha256": review_request_sha256,
        "design_sha256": design_sha256,
        "materializer_source_sha256": materializer_source_sha256,
        "cli_source_sha256": cli_source_sha256,
        "reviewer_confirms_offline_only": None,
        "reviewer_confirms_no_broker_imports": None,
        "reviewer_confirms_no_network_path": None,
        "reviewer_confirms_fail_closed_intent_schema": None,
        "reviewer_evidence_sha256": None,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_b64": None,
    }

    return {
        "engine": ENGINE_VERSION,
        "request_type": REQUEST_TYPE,
        "status": "READY_FOR_INDEPENDENT_OFFLINE_MATERIALIZER_REVIEW",
        "reason": "HUMAN_OFFLINE_MATERIALIZER_REVIEW_REQUIRED",
        "ready_for_independent_materializer_review": True,
        "design_revalidated": True,
        "materializer_source_revalidated": True,
        "cli_source_revalidated": True,
        "operator_asserts_materializer_safe": False,
        "design_sha256": design_sha256,
        "materializer_source_sha256": materializer_source_sha256,
        "cli_source_sha256": cli_source_sha256,
        "review_request_sha256": review_request_sha256,
        "review_request": request,
        "unsigned_attestation_template": template,
        "reviewer_must_set": [
            "materializer_review_id",
            "decision=ATTESTED only after independent review",
            "reviewer_id",
            "captured_at_utc",
            "expires_at_utc",
            "reviewer_confirms_offline_only=true",
            "reviewer_confirms_no_broker_imports=true",
            "reviewer_confirms_no_network_path=true",
            "reviewer_confirms_fail_closed_intent_schema=true",
            "reviewer_evidence_sha256",
            "signature_b64",
        ],
        "independent_materializer_review_required": True,
        "signed_materializer_attestation_required": True,
        **{name: False for name in PERMISSION_FLAGS},
        "next_gate": NEXT_GATE,
    }
