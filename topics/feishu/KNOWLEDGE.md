# 飞书多维表格 API 知识库

> 跨产品的飞书 API 调用知识，供所有需要对接飞书的产品使用。

---

## 核心接口

### 1. 获取 tenant_access_token

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

- Token 有效期 2 小时
- 建议缓存，避免每次请求都获取

### 2. 批量新增记录

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

### 3. 列出数据表

```
GET https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables
```

### 4. 列出字段

```
GET https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
```

---

## 权限配置

需要在飞书开放平台为应用开启权限：
- `bitable:app` - 查看、评论、编辑和管理多维表格
- 或 `base:record:create` - 新增记录

**重要**：发布版本后权限才会生效。

---

## 踩坑记录

### 坑 1：records 为空

**问题**：调用 batch_create 返回 `records can not be empty`。

**原因**：
1. 数据转换逻辑错误
2. n8n 表达式写法不对

**解决**：检查 Code 节点输出，确认 `records` 数组结构正确。

### 坑 2：权限不足

**问题**：调用 API 返回 `Forbidden`（错误码 91403）。

**解决**：
1. 飞书开放平台为应用开通权限
2. 发布版本
3. 多维表格添加应用为协作者

### 坑 3：字段类型不匹配

**问题**：写入时字段类型错误。

**解决**：
- 文本字段：字符串
- 数字字段：数值
- 日期字段：时间戳（毫秒）或格式化字符串

---

## 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 91403   | 权限不足 | 检查应用权限配置 |
| 1254001 | 请求体错误 | 检查 records 格式 |
| 1254004 | table_id 错误 | 检查 table_id |
| 1254040 | app_token 错误 | 检查 app_token |

---

## 相关文档

- 飞书开放平台：https://open.feishu.cn/
- 多维表格 API：https://open.feishu.cn/document/server-docs/docs/bitable-v1/intro

---

## 快速参考

见 `quickref.md`：curl 命令示例、字段映射表、测试脚本。