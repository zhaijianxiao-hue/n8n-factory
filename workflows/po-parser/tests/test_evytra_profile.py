import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


SERVICE_PATH = Path(__file__).resolve().parents[1] / "service" / "po_parser_service.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "evytra" / "expected.json"
PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "evytra.json"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "po-output.schema.json"
EXTRACTED_TEXT_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "evytra" / "extracted-linux.txt"
)


def load_service_module():
    spec = importlib.util.spec_from_file_location("po_parser_service", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_expected_fixture():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_extracted_text():
    return EXTRACTED_TEXT_PATH.read_text(encoding="utf-8")


def test_detects_evytra_profile_from_text():
    module = load_service_module()
    assert module.detect_customer_profile(load_extracted_text()) == "evytra"


def test_evytra_profile_returns_expected_shape():
    module = load_service_module()
    result = module.parse_evytra_text(load_extracted_text())

    assert result["header"]["delivery_tolerance_positive_pct"] == 0
    assert result["header"]["delivery_tolerance_negative_pct"] == 0
    assert result["header"]["production_note"]
    assert result["items"][0]["customer_material"] == "4001391504"
    assert result["items"][0]["material_description"] == "735098"
    assert result["items"][0]["customer_release_no"] == "30601875"
    assert result["items"][0]["delivery_date"] == "2026-05-01"


def test_evytra_parse_matches_expected_fixture_core_fields():
    module = load_service_module()
    expected = load_expected_fixture()
    result = module.parse_evytra_text(load_extracted_text())

    assert result["customer_profile"] == expected["customer_profile"]
    assert result["header"]["customer_name"] == expected["header"]["customer_name"]
    assert result["header"]["po_number"] == expected["header"]["po_number"]
    assert result["header"]["total_amount"] == expected["header"]["total_amount"]
    assert len(result["items"]) == len(expected["items"])
    assert result["items"][2]["amount"] == expected["items"][2]["amount"]


def test_evytra_parse_flags_review_for_suspicious_amounts():
    module = load_service_module()
    result = module.parse_evytra_text(load_extracted_text())

    assert result["status"] == "review"
    assert any(
        "item 30" in warning.lower() or "suspicious" in warning.lower()
        for warning in result["warnings"]
    )


def test_evytra_profile_config_exists_with_required_markers():
    profile = load_json(PROFILE_PATH)

    assert profile["profile_name"] == "evytra"
    assert "EVYTRA GmbH" in profile["markers"]
    assert profile["number_format"]["decimal_separator"] == ","
    assert profile["number_format"]["thousands_separator"] == "."


def test_evytra_expected_fixture_matches_output_schema():
    fixture = load_expected_fixture()
    schema = load_json(SCHEMA_PATH)
    errors = sorted(
        Draft7Validator(schema).iter_errors(fixture), key=lambda error: list(error.path)
    )

    assert errors == []


def test_linux_extracted_fixture_preserves_real_layout_breaks():
    extracted_text = load_extracted_text()

    assert "OrderConfirmation @ evytra . com" in extracted_text
    assert "Your supplier ID:\n704000" in extracted_text
    assert "10\n735098\n1.000\n4001391504     TA\npcs" in extracted_text


@pytest.mark.asyncio
async def test_scan_directory_matches_uppercase_pdf_extension(tmp_path, monkeypatch):
    module = load_service_module()
    uppercase_pdf = tmp_path / "sample.PDF"
    uppercase_pdf.write_bytes(b"fake-pdf")

    original_glob = module.Path.glob

    def linux_like_glob(path_obj, pattern):
        # Simulate Linux case-sensitive glob behavior so this regression test
        # fails on Windows before the scan implementation is fixed.
        if pattern == "*.pdf":
            return [
                child for child in path_obj.iterdir() if child.name.endswith(".pdf")
            ]
        return original_glob(path_obj, pattern)

    monkeypatch.setattr(module.Path, "glob", linux_like_glob)

    result = await module.scan_directory(
        module.ScanRequest(directory=str(tmp_path), pattern="*.pdf")
    )

    assert result["count"] == 1
    assert result["files"] == [str(uppercase_pdf)]
