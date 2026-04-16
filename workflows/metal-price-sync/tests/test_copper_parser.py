"""
铜解析器测试
"""

import pytest
import json
from pathlib import Path


def test_parse_copper_price_from_sample_js():
    """测试从样例JS解析铜价格"""
    fixture_path = Path(__file__).parent / "fixtures" / "copper_sample.js"
    js_content = fixture_path.read_text(encoding="utf-8")

    from service.metal_price_service import parse_copper_price

    result = parse_copper_price(js_content)

    assert result["metal_code"] == "copper"
    assert result["price"] == 102720.0
    assert result["currency"] == "CNY"
    assert result["unit"] == "t"
    assert result["price_date"] == "2026-04-16"


def test_parse_copper_price_missing_data():
    """测试缺少铜价格数据时的错误处理"""
    js_content = 'var hq_str_nf_AL0="铝连续,150000";'

    from service.metal_price_service import parse_copper_price

    with pytest.raises(ValueError, match="Copper price data not found"):
        parse_copper_price(js_content)


def test_parse_copper_price_malformed_data():
    """测试畸形数据时的错误处理"""
    js_content = 'var hq_str_nf_CU0="铜连续";'

    from service.metal_price_service import parse_copper_price

    with pytest.raises(ValueError, match="Insufficient copper price fields"):
        parse_copper_price(js_content)
