from profile_lab.evaluator import evaluate_po_result, normalize_value


def test_normalize_value_collapses_string_whitespace():
    assert normalize_value("  PO   123  ") == "PO 123"


def test_evaluate_po_result_passes_matching_p0_fields():
    expected = {
        "header": {
            "customer_name": "ACME Corp",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "EUR",
            "total_amount": 100.0,
        },
        "items": [
            {
                "line_no": 10,
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 100,
            }
        ],
    }
    actual = {
        "header": {
            "customer_name": " ACME   Corp ",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "EUR",
            "total_amount": 100.0,
        },
        "items": [
            {
                "line_no": 10,
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 100,
            }
        ],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is True
    assert report["publishable"] is True
    assert report["blocking_errors"] == []


def test_evaluate_po_result_blocks_qty_mismatch():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 3, "delivery_date": "2026-06-01"}],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is False
    assert report["publishable"] is False
    assert report["blocking_errors"][0]["field"] == "items[0].qty"


def test_evaluate_po_result_requires_exact_numeric_qty_match():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 1000000000, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 1000000001, "delivery_date": "2026-06-01"}],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is False
    assert report["publishable"] is False
    assert report["blocking_errors"][0]["field"] == "items[0].qty"


def test_evaluate_po_result_blocks_missing_required_header_field():
    expected = {
        "header": {"customer_name": "ACME", "po_number": None, "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": None, "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is False
    assert report["publishable"] is False
    assert report["blocking_errors"][0]["field"] == "header.po_number"
    assert report["blocking_errors"][0]["reason"] == "required field missing"


def test_evaluate_po_result_blocks_empty_items_shape():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["schema_pass"] is False
    assert report["publishable"] is False
    assert report["blocking_errors"][0]["field"] == "items"


def test_evaluate_po_result_blocks_malformed_actual_items_without_exception():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": {},
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["schema_pass"] is False
    assert report["publishable"] is False
    assert any(error["field"] == "items" for error in report["blocking_errors"])


def test_evaluate_po_result_blocks_malformed_actual_item_row_without_exception():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": ["not-an-object"],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["schema_pass"] is False
    assert report["publishable"] is False
    assert any(
        error["field"] == "items[0]" and error["reason"] == "schema shape mismatch"
        for error in report["blocking_errors"]
    )


def test_evaluate_po_result_blocks_malformed_expected_item_row_without_exception():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": ["not-an-object"],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["schema_pass"] is False
    assert report["publishable"] is False
    assert any(
        error["field"] == "items[0]" and error["reason"] == "schema shape mismatch"
        for error in report["blocking_errors"]
    )
