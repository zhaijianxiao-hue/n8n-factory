# old-erp-sync 项目知识库

> 本文档记录工作流开发过程中的经验、避坑指南和关键知识点。

---

## 项目概述

**目标**：从老 ERP 的 SQL Server 存储过程提取数据，批量写入飞书多维表格。

**技术栈**：
- n8n 工作流自动化
- Microsoft SQL Server
- 飞书开放平台 API（多维表格）

---

## 飞书多维表格 API

### 核心接口

**1. 获取 tenant_access_token**
```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
```
请求体：
```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```
返回：
```json
{
  "code": 0,
  "tenant_access_token": "t-xxx",
  "expire": 7200
}
```

**2. 批量新增记录**
```
POST https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create
```
请求头：
```
Authorization: Bearer {tenant_access_token}
Content-Type: application/json
```
请求体：
```json
{
  "records": [
    {
      "fields": {
        "字段名": "值"
      }
    }
  ]
}
```
- 一次最多 500 条记录
- 字段值类型必须匹配（文本用字符串，数字用数值）

**3. 列出数据表**
```
GET https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables
```

**4. 列出字段**
```
GET https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
```

### 配置信息

| 配置项 | 值 |
|--------|-----|
| App ID | `YOUR_FEISHU_APP_ID` |
| App Secret | `YOUR_FEISHU_APP_SECRET` |
| app_token | `YOUR_BITABLE_APP_TOKEN` |
| table_id | `YOUR_BITABLE_TABLE_ID` |

### 权限配置

需要在飞书开放平台为应用开启权限：
- `bitable:app` - 查看、评论、编辑和管理多维表格
- 或 `base:record:create` - 新增记录

发布版本后权限才会生效。

---

## n8n 工作流开发经验

### 表达式语法

**1. 引用其他节点数据**
```javascript
// 正确
$node["节点名称"].json.fieldName

// 错误（n8n 不支持模板语法嵌套）
{{ $node["节点名称"].json.fieldName }}
```

**2. 字符串拼接**
```javascript
// 正确
={{ 'Bearer ' + $json.tenant_access_token }}

// 错误
=Bearer {{ $json.tenant_access_token }}
```

**3. JSON 序列化**
```javascript
// 正确
={{ JSON.stringify($node["转换数据格式"].json) }}

// 错误（不支持管道符）
={{ $json | JSON.stringify }}
```

### Code 节点

**1. 数据访问**
```javascript
// 获取所有输入项
const items = $input.all();

// 每项的 json 属性包含实际数据
const row = items[0].json;
```

**2. 返回格式**
```javascript
// 必须返回数组，每项包含 json 属性
return [{
  json: {
    records: [...]
  }
}];
```

**3. 日期处理**
```javascript
// 使用 Luxon（n8n 内置）
const yesterday = $now.minus({ days: 1 }).toFormat('yyyy/MM/dd');
```

### HTTP Request 节点

**1. 动态请求头**
- 开启 `sendHeaders`
- 在 `headerParameters.parameters` 中添加
- 值支持表达式：`={{ 'Bearer ' + $json.token }}`

**2. 动态请求体**
- `specifyBody: "json"`
- `jsonBody` 支持表达式

---

## 避坑指南

### 坑 1：SQL 节点返回数据结构

**问题**：不确定 SQL 返回的是 JSON 字符串还是对象数组。

**实际**：SQL 节点直接返回对象数组，每条记录是一个对象。

**解决**：
```javascript
// 错误假设：需要解析 JSON 字符串
const rows = JSON.parse($json.Result);

// 正确：直接使用
const rows = $input.all().map(item => item.json);
```

### 坑 2：飞书 API 返回 records 为空

**问题**：调用 batch_create 时返回 `records can not be empty`。

**原因**：
1. 数据转换逻辑错误，没有正确解析数据
2. n8n 表达式写法不对

**排查方法**：
1. 在 Code 节点加 `console.log()` 输出调试信息
2. 检查节点输出，确认数据结构
3. 用独立脚本测试 API 调用

### 坑 3：n8n workflow 更新 API

**问题**：更新 workflow 时报错 `settings must NOT have additional properties`。

**解决**：只发送必要字段
```javascript
const payload = {
  name: workflow.name,
  nodes: workflow.nodes,
  connections: workflow.connections,
  settings: {}  // 空对象
};
```

### 坑 4：飞书权限不足

**问题**：调用 API 返回 `Forbidden`。

**解决**：
1. 飞书开放平台为应用开通权限
2. 发布版本
3. 多维表格添加应用为协作者

### 坑 5：字段类型不匹配

**问题**：写入时字段类型错误。

**解决**：确保类型匹配
- 文本字段：字符串
- 数字字段：数值
- 日期字段：时间戳（毫秒）或格式化字符串

---

## 调试技巧

### 1. Code 节点调试
```javascript
console.log('Input count:', $input.all().length);
console.log('First item:', JSON.stringify($input.first().json));
console.log('Keys:', Object.keys($input.first().json));
```

### 2. 独立测试 API
用 Node.js 脚本直接调用飞书 API，排除 n8n 表达式问题：
```javascript
const https = require('https');
// 直接发请求测试
```

### 3. 分节点验证
- 先确认 SQL 节点返回的数据结构
- 再确认转换节点的输出
- 最后测试 API 调用

---

## 工作流节点顺序

```
手动触发
  → 获取老ERP数据（Microsoft SQL）
  → 转换数据格式（Code）
  → 获取飞书Token（HTTP Request）
  → 写入飞书多维表格（HTTP Request）
```

---

## 相关文档

- 飞书开放平台：https://open.feishu.cn/
- 多维表格 API：https://open.feishu.cn/document/server-docs/docs/bitable-v1/intro
- n8n 表达式：https://docs.n8n.io/code-examples/expressions/
- Luxon 日期：https://luxon.dev/docs/

---

## 更新记录

- **2026-04-02**：初始版本，记录飞书多维表格 API 集成经验
