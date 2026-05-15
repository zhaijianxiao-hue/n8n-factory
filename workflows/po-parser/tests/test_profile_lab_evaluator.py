import json

from profile_lab.commands import main
from profile_lab.customer_assets import init_customer
from profile_lab.evaluator import evaluate_po_result, normalize_value
from profile_lab.json_io import write_json


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


def test_evaluate_po_result_blocks_publish_when_p1_fields_mismatch():
    expected = {
        "header": {
            "customer_name": "ACME",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "EUR",
            "total_amount": 100,
        },
        "items": [
            {
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
            "customer_name": "ACME",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "USD",
            "total_amount": 90,
        },
        "items": [
            {
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 45,
                "amount": 90,
            }
        ],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is True
    assert report["publishable"] is False
    assert report["blocking_errors"] == []
    assert report["scores"]["p1"] < 0.95
    assert report["quality_errors"]


def test_evaluate_po_result_blocks_publish_when_item_amount_rule_fails():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [
            {
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 100,
            }
        ],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [
            {
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 90,
            }
        ],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is True
    assert report["publishable"] is False
    assert report["scores"]["business_rules"] < 0.95
    assert any(error["reason"] == "business rule mismatch" for error in report["quality_errors"])


def test_evaluate_po_result_blocks_publish_when_item_sum_total_rule_fails():
    expected = {
        "header": {
            "customer_name": "ACME",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "total_amount": 100,
        },
        "items": [
            {
                "customer_material": "MAT-1",
                "qty": 1,
                "delivery_date": "2026-06-01",
                "unit_price": 40,
                "amount": 40,
            },
            {
                "customer_material": "MAT-2",
                "qty": 1,
                "delivery_date": "2026-06-02",
                "unit_price": 60,
                "amount": 60,
            },
        ],
    }
    actual = {
        "header": {
            "customer_name": "ACME",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "total_amount": 90,
        },
        "items": [
            {
                "customer_material": "MAT-1",
                "qty": 1,
                "delivery_date": "2026-06-01",
                "unit_price": 40,
                "amount": 40,
            },
            {
                "customer_material": "MAT-2",
                "qty": 1,
                "delivery_date": "2026-06-02",
                "unit_price": 60,
                "amount": 60,
            },
        ],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is True
    assert report["publishable"] is False
    assert report["scores"]["business_rules"] < 0.95
    assert any(error["field"] == "header.total_amount" for error in report["quality_errors"])


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


def test_evaluate_command_writes_summary(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    write_json(customer_dir / "expected" / "po-001.json", expected)
    write_json(
        customer_dir / "runs" / "run-1" / "adjudication" / "po-001.merged_draft.json",
        expected,
    )

    exit_code = main([
        "--lab-root",
        str(root),
        "evaluate",
        "--customer",
        "acme",
        "--run-id",
        "run-1",
    ])

    assert exit_code == 0
    summary_path = customer_dir / "runs" / "run-1" / "evaluation" / "summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["publishable"] is True
    assert summary["reports"][0]["schema_pass"] is True
    assert "scores" in summary["reports"][0]


def test_evaluate_command_checks_draft_when_expected_missing(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    write_json(
        customer_dir / "runs" / "run-1" / "manifest.json",
        {"run_id": "run-1", "customer": "acme", "samples": ["po-001.pdf"]},
    )
    write_json(
        customer_dir / "runs" / "run-1" / "adjudication" / "po-001.merged_draft.json",
        actual,
    )

    exit_code = main([
        "--lab-root",
        str(root),
        "evaluate",
        "--customer",
        "acme",
        "--run-id",
        "run-1",
    ])

    assert exit_code == 0
    summary = json.loads((customer_dir / "runs" / "run-1" / "evaluation" / "summary.json").read_text(encoding="utf-8"))
    report = summary["reports"][0]
    assert summary["sample_count"] == 1
    assert summary["publishable"] is False
    assert report["sample_key"] == "po-001"
    assert report["expected_missing"] is True
    assert report["schema_pass"] is True
    assert report["p0_pass"] is True
    assert report["recommendation"] == "confirm_expected"


def test_evaluate_command_reports_missing_actual_draft(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    write_json(customer_dir / "expected" / "po-001.json", expected)

    exit_code = main([
        "--lab-root",
        str(root),
        "evaluate",
        "--customer",
        "acme",
        "--run-id",
        "run-1",
    ])

    assert exit_code == 0
    evaluation_dir = customer_dir / "runs" / "run-1" / "evaluation"
    report_path = evaluation_dir / "po-001.report.json"
    summary = json.loads((evaluation_dir / "summary.json").read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert summary["publishable"] is False
    assert report_path.is_file()
    assert report["blocking_errors"][0]["reason"] == "actual merged draft missing"
