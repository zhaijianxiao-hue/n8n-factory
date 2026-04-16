"""
黄金解析器测试
"""

import pytest
from pathlib import Path


def test_parse_gold_price_from_sample_html():
    """测试从样例HTML解析黄金价格"""
    fixture_path = Path(__file__).parent / "fixtures" / "gold_sample.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    from service.metal_price_service import parse_gold_price

    result = parse_gold_price(html_content)

    assert result["metal_code"] == "gold"
    assert result["price"] == 761.23
    assert result["currency"] == "CNY"
    assert result["unit"] == "g"
    assert result["price_date"] == "2026-04-15"
    assert "source_url" in result


def test_parse_gold_price_missing_price_field():
    """测试缺少价格字段时的错误处理"""
    html_content = "<html><body><div>无价格信息</div></body></html>"

    from service.metal_price_service import parse_gold_price

    with pytest.raises(ValueError, match="price not found"):
        parse_gold_price(html_content)
