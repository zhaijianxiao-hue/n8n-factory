import importlib.util
import json
from pathlib import Path

import pytest


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
