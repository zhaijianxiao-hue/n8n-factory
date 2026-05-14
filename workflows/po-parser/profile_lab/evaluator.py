import math
import re
from typing import Any


P0_HEADER_FIELDS = ["customer_name", "po_number", "po_date"]
P0_ITEM_FIELDS = ["customer_material", "qty", "delivery_date"]


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and normalize_value(value) == "")


def numbers_equal(expected: Any, actual: Any, tolerance: float = 0.0) -> bool:
    try:
        expected_number = float(expected)
        actual_number = float(actual)
    except (TypeError, ValueError):
        return False
    return math.isclose(expected_number, actual_number, rel_tol=0.0, abs_tol=tolerance)


def values_equal(field: str, expected: Any, actual: Any) -> bool:
    if field in {"qty"}:
        return numbers_equal(expected, actual, tolerance=0.0)
    if field in {"unit_price"}:
        return numbers_equal(expected, actual, tolerance=0.01)
    if field in {"amount"}:
        return numbers_equal(expected, actual, tolerance=0.05)
    if field in {"total_amount"}:
        try:
            tolerance = max(0.10, abs(float(expected)) * 0.0001)
        except (TypeError, ValueError):
            tolerance = 0.10
        return numbers_equal(expected, actual, tolerance=tolerance)
    return normalize_value(expected) == normalize_value(actual)


def add_blocking_error(
    errors: list[dict],
    field: str,
    expected: Any,
    actual: Any,
    reason: str,
) -> None:
    errors.append(
        {
            "field": field,
            "expected": expected,
            "actual": actual,
            "reason": reason,
        }
    )


def get_items(payload: dict, errors: list[dict]) -> list[dict]:
    items = payload.get("items")
    if not isinstance(items, list):
        add_blocking_error(
            errors,
            "items",
            "list",
            type(items).__name__,
            "schema shape mismatch",
        )
        return []
    if not items:
        add_blocking_error(
            errors,
            "items",
            "non-empty list",
            items,
            "schema shape mismatch",
        )
    return items


def add_required_field_error(
    errors: list[dict],
    field: str,
    expected: Any,
    actual: Any,
) -> bool:
    if not is_empty(expected) and not is_empty(actual):
        return False
    add_blocking_error(
        errors,
        field,
        expected,
        actual,
        "required field missing",
    )
    return True


def evaluate_po_result(expected: dict, actual: dict) -> dict:
    blocking_errors: list[dict] = []
    schema_pass = True

    expected_header = expected.get("header")
    actual_header = actual.get("header")
    if not isinstance(expected_header, dict):
        schema_pass = False
        add_blocking_error(
            blocking_errors,
            "header",
            "dict",
            type(expected_header).__name__,
            "schema shape mismatch",
        )
        expected_header = {}
    if not isinstance(actual_header, dict):
        schema_pass = False
        add_blocking_error(
            blocking_errors,
            "header",
            "dict",
            type(actual_header).__name__,
            "schema shape mismatch",
        )
        actual_header = {}

    expected_items = get_items(expected, blocking_errors)
    actual_items = get_items(actual, blocking_errors)
    if not expected_items or not actual_items:
        schema_pass = False
    if any(error["reason"] == "schema shape mismatch" for error in blocking_errors):
        schema_pass = False

    for field in P0_HEADER_FIELDS:
        if add_required_field_error(
            blocking_errors,
            f"header.{field}",
            expected_header.get(field),
            actual_header.get(field),
        ):
            continue
        if not values_equal(field, expected_header.get(field), actual_header.get(field)):
            add_blocking_error(
                blocking_errors,
                f"header.{field}",
                expected_header.get(field),
                actual_header.get(field),
                "P0 field mismatch",
            )

    item_row_count_match = len(expected_items) == len(actual_items)
    if not item_row_count_match:
        add_blocking_error(
            blocking_errors,
            "items",
            len(expected_items),
            len(actual_items),
            "P0 item row count mismatch",
        )

    for index, expected_item in enumerate(expected_items):
        actual_item = actual_items[index] if index < len(actual_items) else {}
        for field in P0_ITEM_FIELDS:
            if add_required_field_error(
                blocking_errors,
                f"items[{index}].{field}",
                expected_item.get(field),
                actual_item.get(field),
            ):
                continue
            if not values_equal(field, expected_item.get(field), actual_item.get(field)):
                add_blocking_error(
                    blocking_errors,
                    f"items[{index}].{field}",
                    expected_item.get(field),
                    actual_item.get(field),
                    "P0 field mismatch",
                )

    p0_pass = len(blocking_errors) == 0
    p1_score = 1.0
    business_rule_score = 1.0
    publishable = (
        schema_pass
        and p0_pass
        and item_row_count_match
        and p1_score >= 0.95
        and business_rule_score >= 0.95
    )

    return {
        "overall_score": 1.0 if publishable else 0.0,
        "publishable": publishable,
        "schema_pass": schema_pass,
        "p0_pass": p0_pass,
        "item_row_count_match": item_row_count_match,
        "scores": {
            "header": 1.0 if p0_pass else 0.0,
            "items": 1.0 if p0_pass else 0.0,
            "p1": p1_score,
            "business_rules": business_rule_score,
        },
        "blocking_errors": blocking_errors,
        "recommendation": "publishable" if publishable else "not_publishable",
    }
