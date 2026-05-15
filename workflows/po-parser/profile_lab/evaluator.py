import math
import re
from typing import Any


P0_HEADER_FIELDS = ["customer_name", "po_number", "po_date"]
P0_ITEM_FIELDS = ["customer_material", "qty", "delivery_date"]
P1_HEADER_FIELDS = ["currency", "total_amount"]
P1_ITEM_FIELDS = ["unit_price", "amount", "unit", "customer_release_no", "sap_material"]


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


def to_number(value: Any) -> float | None:
    if isinstance(value, bool) or is_empty(value):
        return None
    if isinstance(value, str):
        value = normalize_value(value).replace(",", "")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def total_amount_tolerance(value: Any) -> float:
    number = to_number(value)
    if number is None:
        return 0.10
    return max(0.10, abs(number) * 0.0001)


def values_equal(field: str, expected: Any, actual: Any) -> bool:
    if field in {"qty"}:
        return numbers_equal(expected, actual, tolerance=0.0)
    if field in {"unit_price"}:
        return numbers_equal(expected, actual, tolerance=0.01)
    if field in {"amount"}:
        return numbers_equal(expected, actual, tolerance=0.05)
    if field in {"total_amount"}:
        return numbers_equal(expected, actual, tolerance=total_amount_tolerance(expected))
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


def add_quality_error(
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


def score_ratio(scored_count: int, failed_count: int) -> float:
    if scored_count == 0:
        return 1.0
    return (scored_count - failed_count) / scored_count


def calculate_p1_score(
    expected_header: dict,
    actual_header: dict,
    expected_items: list[dict],
    actual_items: list[dict],
    quality_errors: list[dict],
) -> float:
    scored_count = 0
    failed_count = 0

    for field in P1_HEADER_FIELDS:
        expected_value = expected_header.get(field)
        if is_empty(expected_value):
            continue
        scored_count += 1
        actual_value = actual_header.get(field)
        if values_equal(field, expected_value, actual_value):
            continue
        failed_count += 1
        add_quality_error(
            quality_errors,
            f"header.{field}",
            expected_value,
            actual_value,
            "P1 field mismatch",
        )

    for index, expected_item in enumerate(expected_items):
        actual_item = actual_items[index] if index < len(actual_items) else {}
        for field in P1_ITEM_FIELDS:
            expected_value = expected_item.get(field)
            if is_empty(expected_value):
                continue
            scored_count += 1
            actual_value = actual_item.get(field)
            if values_equal(field, expected_value, actual_value):
                continue
            failed_count += 1
            add_quality_error(
                quality_errors,
                f"items[{index}].{field}",
                expected_value,
                actual_value,
                "P1 field mismatch",
            )

    return score_ratio(scored_count, failed_count)


def calculate_business_rule_score(
    actual_header: dict,
    actual_items: list[dict],
    quality_errors: list[dict],
) -> float:
    scored_count = 0
    failed_count = 0

    for index, item in enumerate(actual_items):
        qty = to_number(item.get("qty"))
        unit_price = to_number(item.get("unit_price"))
        amount = to_number(item.get("amount"))
        if qty is None or unit_price is None or amount is None:
            continue
        scored_count += 1
        price_basis_qty = to_number(item.get("price_basis_qty"))
        if price_basis_qty and price_basis_qty > 0:
            expected_amount = qty / price_basis_qty * unit_price
        else:
            expected_amount = qty * unit_price
        if numbers_equal(expected_amount, amount, tolerance=0.05):
            continue
        failed_count += 1
        add_quality_error(
            quality_errors,
            f"items[{index}].amount",
            expected_amount,
            item.get("amount"),
            "business rule mismatch",
        )

    total_amount = to_number(actual_header.get("total_amount"))
    item_amounts = [to_number(item.get("amount")) for item in actual_items]
    if (
        total_amount is not None
        and item_amounts
        and all(amount is not None for amount in item_amounts)
    ):
        scored_count += 1
        expected_total = sum(amount for amount in item_amounts if amount is not None)
        if not numbers_equal(
            expected_total,
            total_amount,
            tolerance=total_amount_tolerance(total_amount),
        ):
            failed_count += 1
            add_quality_error(
                quality_errors,
                "header.total_amount",
                expected_total,
                actual_header.get("total_amount"),
                "business rule mismatch",
            )

    return score_ratio(scored_count, failed_count)


def normalize_item_rows(items: list[Any], errors: list[dict]) -> list[dict]:
    normalized_items = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            normalized_items.append(item)
            continue
        add_blocking_error(
            errors,
            f"items[{index}]",
            "dict",
            item,
            "schema shape mismatch",
        )
        normalized_items.append({})
    return normalized_items


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
    return normalize_item_rows(items, errors)


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
    quality_errors: list[dict] = []
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
    p1_score = calculate_p1_score(
        expected_header=expected_header,
        actual_header=actual_header,
        expected_items=expected_items,
        actual_items=actual_items,
        quality_errors=quality_errors,
    )
    business_rule_score = calculate_business_rule_score(
        actual_header=actual_header,
        actual_items=actual_items,
        quality_errors=quality_errors,
    )
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
        "quality_errors": quality_errors,
        "recommendation": "publishable" if publishable else "not_publishable",
    }
