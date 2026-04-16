"""
铜解析器测试
"""

import pytest
import json
from pathlib import Path


def test_parse_copper_price_from_sample_json():
    """测试从样例JSON解析铜价格"""
    fixture_path = Path(__file__).parent / "fixtures" / "copper_sample.json"
    json_content = fixture_path.read_text(encoding="utf-8")
    data = json.loads(json_content)

    from service.metal_price_service import parse_copper_price_from_data

    result = parse_copper_price_from_data(data)

    assert result["metal_code"] == "copper"
    assert result["price"] == 72850.0
    assert result["currency"] == "CNY"
    assert result["unit"] == "t"
    assert result["price_date"] == "2026-04-15"


def test_parse_copper_price_missing_price():
    """测试缺少铜价格时的错误处理"""
    data = {"data": {"list": []}}

    from service.metal_price_service import parse_copper_price_from_data

    with pytest.raises(ValueError, match="Copper price not found"):
        parse_copper_price_from_data(data)


def test_parse_copper_price_malformed_data():
    """测试畸形数据时的错误处理"""
    data = {"invalid_structure": True}

    from service.metal_price_service import parse_copper_price_from_data

    with pytest.raises(ValueError, match="Unexpected data structure"):
        parse_copper_price_from_data(data)
