import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


SERVICE_PATH = Path(__file__).resolve().parents[1] / "service" / "po_parser_service.py"


def load_service_module():
    spec = importlib.util.spec_from_file_location("po_parser_service", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_profile(profile_dir: Path, name: str, markers: list[str]) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile = {
        "profile_name": name,
        "status": "production",
        "markers": markers,
        "number_format": {
            "decimal_separator": ".",
            "thousands_separator": ",",
        },
        "item_rules": {},
    }
    (profile_dir / f"{name}.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def minimal_parse_result() -> dict:
    return {
        "source_file": "sample.pdf",
        "header": {
            "customer_name": "ACME",
            "customer_code": "acme",
            "po_number": "PO-1",
            "po_date": "2026-05-22",
            "currency": "CNY",
        },
        "items": [
            {
                "line_no": 10,
                "material_description": "part",
                "customer_material": "MAT-1",
                "qty": 1,
                "unit": "PCS",
                "amount": 1,
                "currency": "CNY",
            }
        ],
    }


def test_detects_published_profile_from_markers(tmp_path, monkeypatch):
    module = load_service_module()
    profile_dir = tmp_path / "profiles"
    write_profile(
        profile_dir,
        "武汉万集",
        ["武汉万集光电技术有限公司", "wanji.net.cn"],
    )
    monkeypatch.setattr(module, "PROFILES_DIR", profile_dir)

    text = """
    采购订单
    需方名称：武汉万集光电技术有限公司
    财务邮箱 whcaiwu@wanji.net.cn
    """

    assert module.detect_customer_profile(text) == "武汉万集"


@pytest.mark.asyncio
async def test_parse_uses_detected_published_profile_for_generic_extractor(
    tmp_path, monkeypatch
):
    module = load_service_module()
    profile_dir = tmp_path / "profiles"
    write_profile(profile_dir, "武汉万集", ["武汉万集光电技术有限公司"])
    monkeypatch.setattr(module, "PROFILES_DIR", profile_dir)

    pdf_path = tmp_path / "武汉万集.pdf"
    pdf_path.write_bytes(b"%PDF fake")
    monkeypatch.setattr(
        module,
        "extract_text_from_pdf",
        lambda _path: "需方名称：武汉万集光电技术有限公司\n采购订单",
    )

    captured = {}

    def fake_extract(text_content, customer_profile=None, profile_config=None):
        captured["customer_profile"] = customer_profile
        captured["profile_config"] = profile_config
        return {
            "header": {"customer_name": "武汉万集光电技术有限公司"},
            "items": [],
            "confidence": 0.9,
            "warnings": [],
            "status": "success",
        }

    monkeypatch.setattr(module, "extract_fields_with_ollama", fake_extract)

    result = await module.parse_po(module.ParseRequest(pdf_path=str(pdf_path)))

    assert captured["customer_profile"] == "武汉万集"
    assert captured["profile_config"]["profile_name"] == "武汉万集"
    assert result["customer_profile"] == "武汉万集"


def test_to_sap_uses_test_credentials(monkeypatch):
    module = load_service_module()
    monkeypatch.setattr(module, "SAP_URL", "http://sap-test")
    monkeypatch.setattr(module, "SAP_USER", "TEST_USER")
    monkeypatch.setattr(module, "SAP_PASS", "TEST_PASS")
    monkeypatch.setattr(module, "SAP_CA_BUNDLE", "")
    monkeypatch.setattr(module, "SAP_VERIFY_SSL", "true")
    captured = {}

    class FakeResponse:
        text = '<E_OUTPUT>[{"TYPE":"S","MESSAGE":"ok"}]</E_OUTPUT>'

        def raise_for_status(self):
            return None

    def fake_post(url, data, headers, auth, verify, timeout):
        captured.update({"url": url, "auth": auth, "headers": headers, "verify": verify, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(module.requests, "post", fake_post)
    client = TestClient(module.app)

    response = client.post("/to-sap", json={"parse_result": minimal_parse_result()})

    assert response.status_code == 200
    assert captured["url"] == "http://sap-test"
    assert captured["auth"] == ("TEST_USER", "TEST_PASS")
    assert captured["verify"] is True
    assert response.json()["sap_status"]["type"] == "S"


def test_to_sap_prd_uses_production_credentials(monkeypatch):
    module = load_service_module()
    monkeypatch.setattr(module, "SAP_PRD_URL", "https://sap-prd")
    monkeypatch.setattr(module, "SAP_PRD_USER", "PRD_USER")
    monkeypatch.setattr(module, "SAP_PRD_PASS", "PRD_PASS")
    monkeypatch.setattr(module, "SAP_PRD_CA_BUNDLE", "/tmp/sap-prd.crt")
    monkeypatch.setattr(module, "SAP_PRD_VERIFY_SSL", "true")
    captured = {}

    class FakeResponse:
        text = '<E_OUTPUT>[{"TYPE":"S","MESSAGE":"ok"}]</E_OUTPUT>'

        def raise_for_status(self):
            return None

    def fake_post(url, data, headers, auth, verify, timeout):
        captured.update({"url": url, "auth": auth, "headers": headers, "verify": verify, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(module.requests, "post", fake_post)
    client = TestClient(module.app)

    response = client.post("/to_sap_prd", json={"parse_result": minimal_parse_result()})

    assert response.status_code == 200
    assert captured["url"] == "https://sap-prd"
    assert captured["auth"] == ("PRD_USER", "PRD_PASS")
    assert captured["verify"] == "/tmp/sap-prd.crt"
    assert response.json()["sap_status"]["type"] == "S"
