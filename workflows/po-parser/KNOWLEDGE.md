# PO Parser 产品知识

> 本文件是 `po-parser` 的产品级知识所有者。跨产品规则见根 `KNOWLEDGE.md`，重复踩坑见根 `LEARNINGS.md`。

Status: Active
Last Reviewed: 2026-07-10
Confidence: High（仓库定义）；生产运行态在本次审计中未实时核验

---

## 产品边界

`po-parser` 把客户采购订单 PDF 转换为统一 PO JSON，并由 n8n 负责调度、状态分支、SAP 写入和文件归档。

稳定边界如下：

- 保持一个共享 n8n workflow，不为每个客户复制整套流程。
- 客户识别、规则解析、通用 LLM 抽取和 SAP 报文转换放在 Python service。
- Profile Lab 负责客户样本、评测、审批和发布；正式 `/parse` 只消费已接入运行时的 Profile。
- `success`、`review`、`error` 是解析状态；警告与硬错误分开处理。

## 知识与代码所有者

| 内容 | 所有者 |
|------|--------|
| n8n 节点和连接 | `workflow.json` |
| 解析、Profile 路由、Exchange、SAP 转发 | `service/po_parser_service.py` |
| 输出数据契约 | `schemas/po-output.schema.json` |
| 已发布 Profile | `profiles/*.json` |
| Profile Lab 核心 | `profile_lab/` |
| Profile Lab API / UI | `profile_lab_ui/`、`profile-lab/` |
| 回归测试 | `tests/` |
| 通用 Exchange 规则 | `../../topics/exchange/KNOWLEDGE.md` |
| 通用 SAP 规则 | `../../topics/sap/KNOWLEDGE.md` |

修改 workflow 行为时必须同时检查 `workflow.json` 和 service；修改输出字段时必须同步检查 service、Schema、workflow Set 节点和测试。

## 仓库当前工作流

仓库中的 `workflow.json` 定义每分钟扫描一次：

```text
定时触发
  -> POST /scan
  -> 拆分文件
  -> POST /parse
  -> status 为 success 或 review？
       ├─ 是 -> POST /to-sap -> SAP TYPE == S？
       │        ├─ 是 -> success 移到 done；review 移到 review
       │        └─ 否 -> 移到 error
       └─ 否 -> 移到 error
```

仓库版本的 SAP 节点当前调用测试端点 `/to-sap`。线上生产 workflow 可能使用 `/to_sap_prd`；部署或排障前必须通过项目 n8n skill 读取线上 workflow，不要仅凭本地 JSON 推断生产状态。

## 部署信息

以下值来自仓库指令和文档，属于易漂移的运行环境知识；本次审计未连接生产环境复核：

| 项目 | 记录值 |
|------|--------|
| 主 workflow ID | `BCPYC0kDhe8s9fVJ` |
| 主 workflow 名称 | `PO-Parser - 采购订单PDF解析` |
| Parser Base URL | `http://10.142.1.135:8765` |
| 服务代码 | `/opt/po-parser/po_parser_service.py` |
| systemd unit | `po-parser.service` |

仓库记录的生产 SAP HTTPS 链路使用 `https://s4pascs.tpc2.tianjin-pcb.com:44300/...`，服务器 `/etc/hosts` 映射到 `10.142.1.30`，CA bundle 为 `/opt/po-parser/certificate/sap-prd-selfsigned.crt`。业务侧提供的 `toppcb.com.cer` 与服务端实际证书不匹配；证书排障以 `openssl s_client` 返回的 subject、issuer 和 SAN 为准。

当前目录约定：

| 用途 | 路径 |
|------|------|
| 输入 | `/mnt/smb/po_pdfs/incoming` |
| 人工复核 | `/mnt/smb/po_pdfs/review` |
| 成功归档 | `/mnt/smb/po_pdfs/done` |
| 失败归档 | `/mnt/smb/po_pdfs/error` |
| JSON 输出 | `/mnt/smb/po_pdfs/output` |

## Parser Service

默认端口为 `8765`，生产 systemd unit 为 `po-parser.service`，生产代码路径为 `/opt/po-parser/po_parser_service.py`。

| 端点 | 方法 | 职责 |
|------|------|------|
| `/health` | GET | 返回服务状态和当前模型配置 |
| `/scan` | POST | 按目录和 pattern 列出 PDF；默认 `*.pdf` 对扩展名大小写兼容 |
| `/parse` | POST | 提取 PDF 文本、识别客户、解析并落盘标准 JSON |
| `/move` | POST | 把源文件移动到目标目录 |
| `/check-email` | POST | 从自建 Exchange 下载符合 PO 规则的 PDF 附件 |
| `/to-sap` | POST | 使用服务端 `SAP_*` 环境变量发送到测试 SAP |
| `/to_sap_prd`、`/to-sap-prd` | POST | 使用服务端 `SAP_PRD_*` 环境变量发送到生产 SAP |

n8n 调用 service 的入站认证与 service 调用 SAP 的出站认证彼此独立；SAP 凭据只能放在服务端环境配置中，不写入 workflow JSON 或仓库。

## 输出契约与路由

`POResult` 的稳定主字段：

- `source_file`、`customer_profile`、`file_hash`、`process_time`
- `header`、`items`
- `confidence`、`warnings`
- `status`：`success | review | error`
- `output_file`

Schema 的根级必填字段是 `source_file`、`file_hash`、`header`、`items`、`confidence`。`items` 是数组；n8n Set V3.4 输出该字段时必须声明 `type: "array"`。

路由语义：

- `success`：结构和业务校验通过；SAP 成功后进入 `done`。
- `review`：允许继续发送 SAP，但原 PDF 在 SAP 成功后进入 `review`，等待人工复核。
- `error`：不发送 SAP，直接进入 `error`。
- SAP 返回失败：无论原解析是 `success` 还是 `review`，都进入 `error`。

## 客户 Profile 运行时

运行时 Profile 目录由 `PO_PARSER_PROFILES_DIR` 指定，默认是 `profiles/`。

识别顺序：

1. 扫描 `profiles/*.json`。
2. 只把 `status=production` 且 `markers` 非空的文件作为通用已发布 Profile。
3. 所有 markers 归一化后都命中 PDF 文本，才识别为该 Profile。
4. EVYTRA 另有兼容识别和确定性解析器；它是规则优先的参考实现。
5. 其他已发布客户把 Profile 上下文传入通用 LLM 抽取。

发布闭环必须同时满足：Profile Lab 评测通过、审批通过、生成生产 Profile、运行时能按 markers 识别、`/parse` 输出回填 `customer_profile`。UI 显示“已上线”本身不证明生产解析链路已生效。

EVYTRA 的长期规则：

- 使用欧洲数字格式：小数逗号、千位点。
- 行项目必须锚定真实表格结构，不能从电话、日期等正文数字开始匹配。
- `customer_material` 允许字母、数字、空格、斜杠等，不能假设为纯数字。
- 可疑行金额、合计不一致或必填字段缺失应返回 `review`。

## Profile Lab

核心命令入口：

```powershell
cd workflows/po-parser
python -m profile_lab init-customer --customer evytra
python -m profile_lab_ui
```

UI 默认端口为 `8768`。审批相关动作 `approve`、`reject`、`publish` 必须在服务端校验 `PO_PROFILE_LAB_ADMIN_TOKEN`；前端 mode、tab 或按钮隐藏不是授权边界。审批 webhook 使用 `PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL`。

## 关键环境变量

| 领域 | 变量 |
|------|------|
| 模型 | `PO_PARSER_OPENAI_BASE_URL`、`PO_PARSER_OPENAI_API_KEY`、`PO_PARSER_TEXT_MODEL`、`PO_PARSER_VISION_MODEL` |
| Profile | `PO_PARSER_PROFILES_DIR` |
| Exchange | `EXCHANGE_SERVER`、`EXCHANGE_EMAIL`、`EXCHANGE_USERNAME`、`EXCHANGE_PASSWORD`、`EXCHANGE_INCOMING_DIR` |
| SAP 测试 | `SAP_URL`、`SAP_USER`、`SAP_PASS`、`SAP_CA_BUNDLE`、`SAP_VERIFY_SSL` |
| SAP 生产 | `SAP_PRD_URL`、`SAP_PRD_USER`、`SAP_PRD_PASS`、`SAP_PRD_CA_BUNDLE`、`SAP_PRD_VERIFY_SSL` |
| Profile Lab | `PO_PROFILE_LAB_ADMIN_TOKEN`、`PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL` 及 `PO_PROFILE_LAB_*` 模型配置 |

秘密值不进入 Git；仓库只保留示例变量名和无敏感信息的默认值。

## 验证入口

本地最小回归如下。当前 `tests/requirements.txt` 不是完整测试环境清单；执行前需确认环境已包含 pytest、pytest-asyncio、jsonschema、requests 以及 service 运行依赖：

```powershell
python -m pytest workflows/po-parser/tests/test_evytra_profile.py
python -m pytest workflows/po-parser/tests/test_runtime_profiles.py
python -m pytest workflows/po-parser/tests/test_check_email.py
python -m pytest workflows/po-parser/tests/test_sap_time.py
```

涉及 workflow JSON 时，先使用项目 `.opencode/skill/n8n/` 的验证工具验证本地文件；涉及线上行为时，再通过 n8n skill 获取 workflow 和 execution 数据。不能用“`/parse` 返回成功”代替端到端验证，至少还要确认 SAP 分支、文件移动和最终输出节点。

## 生产排障

```bash
ssh n8n "systemctl status po-parser --no-pager -n 30"
ssh n8n "journalctl -u po-parser --no-pager -n 80"
ssh n8n "curl -sS http://localhost:8765/health"
```

若 service 正常而 workflow 失败，优先读取最近失败 execution 的节点数据；顶层 execution 状态不足以解释 Set 类型错误、If 分支或最终文件移动问题。
