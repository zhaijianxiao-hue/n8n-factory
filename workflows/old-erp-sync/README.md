# old-erp-sync: 老 ERP 数据同步到飞书多维表格

> 从老 ERP 的 SQL Server 存储过程提取前一天数据，通过飞书开放平台 API 批量写入多维表格。

## 业务背景

- 目标：在 n8n 中读取老 ERP 统计数据，通过官方 API 批量写入飞书多维表格。
- 数据日期：统一使用昨天，格式为 `yyyy/MM/dd`，例如 `2026/04/01`。

## 工作流结构

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  手动触发    │───▶│ 获取老ERP数据 │───▶│ 转换数据格式  │───▶│ 获取飞书Token │───▶│ 写入多维表格  │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## 节点说明

### 获取老ERP数据

- 节点类型：`Microsoft SQL`
- 执行方式：`executeQuery`
- SQL 中使用昨天作为日期参数

### 转换数据格式

- 节点类型：`Code`
- 作用：
  - 解析 SQL 返回的 JSON 字符串
  - 添加 `zdate` 字段（数据日期）
  - 转换成飞书多维表格字段格式

### 获取飞书Token

- 节点类型：`HTTP Request`
- 调用：`POST /auth/v3/tenant_access_token/internal`
- 用 App ID + App Secret 换取 `tenant_access_token`

### 写入飞书多维表格

- 节点类型：`HTTP Request`
- 调用：`POST /bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create`
- 批量写入，一次最多 500 条

## 飞书配置信息

| 配置项 | 值 |
|--------|-----|
| App ID | `YOUR_FEISHU_APP_ID` |
| App Secret | `YOUR_FEISHU_APP_SECRET` |
| app_token | `YOUR_BITABLE_APP_TOKEN` |
| table_id | `YOUR_BITABLE_TABLE_ID` |

## 多维表格字段

| 字段名 | 类型 |
|--------|------|
| 序号 | 自动编号 |
| ProcName | 文本 |
| ProcOrd | 文本 |
| ProcNo | 文本 |
| EliArea | 文本 |
| EliPNL | 文本 |
| ScrapArea | 文本 |
| ScrapPNL | 文本 |
| ProdArea | 文本 |
| ProdPNL | 文本 |
| BugNo | 文本 |
| BugArea | 文本 |
| BugName | 文本 |
| Target | 文本 |
| zdate | 文本（数据日期）|

## 文件结构

```
old-erp-sync/
├── config/
│   └── product.json
├── schemas/
├── tests/
├── workflow.json
└── README.md
```

## 注意事项

- 飞书 tenant_access_token 有效期 2 小时
- 批量写入一次最多 500 条
- 需要确保应用有多维表格写入权限
- SQL 返回的 `Result` 字段应为 JSON 字符串
