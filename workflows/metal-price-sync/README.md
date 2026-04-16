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

## SAP集成（待配置）

SAP写入部分由n8n负责，service不直接访问SAP。

**需要配置：**
- SAP endpoint URL
- HTTP method (POST/PUT)
- 认证方式 (basic auth / token / cert)
- 必需headers
- Request body schema
- Success response schema
- Error response schema

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