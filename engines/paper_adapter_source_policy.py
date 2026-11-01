"""G6.20 static source-policy gate for the review-only Paper adapter.

The policy parses source with Python AST and rejects broker/network imports,
broker mutation calls, executable top-level statements, expanded adapter
interfaces, or any broker-facing method that is not a single hard-disabled
RuntimeError. It never executes the candidate source.
"""

import ast
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from engines.paper_adapter_implementation_review import CONTRACT_VERSION


POLICY_VERSION = "AURORA_G6_20_ADAPTER_SOURCE_POLICY_V1"
EXPECTED_CLASS = "IBKRPaperAdapterReviewSkeleton"
EXPECTED_SKELETON_VERSION = (
    "AURORA_G6_20_IBKR_PAPER_ADAPTER_REVIEW_SKELETON_V1"
)
REQUIRED_METHODS = frozenset((
    "__init__",
    "describe",
    "connect",
    "materialize_order_request",
    "submit_order",
    "cancel_order",
    "modify_order",
))
BLOCKED_METHODS = frozenset((
    "connect",
    "materialize_order_request",
    "submit_order",
    "cancel_order",
    "modify_order",
))
FORBIDDEN_IMPORT_ROOTS = frozenset((
    "ibapi",
    "socket",
    "requests",
    "urllib",
    "http",
    "httpx",
    "aiohttp",
    "websockets",
    "paramiko",
    "subprocess",
))
FORBIDDEN_ATTRIBUTE_NAMES = frozenset((
    "placeOrder",
    "cancelOrder",
    "reqGlobalCancel",
    "reqOpenOrders",
    "reqAllOpenOrders",
    "connect",
    "disconnect",
))
FORBIDDEN_CALL_NAMES = frozenset((
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
))
EXPECTED_BLOCK_REASONS = {
    "connect": "G6_20_CONNECTION_DISABLED",
    "materialize_order_request": "G6_20_REQUEST_MATERIALIZATION_DISABLED",
    "submit_order": "G6_20_ORDER_SUBMISSION_DISABLED",
    "cancel_order": "G6_20_ORDER_CANCELLATION_DISABLED",
    "modify_order": "G6_20_ORDER_MODIFICATION_DISABLED",
}
SAFE_DESCRIBE_VALUES = {
    "mode": "PAPER",
    "host": "127.0.0.1",
    "port": 4002,
    "asset_type": "STK",
    "order_type": "LMT",
    "time_in_force": "DAY",
    "connection_allowed": False,
    "broker_submission_allowed": False,
    "paper_order_submission_allowed": False,
    "live_execution_allowed": False,
    "automatic_retry_allowed": False,
    "automatic_cancel_allowed": False,
    "automatic_modify_allowed": False,
    "broker_order_object_allowed": False,
    "broker_request_materialization_allowed": False,
}


def _digest(payload):
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def _source_digest(source):
    if not isinstance(source, str):
        return None
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _valid_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


def _utc_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
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


def _safe_base(status="BLOCKED", reason="ADAPTER_SOURCE_POLICY_BLOCKED"):
    return {
        "engine": "AURORA G6.20 Adapter Source Policy Review",
        "policy_version": POLICY_VERSION,
        "status": status,
        "reason": reason,
        "source_policy_validated": False,
        "implementation_allowed": False,
        "connection_allowed": False,
        "broker_submission_allowed": False,
        "paper_order_submission_allowed": False,
        "live_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_cancel_allowed": False,
        "automatic_modify_allowed": False,
        "broker_order_object_allowed": False,
        "broker_request_materialization_allowed": False,
    }


def _review_contract_payload(contract):
    return {
        "version": contract.get("version"),
        "generated_at": contract.get("generated_at"),
        "review_envelope_sha256": contract.get("review_envelope_sha256"),
        "implementation_manifest_sha256": contract.get(
            "implementation_manifest_sha256"
        ),
        "attempt_id": contract.get("attempt_id"),
        "authorization_id": contract.get("authorization_id"),
        "idempotency_key": contract.get("idempotency_key"),
        "paper_account_evidence_token": contract.get(
            "paper_account_evidence_token"
        ),
        "client_id": contract.get("client_id"),
        "order": contract.get("order"),
        "release_prerequisites": contract.get("release_prerequisites"),
    }


def _validate_review_contract(contract):
    if not isinstance(contract, dict):
        return False, "INVALID_G6_19_REVIEW_CONTRACT"
    if (
        contract.get("status")
        != "IMPLEMENTATION_REVIEW_CONTRACT_VALIDATED_NON_EXECUTABLE"
        or contract.get("reason")
        != "ADAPTER_SPECIFICATION_FROZEN_FOR_REVIEW"
        or contract.get("version") != CONTRACT_VERSION
        or contract.get("next_gate")
        != "G6_20_ADAPTER_SOURCE_POLICY_REVIEW_REQUIRED"
        or _uuid4(contract.get("attempt_id")) is None
        or _uuid4(contract.get("authorization_id")) is None
        or not _valid_sha256(contract.get("review_envelope_sha256"))
        or not _valid_sha256(contract.get("implementation_manifest_sha256"))
        or not _valid_sha256(
            contract.get("implementation_review_contract_sha256")
        )
    ):
        return False, "G6_19_REVIEW_CONTRACT_STATE_INVALID"

    unsafe_flags = (
        "implementation_allowed",
        "connection_allowed",
        "broker_submission_allowed",
        "paper_order_submission_allowed",
        "live_execution_allowed",
        "automatic_retry_allowed",
        "automatic_cancel_allowed",
        "automatic_modify_allowed",
        "broker_order_object_allowed",
        "broker_request_materialization_allowed",
    )
    if any(contract.get(field) is not False for field in unsafe_flags):
        return False, "G6_19_REVIEW_CONTRACT_PERMISSION_INVALID"

    required_release = {
        "g6_11_real_paper_readonly_evidence_required": True,
        "independent_source_review_required": True,
        "paper_execution_release_required": True,
        "live_execution_release_required": True,
    }
    if contract.get("release_prerequisites") != required_release:
        return False, "G6_19_RELEASE_PREREQUISITES_INVALID"

    calculated = _digest(_review_contract_payload(contract))
    if (
        calculated is None
        or calculated != contract["implementation_review_contract_sha256"]
    ):
        return False, "G6_19_REVIEW_CONTRACT_DIGEST_MISMATCH"

    return True, None


def _strip_docstring(body):
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _literal_dict(node):
    if not isinstance(node, ast.Dict):
        return None
    result = {}
    for key_node, value_node in zip(node.keys, node.values):
        if (
            not isinstance(key_node, ast.Constant)
            or not isinstance(key_node.value, str)
        ):
            return None
        if (
            isinstance(value_node, ast.Constant)
            and isinstance(value_node.value, (str, int, bool))
        ):
            result[key_node.value] = value_node.value
            continue
        if (
            isinstance(value_node, ast.Name)
            and value_node.id == "SKELETON_VERSION"
        ):
            result[key_node.value] = EXPECTED_SKELETON_VERSION
            continue
        return None
    return result


def _validate_init(method):
    body = _strip_docstring(method.body)
    if len(body) != 1 or not isinstance(body[0], ast.Assign):
        return False
    assignment = body[0]
    if len(assignment.targets) != 1:
        return False
    target = assignment.targets[0]
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
        and target.attr == "_review_contract"
        and isinstance(assignment.value, ast.Name)
        and assignment.value.id == "review_contract"
    )


def _validate_describe(method):
    body = _strip_docstring(method.body)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    values = _literal_dict(body[0].value)
    if values is None:
        return False
    expected = {
        "skeleton_version": EXPECTED_SKELETON_VERSION,
        **SAFE_DESCRIBE_VALUES,
    }
    return values == expected


def _validate_blocked_method(method, method_name):
    body = _strip_docstring(method.body)
    if len(body) != 1 or not isinstance(body[0], ast.Raise):
        return False
    exc = body[0].exc
    if (
        not isinstance(exc, ast.Call)
        or not isinstance(exc.func, ast.Name)
        or exc.func.id != "RuntimeError"
        or len(exc.args) != 1
        or exc.keywords
        or not isinstance(exc.args[0], ast.Constant)
        or exc.args[0].value != EXPECTED_BLOCK_REASONS[method_name]
    ):
        return False
    return True


def _validate_ast(tree):
    top_level = _strip_docstring(tree.body)
    assignments = {}
    classes = []

    for node in top_level:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "SOURCE_IMPORTS_NOT_ALLOWED"
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)
                or not isinstance(node.value, ast.Constant)
            ):
                return False, "SOURCE_TOP_LEVEL_ASSIGNMENT_INVALID"
            assignments[node.targets[0].id] = node.value.value
            continue
        if isinstance(node, ast.ClassDef):
            classes.append(node)
            continue
        return False, "SOURCE_TOP_LEVEL_EXECUTION_NOT_ALLOWED"

    if assignments != {
        "SKELETON_VERSION": EXPECTED_SKELETON_VERSION
    }:
        return False, "SOURCE_SKELETON_VERSION_INVALID"

    if len(classes) != 1 or classes[0].name != EXPECTED_CLASS:
        return False, "SOURCE_ADAPTER_CLASS_INVALID"

    adapter_class = classes[0]
    if adapter_class.bases or adapter_class.keywords or adapter_class.decorator_list:
        return False, "SOURCE_ADAPTER_INHERITANCE_OR_DECORATOR_NOT_ALLOWED"

    methods = {}
    for node in _strip_docstring(adapter_class.body):
        if isinstance(node, ast.AsyncFunctionDef):
            return False, "SOURCE_ASYNC_METHOD_NOT_ALLOWED"
        if not isinstance(node, ast.FunctionDef):
            return False, "SOURCE_CLASS_STATEMENT_INVALID"
        if node.decorator_list:
            return False, "SOURCE_METHOD_DECORATOR_NOT_ALLOWED"
        if node.name in methods:
            return False, "SOURCE_DUPLICATE_METHOD"
        methods[node.name] = node

    if set(methods) != REQUIRED_METHODS:
        return False, "SOURCE_METHOD_SURFACE_INVALID"

    if not _validate_init(methods["__init__"]):
        return False, "SOURCE_INIT_INVALID"
    if not _validate_describe(methods["describe"]):
        return False, "SOURCE_DESCRIBE_INVALID"
    for method_name in BLOCKED_METHODS:
        if not _validate_blocked_method(methods[method_name], method_name):
            return False, f"SOURCE_{method_name.upper()}_NOT_HARD_DISABLED"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                    return False, "FORBIDDEN_BROKER_OR_NETWORK_IMPORT"
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                return False, "FORBIDDEN_BROKER_OR_NETWORK_IMPORT"
        if (
            isinstance(node, ast.Attribute)
            and node.attr in FORBIDDEN_ATTRIBUTE_NAMES
        ):
            return False, "FORBIDDEN_BROKER_OR_NETWORK_ATTRIBUTE"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALL_NAMES
        ):
            return False, "FORBIDDEN_DYNAMIC_OR_FILE_CALL"
        if isinstance(node, (ast.With, ast.AsyncWith, ast.Lambda, ast.Yield, ast.YieldFrom)):
            return False, "SOURCE_DYNAMIC_CONTROL_FLOW_NOT_ALLOWED"

    return True, None


def evaluate_adapter_source_policy(review_contract, source_text):
    contract_valid, contract_error = _validate_review_contract(
        review_contract
    )
    if not contract_valid:
        return {**_safe_base(), "reason": contract_error}

    if (
        not isinstance(source_text, str)
        or not source_text.strip()
        or len(source_text.encode("utf-8")) > 100_000
    ):
        return {**_safe_base(), "reason": "SOURCE_TEXT_INVALID"}

    try:
        tree = ast.parse(source_text)
    except (SyntaxError, ValueError, TypeError):
        return {**_safe_base(), "reason": "SOURCE_SYNTAX_INVALID"}

    source_valid, source_error = _validate_ast(tree)
    if not source_valid:
        return {**_safe_base(), "reason": source_error}

    source_sha256 = _source_digest(source_text)
    if source_sha256 is None:
        return {**_safe_base(), "reason": "SOURCE_DIGEST_UNAVAILABLE"}

    policy_payload = {
        "version": POLICY_VERSION,
        "review_contract_sha256": review_contract[
            "implementation_review_contract_sha256"
        ],
        "source_sha256": source_sha256,
        "skeleton_version": EXPECTED_SKELETON_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "release_prerequisites": {
            "g6_11_real_paper_readonly_evidence_required": True,
            "independent_source_review_required": True,
            "paper_execution_release_required": True,
            "live_execution_release_required": True,
        },
    }
    policy_sha256 = _digest(policy_payload)
    if policy_sha256 is None:
        return {**_safe_base(), "reason": "SOURCE_POLICY_DIGEST_UNAVAILABLE"}

    return {
        **_safe_base(
            "SOURCE_POLICY_VALIDATED_NON_EXECUTABLE",
            "REVIEW_SKELETON_SOURCE_HARD_DISABLED",
        ),
        "source_policy_validated": True,
        **policy_payload,
        "source_policy_sha256": policy_sha256,
        "next_gate": "G6_21_REAL_PAPER_EVIDENCE_BINDING_REQUIRED",
    }
