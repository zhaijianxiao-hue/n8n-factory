# Exchange Rate Sync

人民币汇率中间价抓取与标准化服务，以及已投产的 CFETS → SAP OB08 n8n workflow。service 不直接写 SAP，生产写入由 n8n 调用 NexCore PRD API 完成。

## 数据源与口径

- 主源：CFETS/中国货币网人民币汇率中间价
- 目标币种：EUR、USD、CAD、HKD、SGD、JPY → CNY
- JPY：原始报价为 100 JPY/CNY，返回 `from_factor=100`
- 周末/节假日：回退到不晚于请求日的最近发布日期
- 严格规则：请求币种任一缺失，整批返回 HTTP 502，不返回部分成功

ECB、Frankfurter 和银行牌价不作为自动备用源。数据源不可用时停止后续 SAP 写入，避免同一汇率类型混入不同口径。

## API

### 健康检查

```text
GET /health
```

### 批量解析汇率

```text
POST /rates/resolve
Content-Type: application/json

{
  "requested_date": "2026-07-12",
  "currencies": ["EUR", "USD", "CAD", "HKD", "SGD", "JPY"],
  "lookback_days": 10
}
```

响应同时包含业务请求日 `requested_date` 和实际汇率发布日期 `source_date`。完整契约见 [DESIGN.md](DESIGN.md)。

## 本地运行

```powershell
cd workflows/exchange-rate-sync
python -m pip install -r requirements.txt
python -m uvicorn service.exchange_rate_service:app --host 0.0.0.0 --port 8770
```

测试：

```powershell
python -m pytest tests -q
```

实时冒烟：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8770/rates/resolve `
  -ContentType application/json `
  -Body '{"requested_date":"2026-07-12","currencies":["EUR","USD","CAD","HKD","SGD","JPY"]}'
```

## n8n 与 SAP

- n8n 负责调度、每日/月末规则、`EURX`/`M` 映射、SAP 调用和告警。
- service 只负责 CFETS 抓取、发布日期回退、校验和标准化。
- 生产 workflow ID：`fgeYDOpIx2lxNsAG`，每天北京时间 09:30 执行。
- SAP API environment 固定为 `prd`，PRD datasource 为 `sap_prd`。
- 月末按 `Asia/Shanghai` 的最后一个日历日判断。
- `GDATU` 发送普通 `YYYYMMDD`；NexCore 负责转换为 TCURR 内部倒置日期，workflow 不得预转换。
- SAP 写入节点不自动重试，避免有副作用的请求重复执行。

## 部署

- Base URL：`http://10.142.1.135:8770`
- 服务器目录：`/opt/exchange-rate-sync`
- systemd：`exchange-rate-sync.service`

```bash
ssh n8n "systemctl status exchange-rate-sync --no-pager -n 30"
ssh n8n "curl -sS http://localhost:8770/health"
```
