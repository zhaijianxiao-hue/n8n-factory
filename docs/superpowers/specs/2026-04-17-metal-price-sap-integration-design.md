# Metal Price Sync SAP Integration 设计

> 日期：2026-04-17
> 状态：Approved

---

## 概述

扩展 metal-price-sync workflow，实现测试/生产系统切换控制，将金价、铜价写入 SAP SOAP endpoint。

**核心特性**：
- Switch 节点控制测试/生产系统选择
- Python 服务构建 SOAP XML（可测试）
- n8n 动态选择 URL 和认证
- SOAP 响应解析判断成功/失败

---

## Workflow 结构

```
手动触发
  → Switch 节点（测试/生产）
  → 获取金铜价格（Python /prices/latest）
  → 检查抓取结果
      ↓ success
  → 构建 SOAP Body（Python /prices/soap-body）
  → 写入 SAP（HTTP POST SOAP，动态 URL/认证）
  → 解析 SOAP 响应
  → 检查 SAP 返回（TYPE === "S" ?）
      ↓ success → 完成
      ↓ error   → 失败处理（记录日志）
```

---

## Python 服务扩展

### 新增端点：`POST /prices/soap-body`

**输入**：
```json
{
  "gold_price": 1057.9,
  "copper_price": 103300,
  "price_date": "2026-04-17"
}
```

**输出**：完整 SOAP XML

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions">
   <soapenv:Header/>
   <soapenv:Body>
      <urn:Z_FMBC_IF_INBOUND>
         <I_DATA_GD>
            <GUID>uuid-generated</GUID>
            <BUTYPE>FI0056</BUTYPE>
            <SYSID>n8n</SYSID>
            <HOST>n8n</HOST>
            <IPADDR>n8n</IPADDR>
            <USERID>n8n</USERID>
            <UNAME>n8n</UNAME>
            <RDATE>20260417</RDATE>
            <RTIME>171056</RTIME>
         </I_DATA_GD>
         <I_INPUT>{
 "GOLD":"1057.9",
 "COPPER":"10.33"
}</I_INPUT>
      </urn:Z_FMBC_IF_INBOUND>
   </soapenv:Body>
</soapenv:Envelope>
```

### 字段规则

| 字段 | 来源 | 说明 |
|------|------|------|
| GUID | `uuid.uuid4()` | 标准格式如 `550e8400-e29b-41d4-a716-446655440000` |
| BUTYPE | 固定 `FI0056` | 业务类型 |
| SYSID | 固定 `n8n` | 系统标识 |
| HOST | 固定 `n8n` | 主机名 |
| IPADDR | 固定 `n8n` | IP 地址 |
| USERID | 固定 `n8n` | 用户 ID |
| UNAME | 固定 `n8n` | 用户名 |
| RDATE | `datetime.now()` | 格式 `YYYYMMDD` |
| RTIME | `datetime.now()` | 格式 `HHMMSS` |
| GOLD | 输入参数 | 元/克，不转换 |
| COPPER | 输入参数 ÷ 10000 | 元/吨 → 万元 |

### 单位转换

```python
gold_value = gold_price  # 元/克，保持原值
copper_value = round(copper_price / 10000, 2)  # 元/吨 → 万元，保留2位小数
```

---

## n8n 节点配置

### Switch 节点（系统选择）

- 类型：手动触发时的表单字段
- 输出：`system_type` = "test" 或 "prod"

### Code Node（配置选择）

```javascript
const systemType = $('Switch').first().json.system_type;
const config = {
  test: {
    url: 'http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600',
    credentialName: 'SAP Test System'
  },
  prod: {
    url: 'PROD_URL_PLACEHOLDER',
    credentialName: 'SAP Production System'
  }
};
return [{ json: config[systemType] }];
```

### Credentials

| Credential Name | Auth Type | 配置 |
|-----------------|-----------|------|
| SAP Test System | HTTP Header Auth (Basic) | User: ZHAIYANAN, Password: Zzhai1984! |
| SAP Production System | HTTP Header Auth (Basic) | 待配置 |

### 写入 SAP 节点

- HTTP Method：POST
- Content-Type：`text/xml; charset=utf-8`
- SOAPAction：`""`（空字符串）
- Body：来自 `/prices/soap-body` 端点的 XML
- URL/认证：来自 Code Node 输出

---

## SOAP 响应解析

### 成功响应示例

```xml
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
    <soap-env:Body>
        <n0:Z_FMBC_IF_INBOUNDResponse xmlns:n0="urn:sap-com:document:sap:rfc:functions">
            <E_OUTPUT>{"TYPE":"S","ID":"","NUMBER":0,"MESSAGE":"数据更新成功"}</E_OUTPUT>
        </n0:Z_FMBC_IF_INBOUNDResponse>
    </soap-env:Body>
</soap-env:Envelope>
```

### Code Node 解析逻辑

```javascript
const soapXml = $input.first().json.data || $input.first().json.body;

const match = soapXml.match(/<E_OUTPUT>([^<]+)<\/E_OUTPUT>/);
if (!match) {
  return [{ json: { success: false, error: 'E_OUTPUT not found' } }];
}

const eOutput = JSON.parse(match[1]);

return [{
  json: {
    success: eOutput.TYPE === 'S',
    type: eOutput.TYPE,
    message: eOutput.MESSAGE,
    error: eOutput.TYPE !== 'S' ? eOutput.MESSAGE : null
  }
}];
```

### 成功判断

| TYPE | 含义 | 处理 |
|------|------|------|
| `S` | 成功 | workflow 完成 |
| `E` | 错误 | 路由到失败处理 |

---

## 失败处理

- **不重试**：写入失败直接记录
- **日志记录**：execution history + 可扩展告警（邮件/钉钉）

---

## 配置项

### 测试系统（已确认）

| 配置项 | 值 |
|--------|-----|
| URL | `http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600` |
| User | ZHAIYANAN |
| Password | Zzhai1984! |
| Client | 600 |

### 生产系统（待配置）

| 配置项 | 值 |
|--------|-----|
| URL | TBD |
| User | TBD |
| Password | TBD |
| Client | TBD |

---

## 文件变更

| 文件 | 变更 |
|------|------|
| `service/metal_price_service.py` | 新增 `/prices/soap-body` 端点 |
| `tests/test_service_api.py` | 新增 SOAP 端点测试 |
| `workflow.json` | 新增 Switch、Code Node、解析节点 |
| `README.md` | 更新 SAP 集成说明 |

---

## 测试验证

1. Python `/prices/soap-body` 单元测试
2. 手动触发 workflow 选择测试系统
3. 验证 SOAP XML 格式
4. 验证 SAP 返回解析
5. 验证失败处理路径