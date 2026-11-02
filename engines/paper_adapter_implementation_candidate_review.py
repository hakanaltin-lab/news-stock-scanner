"""G8.19 static review gate for a non-executable adapter implementation candidate.

The candidate source is parsed with Python AST and is never imported or
executed. A successful result proves only that the tracked candidate remains
hard-disabled and bound to a verified G8.18 design attestation.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from engines.paper_adapter_implementation_design import (
    DESIGN_ID,
    PERMISSION_FLAGS,
)
from engines.paper_adapter_implementation_design_attestation import (
    ENGINE_VERSION as DESIGN_ATTESTATION_ENGINE_VERSION,
)


ENGINE_VERSION = "AURORA G8.19 Paper Adapter Implementation Candidate Review"
CANDIDATE_VERSION = "AURORA_G8_19_IBKR_PAPER_ADAPTER_IMPLEMENTATION_CANDIDATE_V1"
EXPECTED_CLASS = "IBKRPaperAdapterImplementationCandidate"
NEXT_GATE = "INDEPENDENT_ADAPTER_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED"

DESIGN_ATTESTATION_FIELDS = {
    "engine",
    "status",
    "verified",
    "adapter_design_independently_attested",
    "reason",
    "checks",
    "design_review_id",
    "reviewer_id",
    "captured_at_utc",
    "expires_at_utc",
    "design_review_artifact_sha256",
    "review_request_sha256",
    "design_sha256",
    "source_review_id",
    "source_git_sha",
    "source_sha256",
    "source_attestation_sha256",
    "design_attestation_sha256",
    "reviewer_evidence_sha256",
    *PERMISSION_FLAGS,
    "next_gate",
}

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
    "connect": "G8_19_CONNECTION_DISABLED",
    "materialize_order_request": "G8_19_REQUEST_MATERIALIZATION_DISABLED",
    "submit_order": "G8_19_ORDER_SUBMISSION_DISABLED",
    "cancel_order": "G8_19_ORDER_CANCELLATION_DISABLED",
    "modify_order": "G8_19_ORDER_MODIFICATION_DISABLED",
}

SAFE_DESCRIBE_VALUES = {
    "implementation_candidate": True,
    "non_executable": True,
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
    **{
        name: False
        for name in PERMISSION_FLAGS
    },
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


def canonical_json_sha256(payload):
    if not isinstance(payload, dict):
        return None
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


def _uuid4(value):
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError):
        return None
    return text if parsed.version == 4 and str(parsed) == text else None


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


def _permissions_false(payload):
    return (
        isinstance(payload, dict)
        and all(
            name in payload
            and payload.get(name) is False
            for name in PERMISSION_FLAGS
        )
    )


def _blocked(reason):
    return {
        "engine": ENGINE_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "candidate_validated": False,
        "design_attestation_verified": False,
        "candidate_version": None,
        "adapter_class": None,
        "candidate_source_sha256": None,
        "design_attestation_sha256": None,
        "design_sha256": None,
        "design_review_id": None,
        "source_attestation_sha256": None,
        "independent_candidate_review_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": "REPAIR_NON_EXECUTABLE_IMPLEMENTATION_CANDIDATE",
    }


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
                "design_attestation_sha256",
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
            and value_node.id in {
                "CANDIDATE_VERSION",
                "DESIGN_ID",
            }
        ):
            result[key_node.value] = (
                CANDIDATE_VERSION
                if value_node.id == "CANDIDATE_VERSION"
                else DESIGN_ID
            )
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
        and target.attr == "_design_attestation_sha256"
        and isinstance(assignment.value, ast.Name)
        and assignment.value.id == "design_attestation_sha256"
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
        "candidate_version": CANDIDATE_VERSION,
        "design_id": DESIGN_ID,
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


def validate_candidate_source(source_text):
    try:
        tree = ast.parse(
            source_text,
            mode="exec",
        )
    except (SyntaxError, ValueError, TypeError):
        return False, "CANDIDATE_SOURCE_SYNTAX_INVALID"

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
            return False, "CANDIDATE_IMPORTS_NOT_ALLOWED"

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
                return False, "CANDIDATE_TOP_LEVEL_ASSIGNMENT_INVALID"
            assignments[
                node.targets[0].id
            ] = node.value.value
            continue

        if isinstance(node, ast.ClassDef):
            classes.append(node)
            continue

        return False, "CANDIDATE_TOP_LEVEL_EXECUTION_NOT_ALLOWED"

    if assignments != {
        "CANDIDATE_VERSION": CANDIDATE_VERSION,
        "DESIGN_ID": DESIGN_ID,
    }:
        return False, "CANDIDATE_IDENTITY_CONSTANTS_INVALID"

    if (
        len(classes) != 1
        or classes[0].name != EXPECTED_CLASS
        or classes[0].bases
        or classes[0].keywords
        or classes[0].decorator_list
    ):
        return False, "CANDIDATE_CLASS_INVALID"

    adapter = classes[0]
    methods = {}
    for node in _strip_docstring(
        adapter.body
    ):
        if not isinstance(
            node,
            ast.FunctionDef,
        ):
            return False, "CANDIDATE_CLASS_BODY_INVALID"
        if node.name in methods:
            return False, "CANDIDATE_DUPLICATE_METHOD"
        methods[node.name] = node

    if set(methods) != REQUIRED_METHODS:
        return False, "CANDIDATE_METHOD_SET_INVALID"

    if not all(
        _validate_signature(
            methods[name],
            name,
        )
        for name in REQUIRED_METHODS
    ):
        return False, "CANDIDATE_METHOD_SIGNATURE_INVALID"

    if not _validate_init(
        methods["__init__"]
    ):
        return False, "CANDIDATE_INIT_INVALID"

    if not _validate_describe(
        methods["describe"]
    ):
        return False, "CANDIDATE_DESCRIBE_INVALID"

    for name in BLOCKED_METHODS:
        if not _validate_blocked_method(
            methods[name],
            name,
        ):
            return False, (
                "CANDIDATE_BROKER_METHOD_NOT_HARD_DISABLED"
            )

    for node in ast.walk(tree):
        if isinstance(
            node,
            FORBIDDEN_DYNAMIC_NODES,
        ):
            return False, "CANDIDATE_DYNAMIC_EXECUTION_NOT_ALLOWED"

        if (
            isinstance(node, ast.Attribute)
            and node.attr in FORBIDDEN_ATTRIBUTE_NAMES
        ):
            return False, "CANDIDATE_BROKER_API_ATTRIBUTE_FORBIDDEN"

        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            in FORBIDDEN_CALL_NAMES
        ):
            return False, "CANDIDATE_DYNAMIC_CALL_FORBIDDEN"

    return True, None


def evaluate_implementation_candidate(
    design_attestation,
    candidate_source,
    *,
    now=None,
):
    now = (
        now.astimezone(timezone.utc)
        if isinstance(now, datetime)
        and now.tzinfo is not None
        else datetime.now(timezone.utc)
    )

    if not isinstance(design_attestation, dict):
        return _blocked(
            "DESIGN_ATTESTATION_RESULT_INVALID"
        )
    if set(design_attestation) != DESIGN_ATTESTATION_FIELDS:
        return _blocked(
            "DESIGN_ATTESTATION_FIELD_SET_INVALID"
        )
    if not isinstance(candidate_source, str) or not candidate_source:
        return _blocked(
            "CANDIDATE_SOURCE_UNAVAILABLE"
        )

    checks = design_attestation.get("checks")
    attestation_safe = (
        design_attestation.get("engine")
        == DESIGN_ATTESTATION_ENGINE_VERSION
        and design_attestation.get("status")
        == "VERIFIED"
        and design_attestation.get("verified") is True
        and design_attestation.get(
            "adapter_design_independently_attested"
        )
        is True
        and design_attestation.get("reason")
        == "INDEPENDENT_IMPLEMENTATION_DESIGN_ATTESTATION_VERIFIED"
        and isinstance(checks, dict)
        and bool(checks)
        and all(
            value is True
            for value in checks.values()
        )
        and _permissions_false(
            design_attestation
        )
        and design_attestation.get("next_gate")
        == "NON_EXECUTABLE_ADAPTER_IMPLEMENTATION_CANDIDATE_REQUIRED"
    )
    if not attestation_safe:
        return _blocked(
            "DESIGN_ATTESTATION_NOT_VERIFIED"
        )

    captured = _utc_datetime(
        design_attestation.get(
            "captured_at_utc"
        )
    )
    expires = _utc_datetime(
        design_attestation.get(
            "expires_at_utc"
        )
    )
    if (
        captured is None
        or expires is None
        or not captured <= now <= expires
    ):
        return _blocked(
            "DESIGN_ATTESTATION_NOT_CURRENT"
        )

    design_review_id = _uuid4(
        design_attestation.get(
            "design_review_id"
        )
    )
    design_attestation_sha256 = _sha256(
        design_attestation.get(
            "design_attestation_sha256"
        )
    )
    design_sha256 = _sha256(
        design_attestation.get(
            "design_sha256"
        )
    )
    source_attestation_sha256 = _sha256(
        design_attestation.get(
            "source_attestation_sha256"
        )
    )
    source_git_sha = _git_sha(
        design_attestation.get(
            "source_git_sha"
        )
    )
    support = (
        _sha256(
            design_attestation.get(
                "design_review_artifact_sha256"
            )
        ),
        _sha256(
            design_attestation.get(
                "review_request_sha256"
            )
        ),
        _sha256(
            design_attestation.get(
                "source_sha256"
            )
        ),
        _sha256(
            design_attestation.get(
                "reviewer_evidence_sha256"
            )
        ),
        _uuid4(
            design_attestation.get(
                "source_review_id"
            )
        ),
    )
    if (
        design_review_id is None
        or design_attestation_sha256 is None
        or design_sha256 is None
        or source_attestation_sha256 is None
        or source_git_sha is None
        or any(
            value is None
            for value in support
        )
    ):
        return _blocked(
            "DESIGN_ATTESTATION_BINDING_INVALID"
        )

    source_valid, source_reason = (
        validate_candidate_source(
            candidate_source
        )
    )
    if not source_valid:
        return _blocked(
            source_reason
            or "CANDIDATE_SOURCE_POLICY_INVALID"
        )

    candidate_source_sha256 = hashlib.sha256(
        candidate_source.encode("utf-8")
    ).hexdigest()

    return {
        "engine": ENGINE_VERSION,
        "status": "IMPLEMENTATION_CANDIDATE_VALIDATED_NON_EXECUTABLE",
        "reason": "INDEPENDENT_IMPLEMENTATION_CANDIDATE_REVIEW_REQUIRED",
        "candidate_validated": True,
        "design_attestation_verified": True,
        "candidate_version": CANDIDATE_VERSION,
        "adapter_class": EXPECTED_CLASS,
        "candidate_source_sha256": (
            candidate_source_sha256
        ),
        "design_attestation_sha256": (
            design_attestation_sha256
        ),
        "design_sha256": design_sha256,
        "design_review_id": design_review_id,
        "source_attestation_sha256": (
            source_attestation_sha256
        ),
        "source_git_sha": source_git_sha,
        "independent_candidate_review_required": True,
        **{
            name: False
            for name in PERMISSION_FLAGS
        },
        "next_gate": NEXT_GATE,
    }
