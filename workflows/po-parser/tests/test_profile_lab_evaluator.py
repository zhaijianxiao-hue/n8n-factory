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
