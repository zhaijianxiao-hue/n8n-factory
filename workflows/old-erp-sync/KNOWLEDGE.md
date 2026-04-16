# old-erp-sync 项目知识库

> 本文档记录产品业务流程和 n8n 开发经验。
> **飞书 API 知识见 `topics/feishu/KNOWLEDGE.md`**。

---

## 项目概述

**目标**：从老 ERP 的 SQL Server 存储过程提取数据，批量写入飞书多维表格。

**技术栈**：
- n8n 工作流自动化
- Microsoft SQL Server
- 飞书开放平台 API（多维表格）

---

## 工作流节点顺序

```
手动触发
  → 获取老ERP数据
  → 转换数据格式
  → 获取飞书Token（HTTP Request）
  → 写入飞书多维表格（HTTP Request）
```

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

### 坑 2：n8n workflow 更新 API

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

---

## 调试技巧

### 1. Code 节点调试
```javascript
console.log('Input count:', $input.all().length);
console.log('First item:', JSON.stringify($input.first().json));
console.log('Keys:', Object.keys($input.first().json));
```

### 2. 分节点验证
- 先确认 SQL 节点返回的数据结构
- 再确认转换节点的输出
- 最后测试 API 调用

---

## 相关文档

- n8n 表达式：https://docs.n8n.io/code-examples/expressions/
- Luxon 日期：https://luxon.dev/docs/
- **飞书 API 参考**：`topics/feishu/KNOWLEDGE.md`

---

## 更新记录

- **2026-04-16**：飞书 API 知识迁移到 `topics/feishu/`
- **2026-04-02**：初始版本