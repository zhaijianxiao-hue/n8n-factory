# n8n Workflow Factory 知识库

> **所有 agent 必须先读此文件**，了解 n8n 核心概念和通用规则。
> 产品专属知识在各产品目录的 `KNOWLEDGE.md`。
> 踩坑记录在 `LEARNINGS.md`。

---

## 知识库索引

### 主题知识（跨产品）

| 主题 | 目录 | 说明 |
|------|------|------|
| 飞书多维表格 | `topics/feishu/` | Token、API、权限、踩坑 |
| SAP SOAP RFC | `topics/sap/` | SOAP XML、GUID、认证、响应解析 |

### 产品知识

| 产品 | 目录 | 端口 | 说明 |
|------|------|------|------|
| po-parser | `workflows/po-parser/` | 8765 | PO PDF 解析服务 |
| metal-price-sync | `workflows/metal-price-sync/` | 8766 | 金属价格同步服务 |
| old-erp-sync | `workflows/old-erp-sync/` | - | 老 ERP → 飞书流程 |

### 通用服务

| 服务 | 目录 | 端口 | 说明 |
|------|------|------|------|
| hana-query-api | `services/hana-query-api/` | 8766 | SAP HANA SQL → JSON 查询 API，`POST /query` 执行受控查询，`GET /health` 检查连通性 |
| screenshot-service | `services/screenshot-service/` | 8767 | 网页截图服务，`POST /screenshot` 返回 base64 PNG，供 n8n 后续上传飞书图片 |

### Workflow 专用服务

| 服务 | 目录 | 端口 | 说明 |
|------|------|------|------|
| po-parser service | `workflows/po-parser/service/` | 8765 | PO PDF 解析主服务，供 n8n 调用解析接口 |
| po-parser /check-email | `workflows/po-parser/service/` | 8765 | Exchange EWS 拉取邮件附件到 incoming 目录 |
| metal-price-sync service | `workflows/metal-price-sync/service/` | 8766 | 金属价格同步服务，提供价格抓取与 SOAP body 生成接口 |

- `po-parser profile lab` (`workflows/po-parser/profile_lab/` + `workflows/po-parser/profile-lab/`)
  - 本地优先的客户 PO 解析 Profile 训练/评测/调优核心
  - 命令入口：`cd workflows/po-parser && python -m profile_lab init-customer --customer evytra`
  - 产物：customer assets、runs、candidate JSON、adjudication reports、evaluation reports、published profiles

### 踩坑记录

- `LEARNINGS.md` - 所有踩坑汇总

---

### 现有 API / Service 清单

#### 通用服务

- `hana-query-api` (`services/hana-query-api/`)
  - Base URL: `http://10.142.1.135:8766`
  - `GET /health`：检查 HANA 连通性
  - `POST /query`：执行受控 SQL 查询，返回 `data / total / columns`

- `screenshot-service` (`services/screenshot-service/`)
  - Base URL: `http://10.142.1.135:8767`
  - `GET /health`：服务健康检查
  - `POST /screenshot`：输入 `url/width/height/full_page/delay_ms`，返回 `image_base64`
  - 用途：给大屏、查询页、报表页截图，后续节点再上传飞书图片并发消息
  - 限制：仅允许 `http/https`，默认禁止内网地址；可通过 `SCREENSHOT_ALLOWED_PRIVATE_HOSTS` 白名单放行指定内网 host/IP；当前默认使用服务器 Chromium

#### Workflow 专用服务

- `po-parser service` (`workflows/po-parser/service/`)
  - Base URL: `http://10.142.1.135:8765`
  - 解析 PDF、客户 profile 路由、输出标准 PO JSON
  - 同机还提供 `/check-email`：从 Exchange EWS 拉取带附件邮件到 SMB incoming

- `metal-price-sync service` (`workflows/metal-price-sync/service/`)
  - 当前 README 标注端口 `8766`，实际部署时需避免与通用服务冲突
  - 提供价格抓取、标准化 JSON、SOAP body 生成等接口
  - 供每日价格同步 workflow 调用

### Service 维护规则

- 新增或修改 n8n 调用的 API/service 时，必须同步更新这里的清单。
- 区分“通用服务”（`services/`）和“workflow 专用服务”（`workflows/*/service/`）。
- 至少记录：目录、端口、Base URL、主要端点、用途、调用方 workflow。
- 如果端口或部署地址与文档不一致，先以运行环境为准，再回写知识文档。


### 执行模型

```
Workflow (静态定义)
  └── Execution (一次运行实例)
        ├── Node A 执行结果
        ├── Node B 执行结果
        └── ...
```

**核心概念**: Execution 是整个 workflow 运行，不是单个节点。

### 数据流

- Item-based: 每个节点输出数组 `[{ "json": {...} }]`
- 下游节点逐 item 处理（除非 batch mode）

---

## n8n API 速查

### 端点

```
Base: http://10.142.1.135:5678/api/v1
Auth: X-N8N-API-KEY header
```

| 操作 | 端点 | 方法 |
|------|------|------|
| 列出 workflows | `/workflows` | GET |
| 获取 workflow | `/workflows/{id}` | GET |
| 创建 workflow | `/workflows` | POST |
| 更新 workflow | `/workflows/{id}` | PUT |
| 激活 workflow | `/workflows/{id}/activate` | POST |
| 停用 workflow | `/workflows/{id}/deactivate` | POST |
| 列出 executions | `/executions` | GET |
| 获取 execution | `/executions/{id}?includeData=true` | GET |

### 更新 Payload 限制

```json
{
  "name": "...",
  "nodes": [...],
  "connections": {...},
  "settings": {...}
}
```

**禁止额外字段**: `staticData`, `tags`, `pinData`, `meta` 等会被 API 拒绝。

---

## Expression 语法核心

### 引用数据

```javascript
$json                    // 当前节点输出
$json.field              // 字段访问
$json.items[0]           // 数组索引
$node["节点名"].json      // 其他节点输出
$input.item.json         // 输入 item
```

### 常见错误

- ❌ `$json["field"]` → JSON 语法错误（双引号嵌套）
- ✅ `$json.field` 或 `={{ $json['field'] }}`

### Code Node vs Expression

| 场景 | 用法 |
|------|------|
| 简单映射 | Expression `={{ $json.field }}` |
| 复杂逻辑 | Code Node JavaScript |
| 多节点聚合 | Code Node `$input.all()` |

---

## 开发流程

### 创建 Workflow

1. n8n UI 设计 → Export JSON
2. 保存到 `workflows/{product}/workflow.json`
3. 创建 `config/product.json`
4. 文档 `README.md` + `KNOWLEDGE.md`

### 更新 Workflow

1. 读现有 JSON（保留 node IDs）
2. 目标修改
3. `PUT /workflows/{id}` 推送
4. `GET /workflows/{id}` 验证
5. 测试执行

### Debug 失败 Execution

```bash
# 获取失败执行
GET /executions?workflowId={id}&status=error

# 获取完整数据
GET /executions/{id}?includeData=true

# 找失败节点
jq '.data.resultData.lastNodeExecuted'

# 查看错误
jq '.data.resultData.runData["NodeName"][0].data'
```

---

## Skills & Tools

可用 n8n skills:
- `n8n-code-javascript` - Code node JavaScript
- `n8n-expression-syntax` - Expression 语法验证
- `n8n-node-configuration` - 节点配置指导
- `n8n-validation-expert` - Workflow 验证错误
- `n8n-workflow-patterns` - 架构模式

项目 n8n skill: `.opencode/skill/n8n/`

---

## 关键规则速查

### Docker 网络问题

n8n 在 Docker，调用同机服务：
- ❌ `localhost:port`
- ✅ `宿主机IP:port`（如 `10.142.1.135:8766`）

详见 `LEARNINGS.md`。

### If Node V2

字符串比较需显式设置 `caseSensitive: true`。

### Set Node V3.4

字段类型必须匹配：
- 数组 → `type: "array"`
- 对象 → `type: "object"`

---

## HANA Query API

通用 SAP HANA SQL 查询服务，传入 SQL 返回 JSON。任何程序/agent 均可调用。

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查（含 HANA 连通性） |
| `/query` | POST | 执行 SQL，返回 JSON |

### 调用方式

```
POST http://10.142.1.135:8766/query
Content-Type: application/json

{"sql": "SELECT * FROM SAPHANADB.\"MARA\" LIMIT 10"}
```

### 响应格式

```json
{
  "data": [{"MATNR": "...", "MAKTX": "..."}],
  "total": 10,
  "columns": ["MATNR", "MAKTX"]
}
```

### 配置

环境变量（`/opt/hana-query-api/.env`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| HANA_HOST | 10.142.1.38 | HANA 地址 |
| HANA_PORT | 30041 | HANA 端口 |
| HANA_DATABASE | S4P | 租户数据库 |
| HANA_USER | FR_USER | 用户名 |
| HANA_PASSWORD | - | 密码 |
| HANA_MAX_ROWS | 10000 | 最大返回行数 |
| HANA_QUERY_TIMEOUT | 60 | 查询超时秒数 |
| HANA_API_PORT | 8766 | API 服务端口 |

### 技术栈

- FastAPI + uvicorn
- hdbcli（SAP 官方 Python 驱动）
- systemd 服务：`hana-query-api.service`

### n8n 集成

在 n8n 中用 **HTTP Request** 节点：
- Method: POST
- URL: `http://10.142.1.135:8766/query`
- Body: `{"sql": "{{ 你的SQL语句 }}"}`

---

## 参考文档

- n8n 官方文档: https://docs.n8n.io
- n8n API 参考: https://docs.n8n.io/api
- 本项目 API 详细说明: `.opencode/skill/n8n/references/api.md`
