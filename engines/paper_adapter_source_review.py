"""G8.13 static source-policy gate for the review-only Paper adapter.

The candidate adapter source is parsed with Python AST and is never imported or
executed. A valid result only prepares an exact, hard-disabled source artifact
for independent human review. It never enables broker connectivity or orders.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import UUID

from engines.paper_connector_review_prerequisite import (
    ENGINE_VERSION as PREREQUISITE_ENGINE_VERSION,
    EXPECTED_G6_RUNTIME_CHECKS,
)


ENGINE_VERSION = "AURORA G8.13 Paper Adapter Source Review"
POLICY_VERSION = "AURORA_G8_13_ADAPTER_SOURCE_POLICY_V2"
SKELETON_VERSION = "AURORA_G8_13_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1"
EXPECTED_CLASS = "IBKRPaperAdapterReviewSkeleton"
DEFAULT_MAX_PREREQUISITE_AGE_SECONDS = 300

EXPECTED_G8_12_CHECKS = set(
    EXPECTED_G6_RUNTIME_CHECKS
)

_PERMISSION_FLAGS = (
    "implementation_allowed",
    "connection_allowed",
    "broker_request_materialization_allowed",
    "broker_order_object_allowed",
    "automatic_retry_allowed",
    "automatic_cancel_allowed",
    "automatic_modify_allowed",
    "broker_submission_allowed",
    "paper_order_submission_allowed",
    "live_execution_allowed",
    "automatic_promotion_allowed",
    "real_money_trading_allowed",
)

REQUIRED_METHODS = {
    "__init__",
    "describe",
    "connect",
    "materialize_order_request",
    "submit_order",
    "cancel_order",
    "modify_order",
}

BLOCKED_METHODS = {
    "connect",
    "materialize_order_request",
    "submit_order",
    "cancel_order",
    "modify_order",
}

EXPECTED_BLOCK_REASONS = {
    "connect": "G8_13_CONNECTION_DISABLED",
    "materialize_order_request": "G8_13_REQUEST_MATERIALIZATION_DISABLED",
    "submit_order": "G8_13_ORDER_SUBMISSION_DISABLED",
    "cancel_order": "G8_13_ORDER_CANCELLATION_DISABLED",
    "modify_order": "G8_13_ORDER_MODIFICATION_DISABLED",
}

SAFE_DESCRIBE_VALUES = {
    "review_only": True,
    "mode": "PAPER",
    "host": "127.0.0.1",
    "port": 4002,
    "asset_type": "STK",
    "order_type": "LMT",
    "time_in_force": "DAY",
    "market_order_allowed": False,
    "short_selling_allowed": False,
    "fractional_quantity_allowed": False,
    "credentials_allowed": False,
    "raw_account_id_allowed": False,
    "implementation_allowed": False,
    "connection_allowed": False,
    "broker_request_materialization_allowed": False,
    "broker_order_object_allowed": False,
    "automatic_retry_allowed": False,
    "automatic_cancel_allowed": False,
    "automatic_modify_allowed": False,
    "broker_submission_allowed": False,
    "paper_order_submission_allowed": False,
    "live_execution_allowed": False,
    "automatic_promotion_allowed": False,
    "real_money_trading_allowed": False,
}

FORBIDDEN_ATTRIBUTE_NAMES = {
    "placeOrder",
    "cancelOrder",
    "reqGlobalCancel",
    "exerciseOptions",
    "replaceFA",
    "reqAutoOpenOrders",
    "reqOpenOrders",
    "reqAllOpenOrders",
    "reqMktData",
    "reqTickByTickData",
    "disconnect",
}

FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
}

FORBIDDEN_DYNAMIC_NODES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.Lambda,
    ast.Yield,
    ast.YieldFrom,
    ast.NamedExpr,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
)


def _canonical_digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _source_digest(source_text):
    if not isinstance(source_text, str):
        return None
    return hashlib.sha256(
        source_text.encode("utf-8")
    ).hexdigest()


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _sha256(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 64
        or any(
            character not in "0123456789abcdef"
            for character in text
        )
    ):
        return None
    return text


def _git_sha(value):
    text = str(value or "").strip().lower()
    if (
        len(text) != 40
        or any(
            character not in "0123456789abcdef"
            for character in text
        )
    ):
        return None
    return text


def _instance_id(value):
    text = str(value or "").strip()
    if (
        not text.isdigit()
        or not 6 <= len(text) <= 30
        or text[0] == "0"
    ):
        return None
    return text


def _utc_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _fingerprints(value):
    if not isinstance(value, list) or len(value) != 1:
        return None
    item = value[0]
    if (
        not isinstance(item, str)
        or len(item) != 15
        or not item.startswith("IBKR-")
        or any(
            character not in "0123456789ABCDEF"
            for character in item[5:]
        )
    ):
        return None
    return [item]


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in _PERMISSION_FLAGS
        )
    )


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "source_policy_validated": False,
        "independent_source_review_required": True,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "REPAIR_ADAPTER_SOURCE_REVIEW_INPUT",
    }


def _validate_prerequisite(
    prerequisite,
    current_git_sha,
    repository_clean,
    now,
    max_age_seconds,
):
    if not isinstance(prerequisite, dict):
        return None, "G8_12_PREREQUISITE_INVALID"

    if (
        type(max_age_seconds) is not int
        or not 60 <= max_age_seconds <= 900
    ):
        return None, "PREREQUISITE_MAX_AGE_INVALID"

    checks = prerequisite.get("checks")
    checks_valid = (
        isinstance(checks, dict)
        and set(checks) == EXPECTED_G8_12_CHECKS
        and all(
            checks.get(name) is True
            for name in EXPECTED_G8_12_CHECKS
        )
    )

    git_sha = _git_sha(
        prerequisite.get("git_sha")
    )
    current_git_sha = _git_sha(
        current_git_sha
    )
    generated_at = _utc_datetime(
        prerequisite.get("generated_at")
    )
    age_seconds = (
        (now - generated_at).total_seconds()
        if generated_at is not None
        else None
    )

    evidence_age = prerequisite.get(
        "g2_evidence_age_seconds"
    )
    snapshot_age = prerequisite.get(
        "g2_snapshot_age_seconds"
    )
    snapshot_completion_age = prerequisite.get(
        "g2_snapshot_completion_age_seconds"
    )
    ages_valid = (
        isinstance(evidence_age, (int, float))
        and not isinstance(evidence_age, bool)
        and math.isfinite(float(evidence_age))
        and 0 <= float(evidence_age) <= 300
        and isinstance(snapshot_age, (int, float))
        and not isinstance(snapshot_age, bool)
        and math.isfinite(float(snapshot_age))
        and 0 <= float(snapshot_age) <= 300
        and isinstance(snapshot_completion_age, (int, float))
        and not isinstance(snapshot_completion_age, bool)
        and math.isfinite(float(snapshot_completion_age))
        and 0 <= float(snapshot_completion_age) <= 300
        and float(snapshot_completion_age) <= float(snapshot_age)
    )

    fingerprints = _fingerprints(
        prerequisite.get(
            "paper_account_fingerprints"
        )
    )

    valid = (
        prerequisite.get("engine")
        == PREREQUISITE_ENGINE_VERSION
        and prerequisite.get("status")
        == "READY_FOR_PAPER_CONNECTOR_SOURCE_REVIEW"
        and prerequisite.get("next_gate")
        == "REBASE_AND_REVIEW_BROKER_ADAPTER_SOURCE_AGAINST_G8_12"
        and prerequisite.get("g2_probe_stage")
        == "POST_REVIEW_PROBE"
        and prerequisite.get(
            "independent_source_review_required"
        )
        is True
        and _permissions_false(prerequisite)
        and checks_valid
        and _uuid4(
            prerequisite.get("authorization_id")
        )
        is not None
        and _uuid4(
            prerequisite.get("evidence_run_id")
        )
        is not None
        and _instance_id(
            prerequisite.get("gce_instance_id")
        )
        is not None
        and _sha256(
            prerequisite.get("g5_validation_sha256")
        )
        is not None
        and _sha256(
            prerequisite.get(
                "authorization_artifact_sha256"
            )
        )
        is not None
        and _sha256(
            prerequisite.get("g0_g1_proof_sha256")
        )
        is not None
        and _sha256(
            prerequisite.get(
                "g2_paper_read_only_proof_sha256"
            )
        )
        is not None
        and _sha256(
            prerequisite.get(
                "gateway_read_only_attestation_sha256"
            )
        )
        is not None
        and fingerprints is not None
        and ages_valid
        and git_sha is not None
        and current_git_sha is not None
        and git_sha == current_git_sha
        and repository_clean is True
        and age_seconds is not None
        and -2 <= age_seconds <= max_age_seconds
    )
    if not valid:
        return None, "G8_12_PREREQUISITE_NOT_READY_FOR_SOURCE_REVIEW"

    return {
        "prerequisite_sha256": _canonical_digest(
            prerequisite
        ),
        "generated_at": generated_at.isoformat(),
        "age_seconds": round(
            max(0.0, age_seconds),
            3,
        ),
        "git_sha": git_sha,
        "authorization_id": prerequisite.get(
            "authorization_id"
        ),
        "evidence_run_id": prerequisite.get(
            "evidence_run_id"
        ),
        "g2_probe_stage": prerequisite.get(
            "g2_probe_stage"
        ),
        "gce_instance_id": prerequisite.get(
            "gce_instance_id"
        ),
        "g0_g1_proof_sha256": prerequisite.get(
            "g0_g1_proof_sha256"
        ),
        "g2_paper_read_only_proof_sha256": prerequisite.get(
            "g2_paper_read_only_proof_sha256"
        ),
        "gateway_read_only_attestation_sha256": prerequisite.get(
            "gateway_read_only_attestation_sha256"
        ),
        "paper_account_fingerprints": fingerprints,
    }, None


def _strip_docstring(body):
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _arguments_are_plain(arguments):
    values = (
        list(arguments.posonlyargs)
        + list(arguments.args)
        + list(arguments.kwonlyargs)
    )
    return (
        not arguments.defaults
        and not any(
            item is not None
            for item in arguments.kw_defaults
        )
        and all(
            arg.annotation is None
            for arg in values
        )
        and (
            arguments.vararg is None
            or arguments.vararg.annotation is None
        )
        and (
            arguments.kwarg is None
            or arguments.kwarg.annotation is None
        )
    )


def _validate_signature(method, name):
    args = method.args
    if (
        method.decorator_list
        or method.returns is not None
        or method.type_comment is not None
        or not _arguments_are_plain(args)
        or args.posonlyargs
        or args.kwonlyargs
    ):
        return False

    positional = [
        item.arg
        for item in args.args
    ]

    if name == "__init__":
        return (
            positional
            == [
                "self",
                "runtime_prerequisite_sha256",
            ]
            and args.vararg is None
            and args.kwarg is None
        )

    if name == "describe":
        return (
            positional == ["self"]
            and args.vararg is None
            and args.kwarg is None
        )

    return (
        positional == ["self"]
        and args.vararg is not None
        and args.vararg.arg == "args"
        and args.kwarg is not None
        and args.kwarg.arg == "kwargs"
    )


def _literal_dict(node):
    if not isinstance(node, ast.Dict):
        return None
    result = {}
    for key_node, value_node in zip(
        node.keys,
        node.values,
    ):
        if (
            not isinstance(key_node, ast.Constant)
            or not isinstance(key_node.value, str)
            or key_node.value in result
        ):
            return None

        if (
            isinstance(value_node, ast.Constant)
            and isinstance(
                value_node.value,
                (str, int, bool),
            )
        ):
            result[key_node.value] = value_node.value
            continue

        if (
            isinstance(value_node, ast.Name)
            and value_node.id == "SKELETON_VERSION"
        ):
            result[key_node.value] = SKELETON_VERSION
            continue

        return None
    return result


def _validate_init(method):
    body = _strip_docstring(method.body)
    if (
        len(body) != 1
        or not isinstance(body[0], ast.Assign)
    ):
        return False
    assignment = body[0]
    if len(assignment.targets) != 1:
        return False
    target = assignment.targets[0]
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and target.attr == "_runtime_prerequisite_sha256"
        and isinstance(assignment.value, ast.Name)
        and assignment.value.id == "runtime_prerequisite_sha256"
    )


def _validate_describe(method):
    body = _strip_docstring(method.body)
    if (
        len(body) != 1
        or not isinstance(body[0], ast.Return)
    ):
        return False
    values = _literal_dict(
        body[0].value
    )
    if values is None:
        return False
    return values == {
        "skeleton_version": SKELETON_VERSION,
        **SAFE_DESCRIBE_VALUES,
    }


def _validate_blocked_method(method, name):
    body = _strip_docstring(method.body)
    if (
        len(body) != 1
        or not isinstance(body[0], ast.Raise)
    ):
        return False
    call = body[0].exc
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "RuntimeError"
        and len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value
        == EXPECTED_BLOCK_REASONS[name]
    )


def _validate_ast(source_text):
    try:
        tree = ast.parse(
            source_text,
            mode="exec",
        )
    except (SyntaxError, ValueError, TypeError):
        return False, "SOURCE_SYNTAX_INVALID"

    top_level = _strip_docstring(
        tree.body
    )
    assignments = {}
    classes = []

    for node in top_level:
        if isinstance(
            node,
            (ast.Import, ast.ImportFrom),
        ):
            return False, "SOURCE_IMPORTS_NOT_ALLOWED"

        if isinstance(node, ast.Assign):
            if (
                len(node.targets) != 1
                or not isinstance(
                    node.targets[0],
                    ast.Name,
                )
                or not isinstance(
                    node.value,
                    ast.Constant,
                )
            ):
                return False, "SOURCE_TOP_LEVEL_ASSIGNMENT_INVALID"
            assignments[
                node.targets[0].id
            ] = node.value.value
            continue

        if isinstance(node, ast.ClassDef):
            classes.append(node)
            continue

        return False, "SOURCE_TOP_LEVEL_EXECUTION_NOT_ALLOWED"

    if assignments != {
        "SKELETON_VERSION": SKELETON_VERSION
    }:
        return False, "SOURCE_SKELETON_VERSION_INVALID"

    if (
        len(classes) != 1
        or classes[0].name != EXPECTED_CLASS
    ):
        return False, "SOURCE_ADAPTER_CLASS_INVALID"

    adapter = classes[0]
    if (
        adapter.bases
        or adapter.keywords
        or adapter.decorator_list
    ):
        return False, "SOURCE_ADAPTER_INHERITANCE_OR_DECORATOR_NOT_ALLOWED"

    methods = {}
    for node in _strip_docstring(
        adapter.body
    ):
        if not isinstance(
            node,
            ast.FunctionDef,
        ):
            return False, "SOURCE_CLASS_STATEMENT_INVALID"
        if node.name in methods:
            return False, "SOURCE_DUPLICATE_METHOD"
        methods[node.name] = node

    if set(methods) != REQUIRED_METHODS:
        return False, "SOURCE_METHOD_SURFACE_INVALID"

    for name, method in methods.items():
        if not _validate_signature(
            method,
            name,
        ):
            return False, "SOURCE_METHOD_SIGNATURE_INVALID"

    if not _validate_init(
        methods["__init__"]
    ):
        return False, "SOURCE_INIT_INVALID"

    if not _validate_describe(
        methods["describe"]
    ):
        return False, "SOURCE_DESCRIBE_INVALID"

    for name in BLOCKED_METHODS:
        if not _validate_blocked_method(
            methods[name],
            name,
        ):
            return (
                False,
                f"SOURCE_{name.upper()}_NOT_HARD_DISABLED",
            )

    for node in ast.walk(tree):
        if isinstance(
            node,
            FORBIDDEN_DYNAMIC_NODES,
        ):
            return False, "SOURCE_DYNAMIC_CONTROL_FLOW_NOT_ALLOWED"

        if (
            isinstance(node, ast.Attribute)
            and node.attr
            in FORBIDDEN_ATTRIBUTE_NAMES
        ):
            return False, "FORBIDDEN_BROKER_ATTRIBUTE"

        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id
                in FORBIDDEN_CALL_NAMES
            ):
                return False, "FORBIDDEN_DYNAMIC_CALL"
            if not (
                isinstance(node.func, ast.Name)
                and node.func.id == "RuntimeError"
            ):
                return False, "SOURCE_UNEXPECTED_CALL"

    return True, None


def evaluate_adapter_source_review(
    prerequisite,
    source_text,
    current_git_sha,
    repository_clean,
    now=None,
    max_prerequisite_age_seconds=(
        DEFAULT_MAX_PREREQUISITE_AGE_SECONDS
    ),
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    prerequisite_summary, failure = (
        _validate_prerequisite(
            prerequisite,
            current_git_sha,
            repository_clean,
            now,
            max_prerequisite_age_seconds,
        )
    )
    if failure:
        return _blocked(
            failure
        )

    if (
        not isinstance(source_text, str)
        or not source_text.strip()
        or "\x00" in source_text
        or len(
            source_text.encode("utf-8")
        )
        > 100_000
    ):
        return _blocked(
            "SOURCE_TEXT_INVALID"
        )

    source_valid, source_failure = (
        _validate_ast(
            source_text
        )
    )
    if not source_valid:
        return _blocked(
            source_failure
        )

    source_sha256 = _source_digest(
        source_text
    )
    prerequisite_sha256 = (
        prerequisite_summary[
            "prerequisite_sha256"
        ]
    )
    if (
        source_sha256 is None
        or prerequisite_sha256 is None
    ):
        return _blocked(
            "SOURCE_OR_PREREQUISITE_DIGEST_UNAVAILABLE"
        )

    policy_payload = {
        "policy_version": POLICY_VERSION,
        "runtime_prerequisite_sha256": (
            prerequisite_sha256
        ),
        "source_sha256": source_sha256,
        "skeleton_version": SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "git_sha": prerequisite_summary[
            "git_sha"
        ],
        "authorization_id": prerequisite_summary[
            "authorization_id"
        ],
        "evidence_run_id": prerequisite_summary[
            "evidence_run_id"
        ],
        "g2_probe_stage": prerequisite_summary[
            "g2_probe_stage"
        ],
        "gce_instance_id": prerequisite_summary[
            "gce_instance_id"
        ],
        "g0_g1_proof_sha256": prerequisite_summary[
            "g0_g1_proof_sha256"
        ],
        "g2_paper_read_only_proof_sha256": prerequisite_summary[
            "g2_paper_read_only_proof_sha256"
        ],
        "gateway_read_only_attestation_sha256": (
            prerequisite_summary[
                "gateway_read_only_attestation_sha256"
            ]
        ),
        "paper_account_fingerprints": (
            prerequisite_summary[
                "paper_account_fingerprints"
            ]
        ),
    }
    source_policy_sha256 = _canonical_digest(
        policy_payload
    )
    if source_policy_sha256 is None:
        return _blocked(
            "SOURCE_POLICY_DIGEST_UNAVAILABLE"
        )

    return {
        "engine": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "generated_at": now.isoformat(),
        "status": "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE",
        "reason": "REVIEW_SKELETON_SOURCE_HARD_DISABLED",
        "source_policy_validated": True,
        **policy_payload,
        "source_policy_sha256": source_policy_sha256,
        "runtime_prerequisite_age_seconds": (
            prerequisite_summary[
                "age_seconds"
            ]
        ),
        "independent_source_review_required": True,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_request_materialization_allowed": False,
        "broker_order_object_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_promotion_allowed": False,
        "real_money_trading_allowed": False,
        "next_gate": "INDEPENDENT_ADAPTER_SOURCE_REVIEW_REQUIRED",
    }
