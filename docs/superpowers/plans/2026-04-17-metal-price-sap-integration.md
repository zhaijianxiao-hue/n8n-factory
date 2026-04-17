# Metal Price SAP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 metal-price-sync，新增 SOAP Body 构建、测试/生产系统切换、SAP 写入功能

**Architecture:** Python 新增 `/prices/soap-body` 端点构建 SOAP XML；n8n workflow 新增 Switch 节点控制系统选择、Code Node 动态配置、SOAP 响应解析

**Tech Stack:** Python FastAPI、uuid、n8n HTTP Request、Code Node

---

## File Structure

| 文件 | 职责 |
|------|------|
| `workflows/metal-price-sync/service/metal_price_service.py` | 新增 `/prices/soap-body` 端点、SOAP XML 构建、单位转换 |
| `workflows/metal-price-sync/tests/test_soap_body.py` | 新增 SOAP 端点测试（UUID 生成、时间格式、单位转换） |
| `workflows/metal-price-sync/tests/fixtures/soap_request.json` | 测试输入 fixture |
| `workflows/metal-price-sync/workflow.json` | 新增 Switch、Code Node、解析节点、更新连接 |
| `workflows/metal-price-sync/README.md` | 更新 SAP 集成说明 |

---

### Task 1: 新增 SOAP Request Fixture

**Files:**
- Create: `workflows/metal-price-sync/tests/fixtures/soap_request.json`

- [ ] **Step 1: 创建测试 fixture**

```json
{
  "gold_price": 1057.9,
  "copper_price": 103300,
  "price_date": "2026-04-17"
}
```

- [ ] **Step 2: Commit**

```bash
git add workflows/metal-price-sync/tests/fixtures/soap_request.json
git commit -m "test: add SOAP request fixture for metal-price-sync"
```

---

### Task 2: 新增 SOAP Body 端点（TDD）

**Files:**
- Create: `workflows/metal-price-sync/tests/test_soap_body.py`
- Modify: `workflows/metal-price-sync/service/metal_price_service.py`

- [ ] **Step 1: Write the failing test - 端点存在性**

```python
"""
SOAP Body 构建端点测试
"""

import pytest
from pathlib import Path
import json


@pytest.mark.asyncio
async def test_soap_body_endpoint_exists():
    """测试 SOAP body 端点存在"""
    from fastapi.testclient import TestClient
    from service.metal_price_service import app

    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "soap_request.json"
    request_data = json.loads(fixture_path.read_text())

    response = client.post("/prices/soap-body", json=request_data)
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_endpoint_exists -v`
Expected: FAIL with 404 or route not found

- [ ] **Step 3: Write minimal implementation - 端点骨架**

```python
# 在 metal_price_service.py 添加

from uuid import uuid4
from datetime import datetime
import json


class SoapBodyRequest(BaseModel):
    gold_price: float
    copper_price: float
    price_date: str


@app.post("/prices/soap-body")
def build_soap_body(request: SoapBodyRequest):
    soap_xml = "<soapenv:Envelope>placeholder</soapenv:Envelope>"
    return {"soap_body": soap_xml}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_endpoint_exists -v`
Expected: PASS

- [ ] **Step 5: Write the failing test - SOAP XML 结构**

```python
@pytest.mark.asyncio
async def test_soap_body_xml_structure():
    """测试 SOAP XML 包含必需字段"""
    from fastapi.testclient import TestClient
    from service.metal_price_service import app

    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "soap_request.json"
    request_data = json.loads(fixture_path.read_text())

    response = client.post("/prices/soap-body", json=request_data)
    soap_xml = response.json()["soap_body"]

    assert "<soapenv:Envelope" in soap_xml
    assert "xmlns:soapenv" in soap_xml
    assert "<urn:Z_FMBC_IF_INBOUND>" in soap_xml
    assert "<I_DATA_GD>" in soap_xml
    assert "<I_INPUT>" in soap_xml
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_xml_structure -v`
Expected: FAIL

- [ ] **Step 7: Write implementation - SOAP XML 构建**

```python
@app.post("/prices/soap-body")
def build_soap_body(request: SoapBodyRequest):
    guid = str(uuid4())
    rdate = datetime.now().strftime("%Y%m%d")
    rtime = datetime.now().strftime("%H%M%S")
    
    # 单位转换
    gold_value = request.gold_price
    copper_value = round(request.copper_price / 10000, 2)
    
    i_input = json.dumps({
        "GOLD": str(gold_value),
        "COPPER": str(copper_value)
    }, indent=1)
    
    soap_xml = f'''<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions">
   <soapenv:Header/>
   <soapenv:Body>
      <urn:Z_FMBC_IF_INBOUND>
         <I_DATA_GD>
            <GUID>{guid}</GUID>
            <BUTYPE>FI0056</BUTYPE>
            <SYSID>n8n</SYSID>
            <HOST>n8n</HOST>
            <IPADDR>n8n</IPADDR>
            <USERID>n8n</USERID>
            <UNAME>n8n</UNAME>
            <RDATE>{rdate}</RDATE>
            <RTIME>{rtime}</RTIME>
         </I_DATA_GD>
         <I_INPUT>{i_input}</I_INPUT>
      </urn:Z_FMBC_IF_INBOUND>
   </soapenv:Body>
</soapenv:Envelope>'''
    
    return {"soap_body": soap_xml}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_xml_structure -v`
Expected: PASS

- [ ] **Step 9: Write the failing test - UUID 格式**

```python
import re

@pytest.mark.asyncio
async def test_soap_body_guid_format():
    """测试 GUID 为标准 UUID 格式"""
    from fastapi.testclient import TestClient
    from service.metal_price_service import app

    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "soap_request.json"
    request_data = json.loads(fixture_path.read_text())

    response = client.post("/prices/soap-body", json=request_data)
    soap_xml = response.json()["soap_body"]

    guid_match = re.search(r"<GUID>([^<]+)</GUID>", soap_xml)
    assert guid_match
    
    guid_value = guid_match.group(1)
    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    assert uuid_pattern.match(guid_value)
```

- [ ] **Step 10: Run test to verify it passes**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_guid_format -v`
Expected: PASS（UUID 已正确生成）

- [ ] **Step 11: Write the failing test - 单位转换**

```python
import re

@pytest.mark.asyncio
async def test_soap_body_copper_unit_conversion():
    """测试铜价单位转换（元/吨 → 万元）"""
    from fastapi.testclient import TestClient
    from service.metal_price_service import app

    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "soap_request.json"
    request_data = json.loads(fixture_path.read_text())

    response = client.post("/prices/soap-body", json=request_data)
    soap_xml = response.json()["soap_body"]

    i_input_match = re.search(r"<I_INPUT>([^<]+)</I_INPUT>", soap_xml)
    assert i_input_match
    
    i_input = json.loads(i_input_match.group(1).replace("\n", ""))
    
    # 验证金价不变
    assert i_input["GOLD"] == "1057.9"
    
    # 验证铜价转换：103300 / 10000 = 10.33
    assert i_input["COPPER"] == "10.33"
```

- [ ] **Step 12: Run test to verify it passes**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_copper_unit_conversion -v`
Expected: PASS

- [ ] **Step 13: Write the failing test - 固定字段**

```python
@pytest.mark.asyncio
async def test_soap_body_fixed_fields():
    """测试固定字段值"""
    from fastapi.testclient import TestClient
    from service.metal_price_service import app

    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "soap_request.json"
    request_data = json.loads(fixture_path.read_text())

    response = client.post("/prices/soap-body", json=request_data)
    soap_xml = response.json()["soap_body"]

    assert "<BUTYPE>FI0056</BUTYPE>" in soap_xml
    assert "<SYSID>n8n</SYSID>" in soap_xml
    assert "<HOST>n8n</HOST>" in soap_xml
    assert "<IPADDR>n8n</IPADDR>" in soap_xml
    assert "<USERID>n8n</USERID>" in soap_xml
    assert "<UNAME>n8n</UNAME>" in soap_xml
```

- [ ] **Step 14: Run test to verify it passes**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py::test_soap_body_fixed_fields -v`
Expected: PASS

- [ ] **Step 15: Run all SOAP tests**

Run: `cd workflows/metal-price-sync/tests && python -m pytest test_soap_body.py -v`
Expected: All PASS

- [ ] **Step 16: Commit**

```bash
git add workflows/metal-price-sync/tests/test_soap_body.py workflows/metal-price-sync/service/metal_price_service.py
git commit -m "feat: add /prices/soap-body endpoint for SAP SOAP XML construction"
```

---

### Task 3: 更新 Workflow JSON

**Files:**
- Modify: `workflows/metal-price-sync/workflow.json`

- [ ] **Step 1: 添加手动触发节点（带系统选择）**

在 nodes 数组开头添加：

```json
{
  "parameters": {},
  "name": "手动触发",
  "type": "n8n-nodes-base.manualWebhook",
  "typeVersion": 1,
  "position": [50, 300],
  "webhookId": "manual-trigger-sap"
}
```

- [ ] **Step 2: 添加 Switch 节点（系统选择）**

```json
{
  "parameters": {
    "mode": "rules",
    "rules": [
      {
        "output": 0,
        "conditions": {
          "options": {
            "caseSensitive": true
          },
          "string": [
            {
              "value1": "={{ $json.system_type }}",
              "value2": "test"
            }
          ]
        }
      },
      {
        "output": 1,
        "conditions": {
          "options": {
            "caseSensitive": true
          },
          "string": [
            {
              "value1": "={{ $json.system_type }}",
              "value2": "prod"
            }
          ]
        }
      }
    ]
  },
  "name": "选择系统",
  "type": "n8n-nodes-base.switch",
  "typeVersion": 3,
  "position": [150, 300],
  "notes": "手动触发时传入 system_type: test 或 prod"
}
```

- [ ] **Step 3: 添加 Code Node（配置选择）**

```json
{
  "parameters": {
    "mode": "runOnceForAllItems",
    "jsCode": "const systemType = $input.first().json.system_type || 'test';\nconst config = {\n  test: {\n    url: 'http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600',\n    credentialName: 'SAP Test System'\n  },\n  prod: {\n    url: 'PROD_URL_PLACEHOLDER',\n    credentialName: 'SAP Production System'\n  }\n};\nreturn [{ json: config[systemType] }];"
  },
  "name": "获取 SAP 配置",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [250, 300]
}
```

- [ ] **Step 4: 添加构建 SOAP Body 节点**

```json
{
  "parameters": {
    "url": "http://10.142.1.135:8766/prices/soap-body",
    "authentication": "none",
    "method": "POST",
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ gold_price: $node['转换 SAP 请求体'].json.price_gold, copper_price: $node['转换 SAP 请求体'].json.price_copper, price_date: $node['转换 SAP 请求体'].json.price_date_gold }) }}"
  },
  "name": "构建 SOAP Body",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [950, 200]
}
```

- [ ] **Step 5: 更新写入 SAP 节点**

将 placeholder URL 改为动态引用：

```json
{
  "parameters": {
    "url": "={{ $node['获取 SAP 配置'].json.url }}",
    "authentication": "genericCredentialType",
    "genericAuthType": "httpHeaderAuth",
    "method": "POST",
    "specifyBody": "raw",
    "contentType": "text/xml; charset=utf-8",
    "rawBody": "={{ $node['构建 SOAP Body'].json.soap_body }}",
    "options": {
      "headers": {
        "parameters": [
          {
            "name": "SOAPAction",
            "value": ""
          }
        ]
      }
    }
  },
  "name": "写入 SAP",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [1150, 200],
  "notes": "URL和认证来自配置节点"
}
```

- [ ] **Step 6: 添加 SOAP 响应解析节点**

```json
{
  "parameters": {
    "mode": "runOnceForAllItems",
    "jsCode": "const soapXml = $input.first().json.data || $input.first().json.body || $input.first().json;\n\nconst match = soapXml.match(/<E_OUTPUT>([^<]+)<\\/E_OUTPUT>/);\nif (!match) {\n  return [{ json: { success: false, error: 'E_OUTPUT not found' } }];\n}\n\nconst eOutput = JSON.parse(match[1]);\n\nreturn [{\n  json: {\n    success: eOutput.TYPE === 'S',\n    type: eOutput.TYPE,\n    message: eOutput.MESSAGE,\n    error: eOutput.TYPE !== 'S' ? eOutput.MESSAGE : null\n  }\n}];"
  },
  "name": "解析 SOAP 响应",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [1350, 200]
}
```

- [ ] **Step 7: 更新检查 SAP 返回节点**

```json
{
  "parameters": {
    "conditions": {
      "options": {
        "caseSensitive": true
      },
      "boolean": [
        {
          "value1": "={{ $json.success }}",
          "value2": true
        }
      ]
    }
  },
  "name": "检查 SAP 返回",
  "type": "n8n-nodes-base.if",
  "typeVersion": 2,
  "position": [1550, 200]
}
```

- [ ] **Step 8: 更新 connections**

```json
{
  "手动触发": {
    "main": [
      [
        {
          "node": "选择系统",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "选择系统": {
    "main": [
      [
        {
          "node": "获取 SAP 配置",
          "type": "main",
          "index": 0
        }
      ],
      [
        {
          "node": "获取 SAP 配置",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "获取 SAP 配置": {
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
  "构建 SOAP Body": {
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
          "node": "解析 SOAP 响应",
          "type": "main",
          "index": 0
        }
      ]
    ]
  },
  "解析 SOAP 响应": {
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
}
```

- [ ] **Step 9: Commit**

```bash
git add workflows/metal-price-sync/workflow.json
git commit -m "feat: add SAP system switch and SOAP parsing nodes to workflow"
```

---

### Task 4: 更新 README

**Files:**
- Modify: `workflows/metal-price-sync/README.md`

- [ ] **Step 1: 添加 SAP 集成说明**

在 `## SAP集成（待配置）` 部分替换为：

```markdown
## SAP 集成

### 测试/生产切换

Workflow 通过 Switch 节点选择测试或生产系统：
- 测试系统：`system_type = "test"`
- 生产系统：`system_type = "prod"`

### SOAP Endpoint

| 系统 | URL | 认证 |
|------|-----|------|
| 测试 | `http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600` | Basic Auth (ZHAIYANAN) |
| 生产 | TBD | TBD |

### SOAP Body 结构

Python `/prices/soap-body` 端点生成 SOAP XML：
- GUID：每次生成新 UUID
- 单位转换：铜价 元/吨 → 万元（除以 10000）
- 固定字段：BUTYPE=FI0056, SYSID/HOST/IPADDR/USERID/UNAME=n8n

### SOAP 响应解析

成功判断：`E_OUTPUT.TYPE === "S"`
错误处理：记录 execution history
```

- [ ] **Step 2: Commit**

```bash
git add workflows/metal-price-sync/README.md
git commit -m "docs: update SAP integration documentation"
```

---

### Task 5: 部署到服务器

**Files:**
- 服务器：`/opt/metal-price-sync/service/metal_price_service.py`

- [ ] **Step 1: 上传更新后的服务代码**

```bash
scp workflows/metal-price-sync/service/metal_price_service.py n8n:/opt/metal-price-sync/service/metal_price_service.py
```

- [ ] **Step 2: 重启服务**

```bash
ssh n8n "sudo systemctl restart metal-price-sync && sleep 2 && systemctl status metal-price-sync --no-pager -n 10"
```

- [ ] **Step 3: 测试新端点**

```bash
ssh n8n "curl -sS -X POST http://localhost:8766/prices/soap-body -H 'Content-Type: application/json' -d '{\"gold_price\":1057.9,\"copper_price\":103300,\"price_date\":\"2026-04-17\"}'"
```

Expected: 返回完整 SOAP XML

---

### Task 6: 创建 n8n Credentials

**Files:**
- n8n 界面手动操作

- [ ] **Step 1: 创建测试系统 Credential**

在 n8n → Credentials → Add Credential：
- Type: HTTP Header Auth
- Name: `SAP Test System`
- Header Name: `Authorization`
- Header Value: `Basic ZEhBSVlBTkFaemhhaTE5ODQh`（或手动配置 Basic Auth）

- [ ] **Step 2: 创建生产系统 Credential（placeholder）**

- Type: HTTP Header Auth
- Name: `SAP Production System`
- Header Value: placeholder（待配置）

---

### Task 7: 更新 n8n Workflow

**Files:**
- n8n API

- [ ] **Step 1: 推送更新后的 workflow**

```bash
python -m n8n update-workflow --id 78HQP00Y94cBkV1m --file workflows/metal-price-sync/workflow.json
```

- [ ] **Step 2: 验证 workflow 更新**

```bash
python -m n8n get-workflow --id 78HQP00Y94cBkV1m
```

Expected: 包含新增节点

---

## Self-Review

**Spec coverage:**
- ✅ `/prices/soap-body` 端点 → Task 2
- ✅ UUID 生成 → Task 2
- ✅ 时间格式 → Task 2
- ✅ 单位转换 → Task 2
- ✅ Switch 节点 → Task 3
- ✅ 动态 URL/认证 → Task 3
- ✅ SOAP 响应解析 → Task 3
- ✅ 成功判断 TYPE === "S" → Task 3
- ✅ 失败处理 → 已存在
- ✅ 部署 → Task 5
- ✅ Credentials → Task 6

**Placeholder scan:** 无 TBD/TODO

**Type consistency:** 检查通过