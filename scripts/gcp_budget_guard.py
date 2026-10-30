#!/usr/bin/env python3
"""Fail-closed verifier for the approved AURORA Google Cloud budget alert.

This script is read-only. It never creates, edits, or deletes a Cloud Billing
budget. Paid G0/G1 provisioning must not continue unless an exact TRY 750
budget with a 100% alert threshold covers the target project.
"""

import argparse
from decimal import Decimal, InvalidOperation
import json
import re
import subprocess
import sys


def _money_value(value):
    value = value or {}
    try:
        units = Decimal(str(value.get("units", 0)))
        nanos = Decimal(str(value.get("nanos", 0))) / Decimal("1000000000")
    except (InvalidOperation, TypeError, ValueError):
        return None
    return units + nanos


def _sanitize_error(value):
    text = str(value or "")[:500]
    text = re.sub(
        r"billingAccounts/[A-Za-z0-9-]+",
        "billingAccounts/[MASKED]",
        text,
    )
    return text


def evaluate_budget_guard(
    budgets_payload,
    project_id,
    project_number,
    expected_currency="TRY",
    expected_amount=Decimal("750"),
):
    if isinstance(budgets_payload, dict):
        budgets = budgets_payload.get("budgets") or []
    elif isinstance(budgets_payload, list):
        budgets = budgets_payload
    else:
        budgets = []

    expected_amount = Decimal(str(expected_amount))
    expected_currency = str(expected_currency).strip().upper()
    accepted_project_scopes = {
        f"projects/{str(project_id).strip()}",
        f"projects/{str(project_number).strip()}",
    }
    evaluated = []

    for budget in budgets:
        if not isinstance(budget, dict):
            continue

        specified = (
            (budget.get("amount") or {}).get("specifiedAmount")
            or {}
        )
        amount = _money_value(specified)
        currency = str(specified.get("currencyCode") or "").strip().upper()
        projects = set(
            (budget.get("budgetFilter") or {}).get("projects")
            or []
        )
        scope_covers_project = (
            not projects
            or bool(projects & accepted_project_scopes)
        )

        thresholds = []
        for rule in budget.get("thresholdRules") or []:
            try:
                thresholds.append(Decimal(str(rule.get("thresholdPercent"))))
            except (InvalidOperation, AttributeError, TypeError, ValueError):
                continue

        exact_amount = amount == expected_amount
        exact_currency = currency == expected_currency
        full_budget_alert = Decimal("1.0") in thresholds
        matched = all((
            exact_amount,
            exact_currency,
            scope_covers_project,
            full_budget_alert,
        ))

        evaluated.append({
            "display_name": budget.get("displayName") or "UNNAMED_BUDGET",
            "amount": str(amount) if amount is not None else None,
            "currency": currency or None,
            "scope_covers_project": scope_covers_project,
            "has_100_percent_alert": full_budget_alert,
            "matched": matched,
        })

    matches = [item for item in evaluated if item["matched"]]
    return {
        "status": "PASS" if matches else "BLOCK",
        "expected_currency": expected_currency,
        "expected_amount": str(expected_amount),
        "project_id": project_id,
        "budget_count": len(evaluated),
        "matching_budget_count": len(matches),
        "paid_resource_creation_allowed": bool(matches),
        "budget_alert_is_spend_cap": False,
        "failure_reason": None if matches else "EXACT_PROJECT_COVERING_BUDGET_ALERT_NOT_VERIFIED",
    }


def _gcloud_json(arguments):
    completed = subprocess.run(
        ["gcloud", *arguments, "--format=json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "GCLOUD_READ_FAILED: "
            + (completed.stderr.strip() or "unknown gcloud error")[:500]
        )
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as error:
        raise RuntimeError("GCLOUD_INVALID_JSON") from error


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--currency", default="TRY")
    parser.add_argument("--amount", default="750")
    args = parser.parse_args(argv)

    try:
        billing = _gcloud_json([
            "beta", "billing", "projects", "describe", args.project,
        ])
        if billing.get("billingEnabled") is not True:
            raise RuntimeError("PROJECT_BILLING_NOT_ENABLED")

        billing_account_name = str(
            billing.get("billingAccountName") or ""
        ).strip()
        if not billing_account_name.startswith("billingAccounts/"):
            raise RuntimeError("BILLING_ACCOUNT_NOT_RESOLVED")
        billing_account_id = billing_account_name.split("/", 1)[1]

        project = _gcloud_json([
            "projects", "describe", args.project,
        ])
        project_number = str(project.get("projectNumber") or "").strip()
        if not project_number:
            raise RuntimeError("PROJECT_NUMBER_NOT_RESOLVED")

        budgets = _gcloud_json([
            "billing", "budgets", "list",
            f"--billing-account={billing_account_id}",
        ])
        result = evaluate_budget_guard(
            budgets,
            project_id=args.project,
            project_number=project_number,
            expected_currency=args.currency,
            expected_amount=Decimal(args.amount),
        )
    except (InvalidOperation, RuntimeError) as error:
        result = {
            "status": "BLOCK",
            "project_id": args.project,
            "paid_resource_creation_allowed": False,
            "budget_alert_is_spend_cap": False,
            "failure_reason": _sanitize_error(error),
        }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
