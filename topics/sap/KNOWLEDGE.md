# SAP 集成知识

> 本文件记录 SAP SOAP RFC 集成的通用知识，供所有产品参考。
> 产品专属实现细节在各产品目录的 `KNOWLEDGE.md`。

---

## 连接配置

### 环境信息

| 系统 | URL | Client | 认证 |
|------|-----|--------|------|
| 测试 | `http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600` | 600 | Basic Auth |
| 生产 | TBD | TBD | TBD |

### 认证方式

- **HTTP Basic Auth**（非 Header Auth）
- n8n 中创建 Credential 类型选择 `HTTP Basic Auth`
- 测试系统用户：`ZHAIYANAN`

### HTTP 请求头

```
Content-Type: text/xml; charset=utf-8
SOAPAction: ""（空字符串，必须传）
```

---

## SOAP XML 结构

### 通用模板

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="urn:sap-com:document:sap:rfc:functions">
   <soapenv:Header/>
   <soapenv:Body>
      <urn:Z_FMBC_IF_INBOUND>
         <I_DATA_GD>
            <GUID>{GUID}</GUID>
            <BUTYPE>{BUTYPE}</BUTYPE>
            <SYSID>n8n</SYSID>
            <HOST>n8n</HOST>
            <IPADDR>n8n</IPADDR>
            <USERID>n8n</USERID>
            <UNAME>n8n</UNAME>
            <RDATE>{YYYYMMDD}</RDATE>
            <RTIME>{HHMMSS}</RTIME>
         </I_DATA_GD>
         <I_INPUT>{JSON_PAYLOAD}</I_INPUT>
      </urn:Z_FMBC_IF_INBOUND>
   </soapenv:Body>
</soapenv:Envelope>
```

### 命名空间

| 前缀 | URI | 用途 |
|------|-----|------|
| `soapenv` | `http://schemas.xmlsoap.org/soap/envelope/` | SOAP Envelope |
| `urn` | `urn:sap-com:document:sap:rfc:functions` | SAP RFC 函数 |

### RFC 函数名

`Z_FMBC_IF_INBOUND` — 通用入站接口

---

## I_DATA_GD 字段规则

### GUID

```
格式：32位大写十六进制，无连字符
示例：E9552974AC784B1CBBE0F64C5F717241
生成：uuid.uuid4().hex.upper()
```

**常见错误**：
- ❌ `str(uuid.uuid4())` → 36位带连字符（`550e8400-e29b-41d4-a716-446655440000`）
- ❌ 小写字母 → SAP 期望大写
- ✅ `uuid.uuid4().hex.upper()` → 32位大写无连字符

### 固定字段

| 字段 | 值 | 说明 |
|------|-----|------|
| BUTYPE | `FI0056` | 业务类型（按业务场景不同） |
| SYSID | `n8n` | 来源系统标识 |
| HOST | `n8n` | 主机名 |
| IPADDR | `n8n` | IP 地址 |
| USERID | `n8n` | 用户 ID |
| UNAME | `n8n` | 用户名 |

### 日期时间

| 字段 | 格式 | 示例 | 生成方式 |
|------|------|------|----------|
| RDATE | YYYYMMDD | `20260417` | `datetime.now().strftime("%Y%m%d")` |
| RTIME | HHMMSS | `171056` | `datetime.now().strftime("%H%M%S")` |

---

## I_INPUT 字段规则

`I_INPUT` 是 JSON 字符串，嵌入在 XML 中。格式需特别注意缩进和转义。

### JSON 格式要求

```xml
<I_INPUT>{
 "GOLD":"1057.9",
 "COPPER":"10.33"
}</I_INPUT>
```

- 换行 + 1空格缩进（非标准2空格）
- 值为字符串（带引号），即使传入的是数字
- 生成方式：

```python
i_input_dict = {"GOLD": str(gold_price), "COPPER": str(copper_wan)}
i_input_json = "\n" + json.dumps(i_input_dict, indent=1).replace("\n  ", "\n ")
```

### 单位转换

| 金属 | 输入单位 | SAP 单位 | 转换 | 示例 |
|------|----------|----------|------|------|
| 黄金 GOLD | 元/克 | 元/克 | 不转换 | `1057.9` |
| 铜 COPPER | 元/吨 | 万元 | ÷10000，保留2位小数 | `103300 → 10.33` |

```python
copper_wan = round(copper_price / 10000, 2)
```

---

## SOAP 响应解析

### 响应结构

```xml
<soap-env:Envelope xmlns:soap-env="http://schemas.xmlsoap.org/soap/envelope/">
    <soap-env:Body>
        <n0:Z_FMBC_IF_INBOUNDResponse xmlns:n0="urn:sap-com:document:sap:rfc:functions">
            <E_OUTPUT>{"TYPE":"S","ID":"","NUMBER":0,"MESSAGE":"数据更新成功"}</E_OUTPUT>
        </n0:Z_FMBC_IF_INBOUNDResponse>
    </soap-env:Body>
</soap-env:Envelope>
```

### E_OUTPUT 判断

`E_OUTPUT` 是 JSON 字符串，需先正则提取再 `JSON.parse`：

```javascript
const match = soapXml.match(/<E_OUTPUT>([^<]+)<\/E_OUTPUT>/);
const eOutput = JSON.parse(match[1]);
```

| TYPE | 含义 | 处理 |
|------|------|------|
| `S` | 成功 | workflow 完成 |
| `E` | 错误 | 路由到失败处理 |
| 其他 | 未知 | 按失败处理 |

### n8n 解析 Code Node

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

---

## n8n Workflow 模式

### 测试/生产切换

```
手动触发（system_type: "test" | "prod"）
  → Switch 节点路由
  → Code 节点输出 URL + Credential Name
  → HTTP Request 节点使用动态 URL 和认证
```

### Code 节点配置选择

```javascript
const systemType = $('选择系统').first().json.system_type;
const config = {
  test: {
    url: 'http://10.142.1.20:8000/...?sap-client=600',
    credentialName: 'SAP Test System'
  },
  prod: {
    url: 'PROD_URL_PLACEHOLDER',
    credentialName: 'SAP Production System'
  }
};
return [{ json: config[systemType] }];
```

### HTTP Request 节点

| 配置项 | 值 |
|--------|-----|
| Method | POST |
| URL | `={{ $json.url }}`（来自上游 Code 节点） |
| Authentication | Predefined Credential Type |
| Credential Type | HTTP Basic Auth |
| Credential | `={{ $json.credentialName }}` |
| Content-Type | `text/xml; charset=utf-8` |
| SOAPAction | `""`（空） |
| Body | `={{ $('构建 SOAP Body').first().json.soap_body }}` |

### 失败处理

- **不重试**：SAP 写入失败直接记录
- 日志记录在 n8n execution history
- 可扩展告警（邮件/钉钉/飞书）

---

## 常见错误

### GUID 格式错误

```
SAP 拒绝：GUID 不符合 32 位大写格式
原因：使用 str(uuid.uuid4()) 生成带连字符的 UUID
修复：uuid.uuid4().hex.upper()
```

### Content-Type 错误

```
SAP 返回 415 或 500
原因：Content-Type 缺少 charset 或使用了 application/xml
修复：必须 text/xml; charset=utf-8
```

### SOAPAction 缺失

```
SAP 返回错误
原因：未传 SOAPAction header
修复：SOAPAction: ""（空字符串，但 header 必须存在）
```

### I_INPUT JSON 格式错误

```
SAP 解析 I_INPUT 失败
原因：JSON 缩进不符合 SAP 期望（2空格而非1空格）
修复：json.dumps(indent=1).replace("\n  ", "\n ")
```

### n8n Credential 类型错误

```
认证失败
原因：创建了 HTTP Header Auth 而非 HTTP Basic Auth
修复：n8n 中 Credential 类型必须选择 HTTP Basic Auth
```

---

## 参考实现

- 服务端点：`workflows/metal-price-sync/service/metal_price_service.py` → `POST /prices/soap-body`
- 测试：`workflows/metal-price-sync/tests/test_soap_body.py`
- 设计文档：`docs/superpowers/specs/2026-04-17-metal-price-sap-integration-design.md`
