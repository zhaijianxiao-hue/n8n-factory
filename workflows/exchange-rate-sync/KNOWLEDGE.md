# Exchange Rate Sync 产品知识

## 当前状态

- 阶段：生产运行
- 生产 workflow：`fgeYDOpIx2lxNsAG`，名称 `SAP 汇率同步 - CFETS → OB08 (PRD)`
- Workflow 版本：20，已激活
- SAP OB08 API：QAS、PRD 均已注册；生产 workflow 固定使用 `prd`
- Service Base URL：`http://10.142.1.135:8770`
- 部署路径：`/opt/exchange-rate-sync`
- systemd unit：`exchange-rate-sync.service`

## 职责边界

```text
n8n -> exchange-rate-sync service -> 标准化汇率
  └-> SAP OB08 API（后续）
```

- n8n：调度、频次、汇率类型、SAP 写入、执行汇总和告警。
- service：CFETS 查询、历史回退、标准化和完整性校验。
- SAP API：落地 OB08/TCURR 相关数据并返回逐项结果。

## 官方数据源

- Provider：CFETS
- 历史 JSON：`https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew`
- 官方页面：`https://www.chinamoney.com.cn/chinese/bkccpr/`
- 发布时间：工作日北京时间 09:15 左右

生产口径不自动降级到 ECB、Frankfurter 或银行牌价。若 CFETS 不可用，service 返回 502，n8n 必须阻断 SAP 写入。

## 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 服务健康和版本信息 |
| `/rates/resolve` | POST | 按请求日批量解析外币兑 CNY 中间价 |

## 标准化规则

| 币种 | CFETS pair | FROM_FACTOR | TO_FACTOR |
|------|------------|-------------|-----------|
| EUR | EUR/CNY | 1 | 1 |
| USD | USD/CNY | 1 | 1 |
| CAD | CAD/CNY | 1 | 1 |
| HKD | HKD/CNY | 1 | 1 |
| SGD | SGD/CNY | 1 | 1 |
| JPY | 100JPY/CNY | 100 | 1 |

- 查询 `[requested_date-lookback_days, requested_date]`。
- 选择不晚于 `requested_date` 的最大发布日期。
- 返回顺序与请求币种顺序一致。
- 任一币种缺失、非数字或非正数，整批失败。

## Workflow 结构

1. Schedule/Manual 产生业务日期和到期汇率类型。
2. 去重币种并批量调用 `/rates/resolve`。
3. 将 EUR 汇率按配置展开为 `EURX` 和/或 `M`。
4. 构建 SAP API 批量请求，并保留 provider、source_date 和业务有效日期用于审计。
5. 聚合逐项返回；任一失败则整体告警。

调度和日期计算统一使用 `Asia/Shanghai`。使用当日 CFETS 数据时，计划在北京时间 09:30 后执行。

## SAP API 与联调结果

- API：`POST http://10.142.3.84:8000/api/v1/finance/exchange-rate`
- 环境：`qas -> sap_qas`、`prd -> sap_prd`
- 2026-07-13 端到端测试：CFETS 获取和批量请求构建成功，SAP 返回三行“日期无效”
- 文档约定 `GDATU=20260713`，但 QAS 实测 TCURR 内部倒置日期 `79739286` 能通过日期校验并进入下一步
- 倒置日期测试随后持续返回 `E_TABLEE 当前由用户 ZHAIYANAN 锁定`
- 初期 QAS 调试曾由 workflow 发送倒置日期；NexCore 后续已在 API 边界实现普通日期到 TCURR 内部日期的转换
- 当前契约：workflow 必须发送普通 `YYYYMMDD`，不得预转换；例如 `20260714` 由 NexCore 映射为 `79739285`
- 2026-07-13 再次执行后表锁已释放，SAP 返回 `status=S`、`message=3 表记录被计划更新`、`rate_count=3`
- 最终节点核对环境、状态和条数成功，QAS 端到端执行状态为 `success`
- 2026-07-13 PRD 端到端验证：发送普通 `GDATU=20260713`，环境 `prd`，SAP 返回 `status=S`、`message=3 表记录被计划更新`、`rate_count=3`
- PRD 验证成功后已激活 workflow；当前 active version id：`deb24875-a72e-4ec4-a8dd-d8292b3402d0`

## 频次确认

- 月末定义为 `Asia/Shanghai` 的最后一个日历日，不是最后一个工作日。
- 普通日期写 3 行：EURX EUR/CNY、M EUR/CNY、M USD/CNY。
- 月末在上述 3 行基础上增加 4 行：M CAD/HKD/SGD/JPY → CNY。
- 月末若为周末或节假日，汇率来源回退到最近发布日期，但 `valid_from` 仍为月末日历日。

## 运维命令

```bash
ssh n8n "systemctl status exchange-rate-sync --no-pager -n 30"
ssh n8n "journalctl -u exchange-rate-sync --no-pager -n 80"
ssh n8n "curl -sS http://localhost:8770/health"
```
