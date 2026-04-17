"""
SOAP Body endpoint tests
测试 POST /prices/soap-body endpoint
"""

import pytest
import re
from fastapi.testclient import TestClient


def test_soap_body_endpoint_exists():
    """测试 POST /prices/soap-body endpoint存在"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    # Test with minimal valid input
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1000.0,
            "copper_price": 100000,
            "price_date": "2026-04-17"
        }
    )

    # Endpoint should exist (200 or 422 validation error, not 404)
    assert response.status_code != 404


def test_soap_body_xml_structure():
    """测试SOAP XML结构包含必要的SAP字段"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "soap_body" in data
    soap_body = data["soap_body"]
    
    # Verify SOAP envelope structure
    assert "<soapenv:Envelope" in soap_body
    assert 'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"' in soap_body
    assert 'xmlns:urn="urn:sap-com:document:sap:rfc:functions"' in soap_body
    assert "<soapenv:Header/>" in soap_body
    assert "<soapenv:Body>" in soap_body
    assert "</soapenv:Body>" in soap_body
    assert "</soapenv:Envelope>" in soap_body
    
    # Verify SAP-specific elements exist with correct function name
    assert "<urn:Z_FMBC_IF_INBOUND>" in soap_body
    assert "</urn:Z_FMBC_IF_INBOUND>" in soap_body
    
    # Verify I_DATA_GD wrapper element
    assert "<I_DATA_GD>" in soap_body
    assert "</I_DATA_GD>" in soap_body
    
    # Verify required fields inside I_DATA_GD
    assert "<GUID>" in soap_body
    assert "<BUTYPE>" in soap_body
    assert "<SYSID>" in soap_body
    assert "<HOST>" in soap_body
    assert "<IPADDR>" in soap_body
    assert "<USERID>" in soap_body
    assert "<UNAME>" in soap_body
    assert "<RDATE>" in soap_body
    assert "<RTIME>" in soap_body
    
    # Verify I_INPUT element for JSON payload
    assert "<I_INPUT>" in soap_body
    assert "</I_INPUT>" in soap_body
    
    # Verify JSON structure in I_INPUT
    assert '"GOLD"' in soap_body
    assert '"COPPER"' in soap_body


def test_soap_body_guid_format():
    """测试GUID为标准UUID格式xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    soap_body = data["soap_body"]
    
    # Extract GUID from XML
    guid_match = re.search(r"<GUID>([^<]+)</GUID>", soap_body)
    assert guid_match is not None
    
    guid = guid_match.group(1)
    
    # Verify UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(uuid_pattern, guid.lower()) is not None


def test_soap_body_copper_unit_conversion():
    """测试铜价单位转换：元/吨 → 万元（除10000，保留2位小数）"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    # Test with fixture data: copper_price=103300
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    soap_body = data["soap_body"]
    
    # Extract I_INPUT JSON from XML
    i_input_match = re.search(r"<I_INPUT>([^<]+)</I_INPUT>", soap_body)
    assert i_input_match is not None
    
    # Parse JSON from I_INPUT
    import json
    i_input_json = i_input_match.group(1)
    payload = json.loads(i_input_json)
    
    # Verify copper price conversion: 103300 / 10000 = 10.33
    assert "COPPER" in payload
    copper_price_output = float(payload["COPPER"])
    expected_copper = 10.33
    assert copper_price_output == expected_copper
    
    # Verify gold price is passed through
    assert "GOLD" in payload
    assert float(payload["GOLD"]) == 1057.9
    
    # Test edge case: exact decimal
    response2 = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1000.0,
            "copper_price": 98500,  # 98500 / 10000 = 9.85
            "price_date": "2026-04-17"
        }
    )
    
    data2 = response2.json()
    soap_body2 = data2["soap_body"]
    i_input_match2 = re.search(r"<I_INPUT>([^<]+)</I_INPUT>", soap_body2)
    payload2 = json.loads(i_input_match2.group(1))
    
    expected_copper2 = 9.85
    assert float(payload2["COPPER"]) == expected_copper2


def test_soap_body_fixed_fields():
    """测试固定字段值：BUTYPE=FI0056, SYSID/HOST/IPADDR/USERID/UNAME=n8n"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    soap_body = data["soap_body"]
    
    # Extract and verify fixed field values
    butype_match = re.search(r"<BUTYPE>([^<]+)</BUTYPE>", soap_body)
    assert butype_match is not None
    assert butype_match.group(1) == "FI0056"
    
    sysid_match = re.search(r"<SYSID>([^<]+)</SYSID>", soap_body)
    assert sysid_match is not None
    assert sysid_match.group(1) == "n8n"
    
    host_match = re.search(r"<HOST>([^<]+)</HOST>", soap_body)
    assert host_match is not None
    assert host_match.group(1) == "n8n"
    
    ipaddr_match = re.search(r"<IPADDR>([^<]+)</IPADDR>", soap_body)
    assert ipaddr_match is not None
    assert ipaddr_match.group(1) == "n8n"
    
    userid_match = re.search(r"<USERID>([^<]+)</USERID>", soap_body)
    assert userid_match is not None
    assert userid_match.group(1) == "n8n"
    
    uname_match = re.search(r"<UNAME>([^<]+)</UNAME>", soap_body)
    assert uname_match is not None
    assert uname_match.group(1) == "n8n"


def test_soap_body_rdate_format():
    """测试RDATE格式为YYYYMMDD"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    soap_body = data["soap_body"]
    
    # Extract RDATE from XML
    rdate_match = re.search(r"<RDATE>([^<]+)</RDATE>", soap_body)
    assert rdate_match is not None
    
    rdate = rdate_match.group(1)
    
    # Verify YYYYMMDD format (8 digits)
    assert len(rdate) == 8
    assert rdate.isdigit()
    assert rdate == "20260417"


def test_soap_body_rtime_format():
    """测试RTIME格式为HHMMSS"""
    from service.metal_price_service import app

    client = TestClient(app)
    
    response = client.post(
        "/prices/soap-body",
        json={
            "gold_price": 1057.9,
            "copper_price": 103300,
            "price_date": "2026-04-17"
        }
    )

    assert response.status_code == 200
    data = response.json()
    soap_body = data["soap_body"]
    
    # Extract RTIME from XML
    rtime_match = re.search(r"<RTIME>([^<]+)</RTIME>", soap_body)
    assert rtime_match is not None
    
    rtime = rtime_match.group(1)
    
    # Verify HHMMSS format (6 digits)
    assert len(rtime) == 6
    assert rtime.isdigit()
    
    # Verify valid time range (000000-235959)
    hour = int(rtime[:2])
    assert 0 <= hour <= 23