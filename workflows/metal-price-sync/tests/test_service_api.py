"""
FastAPI endpoints集成测试
"""

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint():
    """测试健康检查endpoint"""
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "metal-price-sync"
    assert data["port"] == 8766


def test_prices_latest_endpoint_structure():
    """测试/prices/latest endpoint响应结构"""
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/prices/latest")

    assert response.status_code in [200, 500]

    data = response.json()
    assert "status" in data
    assert "fetched_at" in data
    assert "source_status" in data
    assert "prices" in data
    assert "warnings" in data


def test_prices_latest_endpoint_has_gold_and_copper():
    """测试/prices/latest必须包含gold和copper"""
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/prices/latest")

    data = response.json()

    assert "gold" in data["prices"]
    assert "copper" in data["prices"]


def test_prices_latest_endpoint_gold_fields():
    """测试gold价格字段"""
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/prices/latest")

    data = response.json()

    if data["prices"]["gold"] is not None:
        gold = data["prices"]["gold"]
        assert gold["metal_code"] == "gold"
        assert "price" in gold
        assert "price_date" in gold


def test_prices_latest_endpoint_copper_fields():
    """测试copper价格字段"""
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/prices/latest")

    data = response.json()

    if data["prices"]["copper"] is not None:
        copper = data["prices"]["copper"]
        assert copper["metal_code"] == "copper"
        assert "price" in copper
        assert "price_date" in copper


def test_prices_latest_strict_failure_rule():
    """
    V1严格规则：gold或copper任意缺失时status必须为error

    根据spec要求，V1不允许部分成功，必须两者都成功才返回success
    """
    from service.metal_price_service import app

    client = TestClient(app)
    response = client.get("/prices/latest")
    data = response.json()

    gold_ok = data["source_status"]["gold"] == "success"
    copper_ok = data["source_status"]["copper"] == "success"

    if not (gold_ok and copper_ok):
        assert data["status"] == "error"

    if gold_ok and copper_ok:
        assert data["status"] == "success"
