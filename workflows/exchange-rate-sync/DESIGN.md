# Exchange Rate Sync 设计

## 目标

- 将汇率抓取、回退和标准化从 n8n Code/HTTP 节点迁移到独立 FastAPI service。
- 以 CFETS/中国货币网发布的人民币汇率中间价为唯一生产主源。
- 一次请求批量返回本次需要的全部币种；任一币种缺失时整体失败。
- 为后续 SAP OB08 API 提供稳定、可审计的标准化输入。

## 非目标

- 本阶段不调用 SAP，不实现或模拟 SAP Function。
- 本阶段不修改或激活生产 n8n workflow。
- 不在 CFETS 失败时自动切换 ECB、Frankfurter 或银行牌价。
- 不在 service 中实现每日、月末或汇率类型选择；这些仍由 n8n 负责。

## 数据源

- Provider: `CFETS`
- 官方历史查询：`https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew`
- 页面来源：`https://www.chinamoney.com.cn/chinese/bkccpr/`
- 目标币种：`EUR`、`USD`、`CAD`、`HKD`、`SGD`、`JPY`
- JPY 原始报价是 `100JPY/CNY`，返回 `from_factor=100`；其他币种为 1。

查询请求日之前的回看窗口，选择不晚于请求日的最新发布记录。周末和节假日允许回退，但响应必须同时返回 `requested_date` 和 `source_date`。

## API 契约

### `GET /health`

返回服务名、版本、端口和 provider。

### `POST /rates/resolve`

请求：

```json
{
  "requested_date": "2026-07-12",
  "currencies": ["EUR", "USD", "CAD", "HKD", "SGD", "JPY"],
  "lookback_days": 10
}
```

成功响应：

```json
{
  "status": "success",
  "provider": "CFETS",
  "requested_date": "2026-07-12",
  "source_date": "2026-07-10",
  "fetched_at": "2026-07-13T06:00:00Z",
  "source_url": "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew",
  "rates": [
    {
      "from_currency": "JPY",
      "to_currency": "CNY",
      "rate": 4.1876,
      "from_factor": 100,
      "to_factor": 1,
      "source_pair": "100JPY/CNY"
    }
  ],
  "warnings": ["requested_date 2026-07-12 used source_date 2026-07-10"]
}
```

错误策略：

- 非法币种、未来日期或非法回看窗口：HTTP 422。
- 上游不可用、响应异常、没有发布日期或任一币种缺失：HTTP 502。
- 不返回部分成功结果。

## 后续 n8n 结构

```text
Schedule / Manual
  -> Build due rate types and unique currencies
  -> POST exchange-rate-service /rates/resolve
  -> Validate complete response
  -> Expand rate types (EUR may emit EURX and M)
  -> Build SAP request
  -> Call SAP OB08 API
  -> Aggregate per-item result and notify
```

生产计划时区统一为 `Asia/Shanghai`。如果使用当日 CFETS 中间价，建议北京时间 09:30 后运行。

月末定义为最后一个日历日。Workflow 向 NexCore 发送普通 `YYYYMMDD`；NexCore 在 SAP API 边界将其转换为 `TCURR-GDATU` 内部倒置日期。消费者不得预转换，同时保留普通业务有效日期用于日志和审计。

## 验收标准

- 能解析 CFETS 历史响应并按请求日正确回退。
- 六个目标币种均能标准化为外币兑 CNY。
- JPY 使用 100:1 换算因子，其他币种使用 1:1。
- 缺少任一请求币种时整体失败。
- FastAPI 输入校验、上游错误和健康检查有自动化测试。
- 实时冒烟测试能从部署环境读取 CFETS 最新数据，但不作为默认离线测试的一部分。
