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
python -m uvicorn service.metal_price_service:app --host 0.0.0.0 --port 8766

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

## SAP 集成

### 测试/生产切换

Workflow 通过 Switch 节点选择测试或生产系统：
- 测试系统：`system_type = "test"`
- 生产系统：`system_type = "prod"`

**触发方式：**
- 手动触发：可在 `手动触发` 节点传入 `{"system_type": "test"}` 或 `{"system_type": "prod"}`
- 定时触发：默认使用测试系统

### SOAP Endpoint

| 系统 | URL | 认证 |
|------|-----|------|
| 测试 | `http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600` | Basic Auth (ZHAIYANAN) |
| 生产 | TBD | TBD |

### SOAP Body 结构

Python `/prices/soap-body` 端点生成 SOAP XML：

| 字段 | 来源 | 说明 |
|------|------|------|
| GUID | uuid.uuid4() | 每次生成新 UUID |
| BUTYPE | 固定 FI0056 | 业务类型 |
| SYSID/HOST/IPADDR/USERID/UNAME | 固定 n8n | 系统标识 |
| RDATE | datetime.now() | YYYYMMDD 格式 |
| RTIME | datetime.now() | HHMMSS 格式 |
| GOLD | 输入参数 | 元/克，不转换 |
| COPPER | 输入参数 ÷ 10000 | 元/吨 → 万元 |

### SOAP 响应解析

**成功判断：** `E_OUTPUT.TYPE === "S"`

**响应示例：**
```xml
<E_OUTPUT>{"TYPE":"S","MESSAGE":"数据更新成功"}</E_OUTPUT>
```

**错误处理：** 记录 execution history，路由到 `失败处理` 节点

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