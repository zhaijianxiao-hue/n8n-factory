# Metal Price Sync 产品知识

> 本文件记录 metal-price-sync 产品专属知识，根目录 KNOWLEDGE.md 只做索引引用。

---

## 产品概述

每日金属价格同步服务，抓取黄金和铜价格，标准化为统一 JSON 格式，通过 n8n 写入 SAP。

**关键参数**:
- 服务端口: `8766`
- 定时调度: `0 2 * * *`（每日凌晨 02:00）
- n8n Workflow ID: `78HQP00Y94cBkV1m`

---

## 服务架构

```
n8n 定时触发
    │
    ▼
Python Service (8766)
    │
    ├─ /health         → 健康检查
    ├─ /prices/latest  → 抓取金铜价格
    │
    ▼
n8n 检查结果
    │
    ├─ success → 转换 SAP 请求体 → 写入 SAP
    │
    └─ error   → 失败处理
```

**设计原则**:
- Python 服务只负责抓取和标准化，不直接写 SAP
- n8n 负责：调度、校验、SAP 请求体映射、写入、失败处理

---

## V1 严格失败规则

- 黄金或铜任意缺失 → 整体 status 为 error
- 不允许部分成功写入 SAP
- 失败时完全阻断 SAP 写入

---

## 数据源

**黄金**:
- URL: `http://www.huangjinjiage.cn/quote/119023.html`
- 方法: HTTP GET + BeautifulSoup HTML 解析
- 单位: 元/克 → 标准化为 `g`

**铜**:
- URL: `https://www.jinritongjia.com/hutong/`
- 方法: V1 需调研真实数据 endpoint（当前返回 error）
- 单位: 元/吨 → 标准化为 `t`

---

## 响应结构

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

---

## 部署信息

**服务器**: n8n 同机部署（`10.142.1.135`）

**路径**: `/opt/metal-price-sync`

**Systemd Unit**: `metal-price-sync.service`

**关键命令**:
```bash
# 检查服务状态
ssh n8n "systemctl status metal-price-sync --no-pager"

# 查看日志
ssh n8n "journalctl -u metal-price-sync --no-pager -n 50"

# 重启服务
ssh n8n "sudo systemctl restart metal-price-sync"

# 测试 API
ssh n8n "curl -s http://localhost:8766/health"
ssh n8n "curl -s http://localhost:8766/prices/latest"
```

---

## n8n Workflow 节点

| 节点 | 类型 | 作用 |
|------|------|------|
| 定时触发 | scheduleTrigger | cron: 0 2 * * * |
| 获取金铜价格 | httpRequest | GET http://10.142.1.135:8766/prices/latest |
| 检查抓取结果 | if | 校验 status == success |
| 转换 SAP 请求体 | set | 映射字段到 SAP 格式 |
| 写入 SAP | httpRequest | POST SAP endpoint（待配置） |
| 检查 SAP 返回 | if | 校验 statusCode == 200 |
| 失败处理 | noOp | Placeholder，可扩展告警 |

---

## 相关文件

```
workflows/metal-price-sync/
├── config/
│   ├── product.json      → 产品元数据
│   └── env.example       → 环境变量示例
├── service/
│   └── metal_price_service.py → FastAPI 服务
├── tests/
│   ├── test_gold_parser.py
│   ├── test_copper_parser.py
│   ├── test_service_api.py
│   └── fixtures/
├── workflow.json         → n8n workflow 定义
├── README.md             → 产品文档
└── KNOWLEDGE.md          → 本文件
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-16 | 初始化产品，完成服务部署和 n8n workflow 创建 |