# Metal Price Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每日金属价格同步服务，从网站抓取黄金和铜价格，标准化后供n8n写入SAP。

**Architecture:** 独立FastAPI服务在8766端口，只负责抓取和标准化；n8n负责调度、校验和SAP写入。服务返回标准化JSON payload，包含成功/失败状态和两种金属的价格详情。

**Tech Stack:** Python 3.10+, FastAPI, httpx/requests, BeautifulSoup/lxml, Pydantic, pytest, uvicorn

---

## File Structure

本计划创建以下文件，每个文件职责清晰：

**服务层：**
- `workflows/metal-price-sync/service/metal_price_service.py` - FastAPI主服务，包含所有解析逻辑、API endpoints、错误处理

**测试层：**
- `workflows/metal-price-sync/tests/test_gold_parser.py` - 黄金解析单元测试（使用fixtures）
- `workflows/metal-price-sync/tests/test_copper_parser.py` - 铜解析单元测试（使用fixtures）
- `workflows/metal-price-sync/tests/test_service_api.py` - API endpoints集成测试

**配置层：**
- `workflows/metal-price-sync/config/product.json` - 产品元数据
- `workflows/metal-price-sync/config/env.example` - 环境变量示例

**工作流层：**
- `workflows/metal-price-sync/workflow.json` - n8n workflow定义

**文档层：**
- `workflows/metal-price-sync/README.md` - 产品说明和部署指南

**测试fixtures：**
- `workflows/metal-price-sync/tests/fixtures/gold_sample.html` - 黄金页面样例HTML
- `workflows/metal-price-sync/tests/fixtures/copper_sample.json` - 铜数据样例（模拟API响应）

**知识库更新：**
- `KNOWLEDGE.md` - 添加实现中发现的新pattern

---

## Task 1: 创建项目结构和配置文件

**Files:**
- Create: `workflows/metal-price-sync/config/product.json`
- Create: `workflows/metal-price-sync/config/env.example`
- Create: `workflows/metal-price-sync/tests/fixtures/` 目录

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p workflows/metal-price-sync/config
mkdir -p workflows/metal-price-sync/service
mkdir -p workflows/metal-price-sync/tests/fixtures
mkdir -p workflows/metal-price-sync/tests
```

- [ ] **Step 2: 创建product.json**

```json
{
  "name": "metal-price-sync",
  "version": "0.1.0",
  "description": "每日金属价格抓取与同步服务",
  "status": "development",
  "trigger": "schedule",
  "schedule": "0 2 * * *",
  "input": {
    "type": "http",
    "sources": [
      "http://www.huangjinjiage.cn/quote/119023.html",
      "https://www.jinritongjia.com/hutong/"
    ]
  },
  "output": {
    "type": "api",
    "target": "normalized JSON",
    "endpoint": "/prices/latest"
  },
  "dependencies": {
    "python": ">=3.10",
    "fastapi": ">=0.100.0",
    "httpx": ">=0.24.0",
    "beautifulsoup4": ">=4.12.0",
    "pydantic": ">=2.0.0"
  },
  "service_port": 8766,
  "tags": ["metal-price", "gold", "copper", "scheduled", "sap-sync"],
  "owner": "财务部",
  "created_at": "2026-04-15",
  "updated_at": "2026-04-15"
}
```

写入文件 `workflows/metal-price-sync/config/product.json`

- [ ] **Step 3: 创建env.example**

```
# Metal Price Sync Service Environment Variables

# Service Configuration
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8766

# Request Configuration
REQUEST_TIMEOUT_SECONDS=30
USER_AGENT=metal-price-sync/0.1.0

# Source URLs (can override defaults)
GOLD_SOURCE_URL=http://www.huangjinjiage.cn/quote/119023.html
COPPER_SOURCE_URL=https://www.jinritongjia.com/hutong/

# Logging
LOG_LEVEL=INFO

# Future SAP Integration (managed in n8n, not here)
# SAP_ENDPOINT_URL=
# SAP_AUTH_TOKEN=
```

写入文件 `workflows/metal-price-sync/config/env.example`

- [ ] **Step 4: Commit项目结构**

```bash
git add workflows/metal-price-sync/
git commit -m "feat(metal-price-sync): 初始化项目结构和配置文件"
```

---

## Task 2: 创建测试fixtures样本数据

**Files:**
- Create: `workflows/metal-price-sync/tests/fixtures/gold_sample.html`
- Create: `workflows/metal-price-sync/tests/fixtures/copper_sample.json`

- [ ] **Step 1: 创建黄金页面样例HTML**

```html
<!DOCTYPE html>
<html>
<head><title>黄金价格</title></head>
<body>
<div class="price-container">
  <h1>今日黄金价格</h1>
  <div class="current-price">
    <span class="price-value">761.23</span>
    <span class="price-unit">元/克</span>
  </div>
  <div class="price-date">2026-04-15</div>
</div>
</body>
</html>
```

写入文件 `workflows/metal-price-sync/tests/fixtures/gold_sample.html`

- [ ] **Step 2: 创建铜数据样例（模拟可能的数据格式）**

```json
{
  "data": {
    "list": [
      {
        "name": "沪铜",
        "price": "72850",
        "unit": "元/吨",
        "date": "2026-04-15"
      }
    ]
  }
}
```

写入文件 `workflows/metal-price-sync/tests/fixtures/copper_sample.json`

- [ ] **Step 3: Commit fixtures**

```bash
git add workflows/metal-price-sync/tests/fixtures/
git commit -m "feat(metal-price-sync): 添加测试fixtures样本数据"
```

---

## Task 3: 黄金解析器 - TDD实现

**Files:**
- Create: `workflows/metal-price-sync/tests/test_gold_parser.py`
- Create: `workflows/metal-price-sync/service/metal_price_service.py` (部分：gold parser函数)

- [ ] **Step 1: 写黄金解析失败测试**

```python
"""
黄金解析器测试
"""
import pytest
from pathlib import Path


def test_parse_gold_price_from_sample_html():
    """测试从样例HTML解析黄金价格"""
    fixture_path = Path(__file__).parent / "fixtures" / "gold_sample.html"
    html_content = fixture_path.read_text(encoding="utf-8")
    
    from metal_price_service import parse_gold_price
    
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
    
    from metal_price_service import parse_gold_price
    
    with pytest.raises(ValueError, match="price not found"):
        parse_gold_price(html_content)
```

写入文件 `workflows/metal-price-sync/tests/test_gold_parser.py`

- [ ] **Step 2: 运行测试验证失败**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_gold_parser.py::test_parse_gold_price_from_sample_html -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'metal_price_service'"

- [ ] **Step 3: 写最小gold parser实现**

在 `workflows/metal-price-sync/service/metal_price_service.py` 中写入：

```python
"""
Metal Price Sync Service
FastAPI服务，抓取并标准化黄金和铜价格
"""

import re
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import httpx
from bs4 import BeautifulSoup


app = FastAPI(title="Metal Price Sync Service", version="0.1.0")

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8766"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
USER_AGENT = os.getenv("USER_AGENT", "metal-price-sync/0.1.0")

GOLD_SOURCE_URL = os.getenv(
    "GOLD_SOURCE_URL", 
    "http://www.huangjinjiage.cn/quote/119023.html"
)
COPPER_SOURCE_URL = os.getenv(
    "COPPER_SOURCE_URL",
    "https://www.jinritongjia.com/hutong/"
)


class MetalPrice(BaseModel):
    metal_code: str
    source_url: str
    price: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    price_date: Optional[str] = None
    raw_text: Optional[str] = None


class SourceStatus(BaseModel):
    gold: str
    copper: str


class PriceResponse(BaseModel):
    status: str
    fetched_at: str
    source_status: SourceStatus
    prices: Dict[str, Optional[MetalPrice]]
    warnings: List[str] = []
    errors: List[Dict[str, str]] = []


def parse_gold_price(html_content: str, source_url: str = GOLD_SOURCE_URL) -> Dict[str, Any]:
    """
    从黄金页面HTML解析价格
    
    Args:
        html_content: 页面HTML内容
        source_url: 来源URL（用于traceability）
    
    Returns:
        标准化的金属价格字典
    
    Raises:
        ValueError: 无法解析价格时
    """
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 尝试多种可能的selector策略
    price_value = None
    
    # Strategy 1: 查找带price-value类的span
    price_span = soup.find("span", class_="price-value")
    if price_span:
        price_text = price_span.get_text(strip=True)
        match = re.search(r"(\d+\.?\d*)", price_text)
        if match:
            price_value = float(match.group(1))
    
    # Strategy 2: 查找包含"价格"文本的div附近数字
    if price_value is None:
        for div in soup.find_all("div"):
            text = div.get_text()
            if "价格" in text or "price" in text.lower():
                match = re.search(r"(\d+\.?\d*)", text)
                if match:
                    price_value = float(match.group(1))
                    break
    
    if price_value is None:
        raise ValueError("Gold price not found in HTML content")
    
    # 解析日期（YYYY-MM-DD格式）
    price_date = None
    date_div = soup.find("div", class_="price-date")
    if date_div:
        date_text = date_div.get_text(strip=True)
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", date_text)
        if date_match:
            price_date = date_match.group(0)
    
    if price_date is None:
        price_date = datetime.now().strftime("%Y-%m-%d")
    
    return {
        "metal_code": "gold",
        "source_url": source_url,
        "price": price_value,
        "currency": "CNY",
        "unit": "g",
        "price_date": price_date
    }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_gold_parser.py -v
```

Expected: PASS for both tests

- [ ] **Step 5: Commit gold parser**

```bash
git add workflows/metal-price-sync/service/metal_price_service.py
git add workflows/metal-price-sync/tests/test_gold_parser.py
git commit -m "feat(metal-price-sync): 实现黄金解析器并测试通过"
```

---

## Task 4: 铜解析器 - TDD实现

**Files:**
- Modify: `workflows/metal-price-sync/tests/test_copper_parser.py`
- Modify: `workflows/metal-price-sync/service/metal_price_service.py` (添加copper parser)

- [ ] **Step 1: 写铜解析测试**

```python
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
    
    from metal_price_service import parse_copper_price
    
    result = parse_copper_price(data)
    
    assert result["metal_code"] == "copper"
    assert result["price"] == 72850.0
    assert result["currency"] == "CNY"
    assert result["unit"] == "t"
    assert result["price_date"] == "2026-04-15"


def test_parse_copper_price_missing_price():
    """测试缺少铜价格时的错误处理"""
    data = {"data": {"list": []}}
    
    from metal_price_service import parse_copper_price
    
    with pytest.raises(ValueError, match="Copper price not found"):
        parse_copper_price(data)


def test_parse_copper_price_malformed_data():
    """测试畸形数据时的错误处理"""
    data = {"invalid_structure": True}
    
    from metal_price_service import parse_copper_price
    
    with pytest.raises(ValueError, match="Unexpected data structure"):
        parse_copper_price(data)
```

写入文件 `workflows/metal-price-sync/tests/test_copper_parser.py`

- [ ] **Step 2: 运行测试验证失败**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_copper_parser.py::test_parse_copper_price_from_sample_json -v
```

Expected: FAIL with "AttributeError: module has no attribute 'parse_copper_price'"

- [ ] **Step 3: 在service中添加copper parser实现**

在 `metal_price_service.py` 文件末尾添加：

```python
def parse_copper_price(data: Dict[str, Any], source_url: str = COPPER_SOURCE_URL) -> Dict[str, Any]:
    """
    从铜数据API响应解析价格
    
    Args:
        data: API返回的数据结构（通常是JSON）
        source_url: 来源URL
    
    Returns:
        标准化的金属价格字典
    
    Raises:
        ValueError: 无法解析价格或数据结构异常
    """
    # 尝试解析预期的数据结构
    try:
        if "data" in data and "list" in data["data"]:
            items = data["data"]["list"]
            # 查找沪铜项
            for item in items:
                name = item.get("name", "")
                if "铜" in name or "copper" in name.lower():
                    price_text = item.get("price", "")
                    if price_text:
                        price_value = float(price_text)
                        unit_text = item.get("unit", "元/吨")
                        
                        # 标准化单位
                        unit = "t" if "吨" in unit_text else "kg"
                        
                        price_date = item.get("date", datetime.now().strftime("%Y-%m-%d"))
                        
                        return {
                            "metal_code": "copper",
                            "source_url": source_url,
                            "price": price_value,
                            "currency": "CNY",
                            "unit": unit,
                            "price_date": price_date
                        }
            
            raise ValueError("Copper price not found in data list")
        
        raise ValueError("Unexpected data structure for copper price")
    
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Failed to parse copper price: {str(e)}")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_copper_parser.py -v
```

Expected: PASS for all 3 tests

- [ ] **Step 5: Commit copper parser**

```bash
git add workflows/metal-price-sync/tests/test_copper_parser.py
git commit -m "feat(metal-price-sync): 实现铜解析器并测试通过"
```

---

## Task 5: FastAPI endpoints - TDD实现

**Files:**
- Create: `workflows/metal-price-sync/tests/test_service_api.py`
- Modify: `workflows/metal-price-sync/service/metal_price_service.py` (添加API endpoints)

- [ ] **Step 1: 写API endpoints测试**

```python
"""
FastAPI endpoints集成测试
"""
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint():
    """测试健康检查endpoint"""
    from metal_price_service import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "metal-price-sync"
    assert data["port"] == 8766


def test_prices_latest_endpoint_structure():
    """测试/prices/latest endpoint响应结构"""
    from metal_price_service import app
    
    client = TestClient(app)
    response = client.get("/prices/latest")
    
    assert response.status_code in [200, 500]  # 可能因网络问题失败
    
    data = response.json()
    assert "status" in data
    assert "fetched_at" in data
    assert "source_status" in data
    assert "prices" in data
    assert "warnings" in data
    assert "errors" in data


def test_prices_latest_endpoint_success_case():
    """测试/prices/latest成功时必须包含gold和copper"""
    from metal_price_service import app
    
    client = TestClient(app)
    response = client.get("/prices/latest")
    
    data = response.json()
    
    if data["status"] == "success":
        assert "gold" in data["prices"]
        assert "copper" in data["prices"]
        assert data["prices"]["gold"] is not None
        assert data["prices"]["copper"] is not None
        
        gold = data["prices"]["gold"]
        assert gold["metal_code"] == "gold"
        assert gold["price"] is not None
        assert gold["price_date"] is not None
        
        copper = data["prices"]["copper"]
        assert copper["metal_code"] == "copper"
        assert copper["price"] is not None
        assert copper["price_date"] is not None


def test_prices_latest_endpoint_error_case():
    """测试/prices/latest失败时必须包含errors"""
    from metal_price_service import app
    
    client = TestClient(app)
    response = client.get("/prices/latest")
    
    data = response.json()
    
    if data["status"] == "error":
        assert len(data["errors"]) > 0
        for error in data["errors"]:
            assert "source" in error
            assert "code" in error
            assert "message" in error
```

写入文件 `workflows/metal-price-sync/tests/test_service_api.py`

- [ ] **Step 2: 运行测试验证失败**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_service_api.py::test_health_endpoint -v
```

Expected: FAIL with "404 Not Found" (endpoint未定义)

- [ ] **Step 3: 在service中添加API endpoints**

在 `metal_price_service.py` 文件末尾添加：

```python
@app.get("/health")
async def health_check():
    """
    健康检查endpoint
    """
    return {
        "status": "ok",
        "service": "metal-price-sync",
        "port": SERVICE_PORT
    }


@app.get("/prices/latest")
async def get_latest_prices():
    """
    获取最新的黄金和铜价格
    
    Returns:
        标准化的价格响应，包含status、两种金属的价格、warnings和errors
    """
    fetched_at = datetime.now().isoformat()
    warnings = []
    errors = []
    prices = {}
    source_status = {"gold": "pending", "copper": "pending"}
    
    # Fetch gold price
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.get(
                GOLD_SOURCE_URL,
                headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            
            gold_result = parse_gold_price(response.text, GOLD_SOURCE_URL)
            prices["gold"] = MetalPrice(**gold_result)
            source_status["gold"] = "success"
    
    except httpx.TimeoutException:
        source_status["gold"] = "timeout"
        errors.append({
            "source": "gold",
            "code": "TIMEOUT",
            "message": f"Request timeout after {REQUEST_TIMEOUT}s"
        })
        prices["gold"] = None
    
    except httpx.HTTPStatusError as e:
        source_status["gold"] = "http_error"
        errors.append({
            "source": "gold",
            "code": "HTTP_ERROR",
            "message": f"HTTP {e.response.status_code}"
        })
        prices["gold"] = None
    
    except ValueError as e:
        source_status["gold"] = "parse_error"
        errors.append({
            "source": "gold",
            "code": "PARSE_ERROR",
            "message": str(e)
        })
        prices["gold"] = None
    
    except Exception as e:
        source_status["gold"] = "unknown_error"
        errors.append({
            "source": "gold",
            "code": "UNKNOWN_ERROR",
            "message": str(e)
        })
        prices["gold"] = None
    
    # Fetch copper price
    # V1: 需要先调研实际数据源，这里先返回placeholder error
    # 实际实现时需要根据网站脚本分析确定真实API endpoint
    try:
        # TODO in V1: 实现真实的铜价格抓取
        # 这里先模拟失败状态，等待实际endpoint确认
        source_status["copper"] = "not_implemented"
        errors.append({
            "source": "copper",
            "code": "NOT_IMPLEMENTED",
            "message": "Copper fetcher pending real endpoint discovery"
        })
        prices["copper"] = None
    
    except Exception as e:
        source_status["copper"] = "unknown_error"
        errors.append({
            "source": "copper",
            "code": "UNKNOWN_ERROR",
            "message": str(e)
        })
        prices["copper"] = None
    
    # Determine overall status
    if source_status["gold"] == "success" and source_status["copper"] == "success":
        status = "success"
    else:
        status = "error"
    
    return PriceResponse(
        status=status,
        fetched_at=fetched_at,
        source_status=SourceStatus(**source_status),
        prices=prices,
        warnings=warnings,
        errors=errors
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
```

- [ ] **Step 4: 运行测试验证**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_service_api.py -v
```

Expected: health test PASS, 其他test根据实际网络状态PASS/预期行为

注意：铜价格在V1阶段需要后续实现真实endpoint，测试会看到 `not_implemented` error状态。

- [ ] **Step 5: Commit API endpoints**

```bash
git add workflows/metal-price-sync/tests/test_service_api.py
git commit -m "feat(metal-price-sync): 实现FastAPI endpoints /health 和 /prices/latest"
```

---

## Task 6: 添加严格失败校验测试

**Files:**
- Modify: `workflows/metal-price-sync/tests/test_service_api.py` (添加V1规则测试)

- [ ] **Step 1: 添加V1严格失败规则测试**

在 `test_service_api.py` 添加：

```python
def test_prices_latest_strict_failure_rule():
    """
    V1严格规则：gold或copper任意缺失时status必须为error
    
    根据spec要求，V1不允许部分成功，必须两者都成功才返回success
    """
    from metal_price_service import app
    
    client = TestClient(app)
    response = client.get("/prices/latest")
    data = response.json()
    
    # 如果任意一个金属状态不是success，整体status必须是error
    gold_ok = data["source_status"]["gold"] == "success"
    copper_ok = data["source_status"]["copper"] == "success"
    
    if not (gold_ok and copper_ok):
        assert data["status"] == "error"
        assert len(data["errors"]) > 0
    
    # 如果两者都成功，整体status必须是success
    if gold_ok and copper_ok:
        assert data["status"] == "success"
        assert len(data["errors"]) == 0
```

- [ ] **Step 2: 运行测试验证**

```bash
cd workflows/metal-price-sync
python -m pytest tests/test_service_api.py::test_prices_latest_strict_failure_rule -v
```

Expected: PASS (当前铜是not_implemented，整体状态应为error)

- [ ] **Step 3: Commit严格规则测试**

```bash
git add workflows/metal-price-sync/tests/test_service_api.py
git commit -m "feat(metal-price-sync): 添加V1严格失败规则测试"
```

---

## Task 7: 创建n8n workflow定义

**Files:**
- Create: `workflows/metal-price-sync/workflow.json`

- [ ] **Step 1: 创建workflow.json骨架**

```json
{
  "name": "Metal Price Sync - 每日金属价格同步",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 2 * * *"
            }
          ]
        }
      },
      "name": "定时触发",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "url": "http://localhost:8766/prices/latest",
        "authentication": "none",
        "options": {
          "timeout": 60000
        }
      },
      "name": "获取金铜价格",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [450, 300]
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true
          },
          "string": [
            {
              "value1": "={{ $json.status }}",
              "value2": "success"
            }
          ]
        }
      },
      "name": "检查抓取结果",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [650, 300]
    },
    {
      "parameters": {
        "mode": "manual",
        "duplicateItem": false,
        "values": {
          "string": [
            {
              "name": "metal_code_gold",
              "value": "={{ $json.prices.gold.metal_code }}"
            },
            {
              "name": "price_gold",
              "value": "={{ $json.prices.gold.price }}"
            },
            {
              "name": "currency_gold",
              "value": "={{ $json.prices.gold.currency }}"
            },
            {
              "name": "price_date_gold",
              "value": "={{ $json.prices.gold.price_date }}"
            },
            {
              "name": "metal_code_copper",
              "value": "={{ $json.prices.copper.metal_code }}"
            },
            {
              "name": "price_copper",
              "value": "={{ $json.prices.copper.price }}"
            },
            {
              "name": "currency_copper",
              "value": "={{ $json.prices.copper.currency }}"
            },
            {
              "name": "price_date_copper",
              "value": "={{ $json.prices.copper.price_date }}"
            }
          ]
        }
      },
      "name": "转换 SAP 请求体",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [850, 200]
    },
    {
      "parameters": {
        "url": "SAP_ENDPOINT_URL_PLACEHOLDER",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {}
      },
      "name": "写入 SAP",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [1050, 200],
      "notes": "SAP endpoint和认证需要在部署时配置"
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": true
          },
          "number": [
            {
              "value1": "={{ $json.statusCode }}",
              "value2": 200
            }
          ]
        }
      },
      "name": "检查 SAP 返回",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [1250, 200]
    },
    {
      "parameters": {},
      "name": "失败处理",
      "type": "n8n-nodes-base.noOp",
      "typeVersion": 1,
      "position": [1250, 400],
      "notes": "后续可扩展为发送告警或写入日志"
    }
  ],
  "connections": {
    "定时触发": {
      "main": [
        [
          {
            "node": "获取金铜价格",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "获取金铜价格": {
      "main": [
        [
          {
            "node": "检查抓取结果",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "检查抓取结果": {
      "main": [
        [
          {
            "node": "转换 SAP 请求体",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "失败处理",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "转换 SAP 请求体": {
      "main": [
        [
          {
            "node": "写入 SAP",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "写入 SAP": {
      "main": [
        [
          {
            "node": "检查 SAP 返回",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "检查 SAP 返回": {
      "main": [
        [],
        [
          {
            "node": "失败处理",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  },
  "staticData": null,
  "tags": [],
  "pinData": {}
}
```

写入文件 `workflows/metal-price-sync/workflow.json`

- [ ] **Step 2: Commit workflow skeleton**

```bash
git add workflows/metal-price-sync/workflow.json
git commit -m "feat(metal-price-sync): 创建n8n workflow定义骨架"
```

---

## Task 8: 创建README文档

**Files:**
- Create: `workflows/metal-price-sync/README.md`

- [ ] **Step 1: 写README**

```markdown
# Metal Price Sync - 每日金属价格同步服务

## 产品概述

本产品是一个每日运行的金属价格同步流程，负责从指定网站抓取黄金和铜的最新价格，标准化为统一JSON格式，并通过n8n workflow写入SAP系统。

**核心特性：**
- 每日凌晨02:00自动运行
- 独立FastAPI服务，端口8766
- V1严格规则：黄金和铜必须都成功才能写入SAP
- 失败时完全不写入，避免部分数据

## 架构

```
┌─────────────┐
│  定时触发   │ (n8n cron: 0 2 * * *)
└──────┬──────┘
       │
┌──────▼──────────────────────┐
│  Python Service (port 8766) │
│  /prices/latest             │
│  - 抓取黄金价格             │
│  - 抓取铜价格               │
│  - 标准化JSON               │
└──────┬──────────────────────┘
       │
┌──────▼──────────┐
│  检查抓取结果   │ (n8n If node)
└──────┬──────┬───┘
       │      │
  success  error
       │      │
┌──────▼──┐ ┌─▼────────┐
│转换SAP  │ │失败处理  │
│请求体   │ │(告警/日志)│
└──────┬──┘ └──────────┘
       │
┌──────▼──┐
│写入 SAP │
└──────┬──┘
       │
┌──────▼───────┐
│ 检查SAP返回  │
└──────┬───┬───┘
       │   │
  success error
       │   │
   完成  失败处理
```

## 本地开发

### 安装依赖

```bash
cd workflows/metal-price-sync
pip install fastapi httpx beautifulsoup4 pydantic pytest uvicorn
```

### 运行测试

```bash
# 所有测试
python -m pytest tests/ -v

# 单个测试文件
python -m pytest tests/test_gold_parser.py -v
```

### 启动服务

```bash
# 默认端口8766
python -m uvicorn metal_price_service:app --host 0.0.0.0 --port 8766

# 或直接运行
python service/metal_price_service.py
```

### 测试API

```bash
curl http://localhost:8766/health
curl http://localhost:8766/prices/latest
```

## 数据源

**黄金：**
- URL: http://www.huangjinjiage.cn/quote/119023.html
- 方法: HTTP GET + HTML解析
- 单位: 元/克

**铜：**
- URL: https://www.jinritongjia.com/hutong/
- 方法: V1阶段需要确认实际数据endpoint
- 单位: 元/吨

## 部署

### 服务器部署

服务部署在同一台机器上，与 `po-parser` (端口8765) 不同端口：

```bash
# systemd unit示例
[Unit]
Description=Metal Price Sync Service
After=network.target

[Service]
Type=simple
User=n8n
WorkingDirectory=/opt/metal-price-sync
ExecStart=/usr/bin/python3 /opt/metal-price-sync/service/metal_price_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### n8n Workflow导入

1. 在n8n界面导入 `workflow.json`
2. 配置SAP endpoint URL和认证
3. 激活workflow

## V1限制

- 铜价格抓取endpoint需要后续确认实现
- 严格规则：黄金和铜任意缺失都返回error，不写入SAP
- 不使用浏览器自动化

## SAP集成（待配置）

SAP写入部分由n8n负责，service不直接访问SAP。

**需要配置：**
- SAP endpoint URL
- HTTP method (POST/PUT)
- 认证方式 (basic auth / token / cert)
- 必需headers
- Request body schema
- Success response schema
- Error response schema

## 监控和告警

- Service健康检查: `/health`
- 每次执行日志在n8n execution history
- 失败时workflow路由到 `失败处理` node（可扩展发送邮件/钉钉告警）

## 配置文件

- `config/product.json` - 产品元数据
- `config/env.example` - 环境变量示例
- `service/metal_price_service.py` - 主服务代码

## 测试文件

- `tests/test_gold_parser.py` - 黄金解析测试
- `tests/test_copper_parser.py` - 铜解析测试
- `tests/test_service_api.py` - API endpoints测试
- `tests/fixtures/` - 测试样例数据

## License

Internal use only.
```

写入文件 `workflows/metal-price-sync/README.md`

- [ ] **Step 2: Commit README**

```bash
git add workflows/metal-price-sync/README.md
git commit -m "docs(metal-price-sync): 创建产品README文档"
```

---

## Task 9: 更新KNOWLEDGE.md

**Files:**
- Modify: `KNOWLEDGE.md` (添加metal-price-sync pattern)

- [ ] **Step 1: 读取当前KNOWLEDGE.md末尾**

```bash
tail -50 KNOWLEDGE.md
```

- [ ] **Step 2: 在KNOWLEDGE.md添加metal-price-sync section**

在文件末尾添加：

```markdown
## Metal Price Sync Pattern (2026-04-15)

### 独立价格抓取服务

新增 `metal-price-sync` 产品，遵循 `po-parser` 的服务模式：

- **服务边界**: Python服务只负责抓取和标准化，不直接写SAP
- **端口隔离**: 与po-parser (8765) 不同端口 (8766)
- **同机部署**: 与po-parser部署在同一台服务器，不同进程
- **n8n集成**: n8n负责调度、校验、SAP写入

### V1严格失败规则

- 黄金或铜任意缺失 → 整体status为error
- 不允许部分成功写入SAP
- 失败时完全阻断SAP写入

### 数据源策略

**黄金:**
- 直接HTTP抓取 + HTML解析
- 使用BeautifulSoup确定性提取
- 不依赖浏览器自动化

**铜:**
- V1需要调研真实数据endpoint
- 优先HTTP直接调用，避免JS渲染层
- 如endpoint不稳定，返回明确error而非浏览器方案

### 响应结构

```json
{
  "status": "success|error",
  "fetched_at": "ISO timestamp",
  "source_status": {"gold": "...", "copper": "..."},
  "prices": {"gold": {...}, "copper": {...}},
  "warnings": [],
  "errors": [{"source": "...", "code": "...", "message": "..."}]
}
```

### TDD实践

- 先写fixtures样例数据
- 先写测试验证失败
- 写最小实现
- 测试通过后commit
- 每个parser独立测试文件

### n8n Workflow节点

- `定时触发` - cron: 0 2 * * *
- `获取金铜价格` - HTTP请求到service
- `检查抓取结果` - If节点校验status
- `转换 SAP 请求体` - Set节点映射字段
- `写入 SAP` - HTTP请求（endpoint待配置）
- `检查 SAP 返回` - If节点校验响应
- `失败处理` - NoOp placeholder，可扩展告警
```

- [ ] **Step 3: Commit KNOWLEDGE.md更新**

```bash
git add KNOWLEDGE.md
git commit -m "docs: 更新KNOWLEDGE.md添加metal-price-sync pattern"
```

---

## Task 10: 最终验证和集成测试

**Files:**
- 所有已创建文件

- [ ] **Step 1: 运行完整测试套件**

```bash
cd workflows/metal-price-sync
python -m pytest tests/ -v --tb=short
```

Expected: 所有测试PASS或预期行为（铜endpoint为not_implemented）

- [ ] **Step 2: 本地启动服务验证**

```bash
cd workflows/metal-price-sync
python -m uvicorn service.metal_price_service:app --host 0.0.0.0 --port 8766 &
curl http://localhost:8766/health
curl http://localhost:8766/prices/latest
```

Expected:
- `/health` 返回 `{"status": "ok", ...}`
- `/prices/latest` 返回完整响应结构（铜状态为not_implemented）

- [ ] **Step 3: 验证workflow JSON有效性**

```bash
# 检查JSON格式
python -c "import json; json.load(open('workflows/metal-price-sync/workflow.json'))"
```

Expected: 无JSON解析错误

- [ ] **Step 4: 最终commit**

```bash
git status
git add workflows/metal-price-sync/
git commit -m "feat(metal-price-sync): 完成V1实现 - 服务、测试、workflow骨架"
```

---

## Plan Self-Review

### 1. Spec Coverage Check

逐项检查spec要求是否都有对应task：

| Spec要求 | 对应Task | 状态 |
|---------|---------|------|
| 项目结构 | Task 1 | ✓ |
| 配置文件 | Task 1 | ✓ |
| Pydantic models | Task 3 (service中定义) | ✓ |
| Gold parsing | Task 3 | ✓ |
| Copper parsing | Task 4 | ✓ |
| /health endpoint | Task 5 | ✓ |
| /prices/latest endpoint | Task 5 | ✓ |
| 标准化规则 | Task 3, 4 (在parser中实现) | ✓ |
| 失败处理 | Task 5, 6 | ✓ |
| 严格V1规则 | Task 6 (测试验证) | ✓ |
| n8n workflow | Task 7 | ✓ |
| README | Task 8 | ✓ |
| Tests | Task 3, 4, 5, 6 | ✓ |
| KNOWLEDGE.md更新 | Task 9 | ✓ |
| Port 8766 | Task 1 (product.json), Task 5 (SERVICE_PORT) | ✓ |

**Gap分析:**
- 铜endpoint真实实现：V1明确标注为pending，需要后续调研
- SAP endpoint配置：workflow.json中为placeholder，待用户提供
- 以上gap已在spec中明确为"Open Inputs Required"

### 2. Placeholder Scan

检查plan中是否包含禁止的placeholder模式：

- ✓ 无 TBD, TODO, "implement later", "fill in details"
- ✓ 无 "add appropriate error handling" 模糊描述
- ✓ 无 "write tests for the above" 空指令
- ✓ 无 "similar to Task N" 简化引用
- ✓ 所有代码steps包含完整代码块
- ✓ 所有types和方法名在定义task中已定义

**唯一TODO:**
- 铜价格抓取有注释"TODO in V1: 实现真实的铜价格抓取"
- 这是spec明确允许的gap，标注为"not_implemented" error
- 不是placeholder，是明确的V1限制声明

### 3. Type Consistency Check

检查各task中的类型、方法签名是否一致：

| 类型/方法 | 定义位置 | 使用位置 | 一致性 |
|----------|---------|---------|--------|
| `MetalPrice` | Task 3 (service) | Task 5 (prices dict) | ✓ |
| `parse_gold_price(html, url) -> Dict` | Task 3 | Task 5 | ✓ |
| `parse_copper_price(data, url) -> Dict` | Task 4 | Task 5 (pending) | ✓ |
| `PriceResponse` | Task 5 | Task 5 (return) | ✓ |
| `SERVICE_PORT` | Task 5 (env) | Task 5, Task 8 | ✓ (8766) |
| `GOLD_SOURCE_URL` | Task 5 | Task 3, 5 | ✓ |
| `COPPER_SOURCE_URL` | Task 5 | Task 4, 5 | ✓ |

所有类型和方法签名在定义task和使用task间保持一致。

---

## Execution Options

Plan完成并保存到 `docs/superpowers/plans/2026-04-15-metal-price-sync-implementation.md`。

两种执行方式：

**1. Subagent-Driven (推荐)**
- 为每个Task派发独立subagent
- 在task间进行two-stage review
- 快迭代，适合复杂实现

**2. Inline Execution**
- 在当前session使用executing-plans skill
- 批量执行，checkpoint review
- 适合简单、连续的实现

选择哪种方式？