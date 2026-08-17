# 踩坑记录与避坑指南

> 本文件记录开发过程中遇到的踩坑点，防止新会话重复犯错。
> **所有 agent 发现新踩坑时，必须登记到此文件。**

---

## 2026-04-16

### 1. n8n Docker 调用本地服务 URL 问题

**问题**: n8n workflow 调用本地服务，URL 用 `localhost:8766` 报错连接失败。

**根因**: n8n 运行在 Docker 容器内，`localhost` 指向容器自己，不是宿主机。

**解决**: 改用宿主机 IP 和目标服务的实际端口，例如 `10.142.1.135:8769`。

**预防规则**:
```
新服务部署到 n8n 同机时，workflow 中 HTTP Request URL：
❌ localhost:port（容器内部）
✅ 宿主机IP:port（10.142.1.135:实际服务端口）
```

**影响范围**: 所有 n8n workflow 调用同机部署的服务（例如 po-parser 8765、hana-query-api 8766、metal-price-sync 8769）。

---

### 2. HTML 解析预期结构与实际不符

**问题**: Parser 代码预期 `<span class="price-value">`，但实际网站是 `<tr id="g1">` 表格结构，导致抓取失败。

**根因**: 
- 编写 parser 时假设 HTML 结构，未先验证真实网站
- Fixture 文件是简化结构，与生产环境不符

**解决**: 
- 先用 curl 抓取真实 HTML，分析实际 DOM 结构
- 更新 fixture 与 parser 同时适配真实结构
- 铜价格发现是 JS 动态加载，需调用 API endpoint `tong.js`

**预防规则**:
```
Web 抓取开发流程：
1. ✅ 先 curl 抓取真实页面 → 分析 HTML 结构
2. ✅ 用真实 HTML 创建 fixture
3. ✅ Parser 代码匹配真实结构
4. ❌ 不要假设或猜测 DOM 结构

动态加载检测：
- 检查 <script> 标签中的数据加载逻辑
- 找真实 API endpoint（如 tong.js）
- 静态 HTML 抓取可能无法获取 JS 动态内容
```

**影响范围**: 所有 web scraping parser 开发（金价、铜价、其他数据抓取）。

---

## 2026-04-17

### 4. 服务代码与测试断言不同步

**问题**: 服务代码已改成 SAP GUID 格式（32位大写无连字符），但测试仍断言旧 UUID 格式（36位带连字符），导致测试失败。

**根因**: 
- 修改服务代码时未同步更新测试文件
- 测试与服务代码位于不同文件，容易遗漏
- 只关注功能实现，忽略了测试契约

**解决**:
- 先跑失败测试确认根因（而非猜测）
- 同步更新 `test_soap_body.py` 中的断言
- 使用 edit 工具分两步精确修改（docstring + 正则）
- 验证测试通过后再部署服务

**预防规则**:
```
服务代码修改时必须同步检查测试：
1. ✅ 修改服务代码后，立即 grep 相关测试文件
2. ✅ 跑相关测试，观察失败原因
3. ✅ 同步更新测试断言和说明
4. ✅ 本地验证通过后再部署
5. ❌ 不要只改服务，忽略测试同步

测试驱动修改流程：
- 发现不匹配 → 跑测试确认失败 → 定位根因 → 修改测试 → 验证通过 → 部署
```

**影响范围**: 所有服务端点修改，特别是涉及数据格式、字段定义、业务规则的改动。

---

### 5. 文件编辑工具选择问题

**问题**: 使用 apply_patch 工具编辑文件时频繁报错 "JSON Parse error"，无法完成编辑。

**根因**: 
- apply_patch 工具参数格式在当前环境不稳定
- 补丁内容中的特殊字符（中文、引号）可能导致解析失败
- 大量重复调用浪费时间和 token

**解决**: 改用 edit 工具，直接指定 oldString/newString 进行精确替换。

**预防规则**:
```
文件编辑优先级：
1. ✅ edit 工具（精确字符串替换，稳定可靠）
2. ⚠️ apply_patch（仅在简单英文补丁时尝试）
3. ❌ 避免重复调用失败的工具（浪费资源）

edit 工具最佳实践：
- 先 read 文件确认精确内容
- oldString 必须完全匹配（包括缩进、空格）
- 一次只改一小段，改完立即验证
- 不要试图一次改多个不连续位置
```

**影响范围**: 所有文件编辑操作（Python、JSON、Markdown等）。

---

## 2026-04-03

### 2. n8n If node V2 字段匹配问题

**问题**: If node V2 字段匹配失败，明明值相等却判定为 false。

**根因**: V2 版本 If node 默认不区分大小写，但某些字段值需要精确匹配。

**解决**: 在 If node conditions 中显式设置 `caseSensitive: true`。

**预防规则**:
```
n8n If node V2 比较字符串时：
✅ options.caseSensitive: true（精确匹配）
⚠️ 默认 false 可能导致意外匹配
```

---

### 3. Set node V3.4 类型问题

**问题**: Set node V3.4 定义的 array 字段实际输出为 object，导致下游节点处理异常。

**根因**: Set node V3.4 强类型检查，声明类型与实际值类型必须一致。

**解决**:
- 数组字段必须声明为 `type: "array"`
- 不要用 `type: "object"` 声明数组

**预防规则**:
```
n8n Set node V3.4 字段类型：
- 数组 → type: "array"
- 对象 → type: "object"
- 字符串 → type: "string"
- 数字 → type: "number"
```

---

## 2026-04-24

### 4. Exchange EWS 集成踩坑记录

**问题**: 通过 `exchangelib` 连接自建 Exchange 邮箱时，遇到认证失败、查询超时、密码特殊字符转义等多个问题。

**根因**: 
1. 自建 Exchange 不支持 IMAP，也不支持 Microsoft Graph API（Graph 仅适用于 Exchange Online）
2. exchangelib 默认 `autodiscover=True` 会尝试 DNS 自动发现，自建环境可能超时
3. 大邮箱（1300+ 封邮件）上 `has_attachments=True` + `is_read=False` 组合过滤慢 >120s
4. 密码中的 `!` 字符在 PowerShell 和 bash 中都会被解释为特殊字符

**解决**:
- 改用 EWS (exchangelib) 方案，`autodiscover=False`，手动指定服务器
- 登录用户名和邮箱地址可能不同（`yanan1.zhai@tcl.com` vs `zhaiyanan@tianjin-pcb.com`）
- 简化 EWS 过滤条件为仅按时间窗口 `datetime_received__gte`，附件检查和已读标记在客户端处理
- 默认 `days_back=1`，`max_emails=10`，n8n timeout 设为 180s
- 密码含特殊字符时，部署通过写入临时文件 + `scp` + `ssh sudo cp` 避免 shell 转义

**预防规则**:
```
Exchange EWS 集成检查清单：
1. ✅ 确认是 Exchange Online 还是自建 Exchange（自建不能用 Microsoft Graph）
2. ✅ exchangelib 配置使用 autodiscover=False，手动指定服务器
3. ✅ 确认 login username 与 mailbox address 可能不同
4. ✅ EWS 查询优化：只用时间窗口过滤，避免 has_attachments + is_read 组合
5. ✅ n8n HTTP Request 节点 timeout >= 120s（推荐 180s）
6. ✅ 密码特殊字符通过文件 + scp 部署，避免 shell 转义
7. ❌ 不要在自建 Exchange 上使用 IMAP 或 Outlook/Microsoft Graph 节点
```

**影响范围**: 自建 Exchange 环境下的邮件集成方案。

### 5. n8n HTTP Request 节点超时设置

**问题**: exchangelib 同步 I/O 查询大邮箱可能超过 n8n 默认 timeout（60s），导致 HTTP 请求被取消。

**根因**: n8n HTTP Request 节点默认 timeout 只有 60 秒，而 EWS 查询大邮箱可能 >120s。

**解决**: 在 n8n HTTP Request 节点设置 `options.timeout: 180000`（毫秒 = 180s）。

**预防规则**:
```
n8n HTTP Request 调用慢服务的超时策略：
1. ✅ 调用外部系统需评估实际耗时，保守设置 timeout
2. 🎯 Exchange EWS: 推荐 180s
3. 🎯 SAP RFC: 根据实际 SAP 响应时间调整
4. ❌ 不要保留默认 60s 超时
```

## 2026-04-29

### 6. n8n API PUT workflow 的 settings 字段限制

**问题**: 通过 n8n API 更新 workflow 时，`settings` 对象包含 `availableInMCP`、`binaryMode` 等字段导致 400 错误。

**根因**: n8n API 的 PUT `/workflows/{id}` 端点对 `settings` 做了严格校验，只接受 `executionOrder` 和 `callerPolicy` 两个字段。工作流导出 JSON 中可能包含额外字段（`availableInMCP`、`binaryMode`），直接回传会被拒绝。

**解决**: 构造 PUT payload 时，`settings` 只保留 `{"executionOrder": "v1", "callerPolicy": "workflowsFromSameOwner"}`，删除所有额外字段。

**预防规则**:
```
n8n API PUT 更新 workflow 的 payload 规则：
1. ✅ payload 只包含: name, nodes, connections, settings
2. ✅ settings 只保留: executionOrder, callerPolicy
3. ❌ 删除: availableInMCP, binaryMode, staticData, tags, pinData, meta
4. ✅ 先在测试脚本中验证，再应用到生产
```

**影响范围**: 所有通过 API 编程方式更新 n8n workflow 的场景。

### 7. Claude Code 新会话只自动加载 CLAUDE.md，不加载 AGENTS.md

**问题**: 项目中有 AGENTS.md 包含重要上下文（Exchange 配置、n8n 端点、踩坑规则），但新会话不会自动读取。

**根因**: Claude Code 默认只自动读取项目根目录的 `CLAUDE.md`（以及 `~/.claude/` 下的配置），不会自动加载 `AGENTS.md`。

**解决**: 在 `CLAUDE.md` 顶部添加 `@include AGENTS.md`，确保所有项目上下文在新会话中自动加载。

**预防规则**:
```
Claude Code 项目上下文文件优先级：
1. ✅ CLAUDE.md — 自动加载（项目根目录）
2. ✅ ~/.claude/rules/*.md — 自动加载（用户全局）
3. ⚠️ AGENTS.md — 需要 @include 或手动读取
4. ❌ 不要假设 AGENTS.md 会被自动加载
```

**影响范围**: 从 opencode 迁移到 Claude Code 的项目，或同时维护多个 AI 工具配置的项目。

### 8. exchangelib 时区对象类型错误

**问题**: 修复 `EWSTimeZone` 用法时，先改成 `datetime.timezone.utc`，线上仍报错 `InvalidTypeError: 'tzinfo' datetime.timezone.utc must be of type EWSTimeZone`。

**根因**: exchangelib 的 `EWSDateTime.now()` 严格要求传入 `EWSTimeZone` 类型，不接受标准库 `datetime.timezone`。

**解决**: 使用 `ewl.EWSTimeZone('UTC')` 创建时区对象。

**预防规则**:
```
exchangelib 时区使用规范：
1. ✅ ewl.EWSTimeZone('UTC') — 正确
2. ❌ ewl.EWSTimeZone.timezone("UTC") — 方法不存在
3. ❌ datetime.timezone.utc — 类型不匹配
4. ⚠️ 本地语法检查通过 ≠ 线上 exchangelib 版本兼容
```

**影响范围**: 所有使用 exchangelib 处理 Exchange EWS 时间过滤的场景。

### 9. unread_only 只标记已读，不等于只查询未读

**问题**: `/check-email` 请求里传了 `unread_only=true`，但服务实际仍会查询最近时间窗口内的全部邮件（已读 + 未读），只是处理完成后再把邮件标记为已读。

**根因**: `unread_only` 只用于处理后的 `item.is_read = True`，EWS 查询条件里没有同步加上 `is_read=False` 过滤。

**解决**: 构造 `filter_kwargs` 时，在 `request.unread_only` 为 true 的情况下显式加入 `is_read=False`，让 Exchange 查询阶段就只返回未读邮件。

**预防规则**:
```
邮件查询类开关命名检查：
1. ✅ 区分“查询过滤条件”和“处理后状态变更”是两件事
2. ✅ 参数名如果叫 unread_only，查询语句里必须能看到 is_read=False
3. ✅ 验证方式：首次查询命中未读邮件，第二次查询应返回 0 封
4. ❌ 不要只在处理后 mark as read，就认为实现了“只查未读”
```

**影响范围**: 所有基于 Exchange/EWS、IMAP 或邮件 API 的“未读邮件处理”逻辑。

### 10. n8n Set node V3.4 中数组字段必须声明为 array

**问题**: 工作流手动逐节点运行到 `输出-成功` 时，Set 节点报错：`'items' expects a object but we got array [item 0]`。

**根因**: `输出-成功` 节点里的 `items` 字段来自 `解析PDF` 的行项目列表，实际值是数组，但 Set node 中把该字段声明成了 `type: "object"`。n8n V3.4 会做严格类型校验，因此直接失败。

**解决**: 把 `items` 字段类型从 `object` 改成 `array`。同时检查其他输出节点，确认只有该节点包含 `items` 字段，`输出-审核` 和 `输出-失败` 不受影响。

**预防规则**:
```
n8n Set node V3.4 输出字段检查：
1. ✅ items / warnings / rows / list 这类字段优先怀疑是数组
2. ✅ 从上游表达式实际返回值反推 type，而不是按字段名猜测
3. ✅ 手动逐节点运行时，如出现 expects a object but we got array，优先检查 Set node assignment type
4. ✅ 修改后顺带排查同类输出节点，避免只修一个分支
5. ❌ 不要用 Ignore Type Conversion Errors 掩盖真实类型配置错误
```

**影响范围**: 所有使用 n8n `Set` 节点拼装结构化 JSON 输出的工作流。

### 11. SAP SOAP 报文时间字段不能混用本地时间和 UTC

**问题**: n8n 服务器在本地时间 2026-05-06 18:58 触发 SAP 发送，但 SAP 里记录的 `RTIME` 变成了 `10:54`，相差 8 小时。

**根因**: 代码里 `RDATE` / `RTIME` 使用了 `datetime.utcnow()` 生成 UTC 时间，而当前业务希望 SAP 记录服务器本地时间（Asia/Shanghai）。

**解决**: 统一改为 `datetime.now()` 生成 `RDATE` 和 `RTIME`，并补一个回归测试，确保不会再退回 UTC。

**预防规则**:
```
SAP SOAP 时间字段检查：
1. ✅ 先确认 SAP 期望的是服务器本地时间还是 UTC
2. ✅ RDATE 和 RTIME 必须来自同一个时间基准
3. ✅ 如果服务器按本地时间对账，优先用 datetime.now()
4. ✅ 为时间格式生成逻辑补回归测试，避免时区回退
5. ❌ 不要默认 datetime.utcnow() 一定正确
```

**影响范围**: 所有向 SAP 或其他外部系统发送业务时间戳的 SOAP / HTTP 集成。

### 12. UI 模式不等于服务端审批授权

**问题**: Profile Lab UI 区分了 Business Gate 和 Admin Gate，但早期版本只靠前端 `admin` 模式启用 Approve / Reject / Publish。任何能调用 API 的客户端仍可直接调用审批接口，绕过真实管理员审批。

**根因**: 前端视图状态被当成了权限边界，服务端只校验 `approval.json` 状态，没有校验调用方是否持有管理员授权。

**解决**: Admin Review 的 approve / reject / publish API 增加 `PO_PROFILE_LAB_ADMIN_TOKEN` 环境变量和 `X-PO-Profile-Lab-Admin-Token` 请求头校验；前端 Admin Review 先输入 token 才能打开审批运行并调用管理动作。

**预防规则**:
```
审批/上线类动作必须有服务端授权边界：
1. ✅ 前端 mode / tab / disabled 只做体验控制，不能当权限控制
2. ✅ approve / reject / publish 这类动作必须在 API 层校验管理员凭证
3. ✅ CLI publish 也要复用同一份发布门禁，不能绕开 approval.json
4. ❌ 不要只靠隐藏按钮或前端模式限制上线动作
```

**影响范围**: 所有内部工作台、审批流、上线发布类 API。

### 13. Profile Lab 上线不等于生产解析链路自动生效

**问题**: Profile Lab 中客户状态显示“已上线”后，容易误以为正式 `/parse` 服务会自动使用该客户 Profile；实际上如果生产 service 没有读取 `profiles/*.json`，新客户 PDF 仍会走通用解析逻辑。

**根因**: 发布动作只负责生成生产 Profile 产物，运行时解析服务还需要单独接入“加载已上线 Profile、按 marker 识别客户、把 Profile 上下文传给解析器”的链路。

**解决**: `po_parser_service.py` 运行时读取 `profiles` 目录中 `status=production` 且带 `markers` 的 Profile；识别命中后把 `customer_profile` 和 Profile 配置传给通用 LLM 抽取，并在输出 JSON 中保留客户 Profile。

**预防规则**:
```
Profile Lab 新客户上线闭环：
1. ✅ publish 生成 profiles/<customer>.json
2. ✅ Profile 必须包含稳定 markers，不能只靠 UI 状态
3. ✅ /parse 服务必须读取生产 Profile 并完成客户识别
4. ✅ 解析输出 customer_profile 应回填命中的客户
5. ❌ 不要把“已上线状态”当成“生产解析已接线”
```

**影响范围**: PO Profile Lab 到正式 PO Parser 服务的所有客户上线流程。

### 14. OpenAI-compatible 供应商不一定支持 Responses API

**问题**: n8n 工作台中 OpenAI 协议 credential 使用自定义 Base URL 可以保存，`/models` 也能刷出模型，但普通 `OpenAI` 节点选择 `Text -> Message a Model` 时，测试对话报 `404 status code (no body)` 和 LangChain `MODEL_NOT_FOUND`。

**根因**: n8n 2.12.2 的普通 `OpenAI` 节点 v2 `Text -> Message a Model` 会调用 `<base_url>/responses`。部分 OpenAI-compatible 供应商只实现 `/models` 和 `/chat/completions`，不实现 `/responses`，因此模型列表可用但真实对话 404。

**解决**: 实测可用方案是使用 `Basic LLM Chain` 连接子节点 `OpenAI Chat Model`，在 `OpenAI Chat Model` 中关闭 `Use Responses API`，继续使用 `https://ai.docker.tcl.com/imaas/v1` 这类带 `/v1` 的 OpenAI-compatible Base URL，并选择 `/models` 返回的精确模型 ID。

**预防规则**:
```
OpenAI-compatible 供应商接入 n8n AI Chat Model：
1. ✅ 先分别验证 /models、/chat/completions、/responses 三个端点
2. ✅ 如果 /responses 返回 404，避免用普通 OpenAI 节点的 Text -> Message a Model
3. ✅ 推荐 Basic LLM Chain / AI Agent + OpenAI Chat Model，并在 OpenAI Chat Model 关闭 Use Responses API
4. ✅ 模型名使用 /models 返回的精确 id，注意大小写和符号
5. ⚠️ Ollama 原生节点的 Base URL 不带 /v1；OpenAI-compatible 节点通常需要带 /v1
6. ❌ 不要把“Credential 保存成功 / models 能加载”当成“chat 接口可用”
```

**影响范围**: 所有在 n8n 中通过 `OpenAI Chat Model` 节点接入第三方 OpenAI-compatible 网关、公司模型网关或 LiteLLM/vLLM 类服务的场景。

### 15. n8n HTTP Basic Auth 不等于服务端出站 SAP 认证

**问题**: n8n HTTP Request 节点给 `po-parser` 的 `/to-sap` 配了 Basic Auth，容易误以为这组凭据会被继续用于调用 SAP 生产系统。

**根因**: Basic Auth 只在 n8n 调用 `po-parser` 服务时发送给本地 FastAPI 服务；`po-parser` 转发到 SAP 时使用的是服务端环境变量里的 `SAP_USER` / `SAP_PASS`，两段认证链路彼此独立。

**解决**: 保留 `/to-sap` 作为测试系统 endpoint，新增 `/to_sap_prd` 作为生产系统 endpoint，并分别配置 `SAP_*` 与 `SAP_PRD_*` 环境变量；生产 workflow 的 SAP 节点指向 `/to_sap_prd`。

**预防规则**:
```
n8n -> 本地服务 -> SAP 这类两跳调用：
1. ✅ 先区分入站认证和出站认证
2. ✅ n8n credential 只保证能调用本地服务，不自动传递给 SAP
3. ✅ 测试/生产 SAP 必须拆 endpoint 或显式选择目标环境
4. ✅ 生产凭据放 systemd/env secret，不写入 workflow JSON 或仓库
5. ❌ 不要把 HTTP Request 节点的 Basic Auth 当成 SAP 出站账号
```

**影响范围**: 所有 n8n 调用本地 FastAPI 服务，再由服务转发 SAP/ERP/外部系统的工作流。

### 16. SAP HTTPS 证书要匹配实际服务端证书和访问主机名

**问题**: 生产 SAP 地址用 `https://10.142.1.30:44300/...` 调用时报 `certificate verify failed: self-signed certificate`。业务侧提供了 `toppcb.com.cer`，但该证书是 `*.toppcb.com / toppcb.com`，与 SAP 实际返回证书不一致。

**根因**: `10.142.1.30:44300` 实际返回自签证书 `CN=s4pascs.tpc2.tianjin-pcb.com`，且没有 `subjectAltName`。继续用 IP 访问会导致证书主机名不匹配；使用不相关的公网证书也无法建立信任链。

**解决**: 从 SAP 服务端导出实际自签证书，配置为 `SAP_PRD_CA_BUNDLE`；将 `SAP_PRD_URL` 改为证书 CN 对应主机名，并在服务器 `/etc/hosts` 映射到 `10.142.1.30`。

**预防规则**:
```
SAP HTTPS 证书排查：
1. ✅ 先用 openssl s_client 查看服务端实际返回的 subject / issuer / SAN
2. ✅ CA bundle 必须信任实际服务端证书或其签发 CA
3. ✅ URL host 必须匹配证书 SAN 或 CN，不要直接用 IP 绕过主机名
4. ⚠️ 没有 SAN 的证书只能临时依赖 CN fallback，长期应让 Basis 重签带 SAN 的证书
5. ❌ 不要把文件名像 toppcb.com.cer 的证书默认当成 SAP 当前服务证书
```

**影响范围**: 所有通过 HTTPS 调用自签名 SAP NetWeaver / RFC SOAP 服务的场景。

### 17. EVYTRA 行项目客户物料不一定是纯数字

**问题**: EVYTRA PDF `Order2261643.pdf` 能识别到 `customer_profile=evytra`，但 `items=[]`，导致生产 workflow 输出空行项目并进入 review。

**根因**: EVYTRA 专属解析器早期按旧样本假设 `customer_material` 是纯数字；新样本行项目为 `AN00R08236 / FUX3001 743873 ÄI013 TA`。直接放宽正则后，电话号里的 `20 3902 14` 又可能被误识别成行项目起点。

**解决**: EVYTRA item header 匹配必须锚定“独立行号 + article + qty + customer material + TA + pcs”的真实表格结构；客户物料允许字母、数字、空格、斜杠等内容，但不能从正文任意位置开始匹配。

**预防规则**:
```
EVYTRA PDF 行项目解析：
1. ✅ customer_material 不能假设为纯数字
2. ✅ item line_no 必须是独立行开头的 10/20/30/40
3. ✅ 放宽正则后必须用真实 PDF 文本复核，防止电话号/日期误匹配
4. ✅ 新版 EVYTRA 样本要覆盖 alphanumeric customer_material
5. ❌ 不要只用旧 fixture 判断 EVYTRA 行项目解析已经稳定
```

**影响范围**: EVYTRA 及所有依赖 PDF 文本层正则解析行项目的客户 Profile。

### 18. Docker 拉取 n8n 镜像时代理要配给 Docker daemon

**问题**: 升级服务器 n8n Docker 镜像时，`docker compose pull n8n` 长时间卡住；服务器直连 `registry-1.docker.io` 被拒绝或超时，但 `curl -x http://10.142.192.59:10808` 可以访问 Docker Hub。

**根因**: `docker pull` 的出网请求由 Docker daemon 发起，不由当前 shell 的 `curl` 或普通命令环境发起。只验证 shell 代理可用，或只给当前命令设置代理，不能保证 Docker daemon 拉镜像也会走代理。

**解决**: 在服务器 `/etc/systemd/system/docker.service.d/http-proxy.conf` 给 Docker daemon 配置 `HTTP_PROXY` / `HTTPS_PROXY` 后 `systemctl daemon-reload && systemctl restart docker`，再拉取明确版本镜像，例如 `n8nio/n8n:2.23.4`。升级前先确认 n8n 数据目录是持久化挂载，并备份 `n8n_data`。

**预防规则**:
```
n8n Docker 升级拉镜像：
1. ✅ 先确认 Docker daemon 能通过代理访问 Docker Hub，而不是只测 curl
2. ✅ 需要代理时，把 HTTP_PROXY / HTTPS_PROXY 配到 docker.service 的 systemd drop-in
3. ✅ 拉明确稳定版本镜像，升级前备份 n8n_data 并保留旧镜像回滚 tag
4. ⚠️ 重启 Docker daemon 可能造成 n8n 短暂闪断，先通知再操作
5. ❌ 不要把当前 shell 能访问外网误认为 docker pull 一定可用
```

**影响范围**: 所有在受限网络服务器上通过 Docker / Docker Compose 升级 n8n 或其他容器镜像的场景。

### 19. 同机服务端口冲突会让 workflow 打到错误 service

**问题**: `Metal Price Sync - 每日金属价格同步` 的 `获取金铜价格` 节点请求 `http://10.142.1.135:8766/prices/latest` 返回 404，n8n 显示 `The resource you are requesting could not be found`。

**根因**: 线上 `hana-query-api.service` 已经占用 `8766`，`metal-price-sync.service` 仍尝试绑定 `8766`，因此反复重启并报 `[Errno 98] address already in use`。workflow 请求 `8766` 时实际打到了 HANA Query API，HANA 服务没有 `/prices/latest` 路由，所以返回 404。

**解决**: 给 `metal-price-sync.service` 增加 systemd drop-in 设置 `SERVICE_PORT=8769`，重启服务后验证 `/health` 返回 `service=metal-price-sync`；同时把生产 workflow 中 `获取金铜价格` 和 `构建 SOAP Body` 两个 HTTP Request 节点改到 `http://10.142.1.135:8769`。

**预防规则**:
```
同机部署多个 FastAPI service 时：
1. 先用 systemctl status/journalctl 看目标 service 是否真实 active
2. 用 /health 校验返回的 service 名，不要只看端口 200
3. 用 ss -ltnp 确认端口占用进程
4. workflow URL、systemd SERVICE_PORT、产品 KNOWLEDGE 必须同步
5. 端口冲突导致的 404 优先怀疑“请求打到另一个服务”
```

**影响范围**: 所有 n8n 同机部署的 service，尤其是 `hana-query-api`、`metal-price-sync`、`po-parser`、`screenshot-service` 等端口固定服务。

### 20. Playwright full_page 不会自动展开内部滚动容器

**问题**: `screenshot-service` 请求里设置了 `full_page: true`，但 NexReport 报表页截图仍只截到一屏；手工打开页面时实际可以向下滚动。

**根因**: Playwright 的 `page.screenshot(full_page=True)` 按 `document.body` / `documentElement` 的滚动高度截图，不会自动展开页面内部的滚动容器。NexReport 展示页外壳使用 `height: 100vh; overflow: hidden`，真正滚动的是 `.app-content { overflow-y: auto }`，因此 `body.scrollHeight` 只有视口高度。

**解决**: 对 NexReport `display_token` 展示模式增加专用布局 class，让展示页外壳和 `.app-content` 使用自然高度与 `overflow: visible`，使整页内容回到 body/document 滚动高度中；截图服务继续用原有 `full_page: true`。

**预防规则**:
```
排查 Playwright full_page 只截一屏：
1. 先量 document.body.scrollHeight / documentElement.scrollHeight
2. 再量主要容器（如 .app-content）的 clientHeight / scrollHeight / overflowY
3. 如果 body 只有一屏但内部容器 scrollHeight 很高，优先改页面展示/打印布局，而不是怀疑截图服务 full_page 失效
4. 对自动截图专用页面，避免 height: 100vh + 内部 overflow-y:auto；让 body 能自然承载整页高度
```

**影响范围**: 所有通过 `screenshot-service` 截取 React/Ant Design 大屏、报表页、后台页等固定视口布局的场景。

### 21. screenshot-service 的 delay_ms 上限和 n8n HTTP 超时不是一回事

**问题**: 慢报表需要更多时间渲染，旧版 n8n workflow 已把截图请求 `delay_ms` 设置为 `30000`，但继续把参数调大时截图服务会返回 422。

**根因**: `screenshot-service` 的旧版 `delay_ms` 字段在 FastAPI/Pydantic 入参校验中写死 `le=30000`，这是页面打开后额外等待时间的服务端硬上限。n8n HTTP Request 节点未显式配置 `options.timeout` 时，运行时代码会给请求设置 5 分钟默认超时，因此旧版限制主要在截图服务入参校验，不在 n8n 调用端。

**解决**: 把截图服务的最大等待时间改成环境变量 `SCREENSHOT_MAX_DELAY_MS`，默认 `300000`（5 分钟）；再把 workflow 截图节点的 `delay_ms` 调到不超过该上限。若显式设置 n8n HTTP Request `options.timeout`，应大于 `delay_ms + 页面加载超时 + 截图耗时`。

**预防规则**:
```
慢报表截图等待时间排查：
1. 先看 screenshot-service 的 delay_ms 校验上限，当前默认 300000ms，超过上限会 422
2. 再看 SCREENSHOT_TIMEOUT，它只控制 page.goto 页面打开阶段，不等于渲染后等待时间
3. n8n HTTP Request options 为空时默认请求超时是 5 分钟，不要误以为显示默认值 10000ms 一定生效
4. 调大等待时间时，服务端 delay_ms 上限、workflow delay_ms、n8n 请求 timeout 要一起对齐
5. 长期方案优先用页面 ready 标记或选择器等待，少依赖盲等
```

**影响范围**: 所有通过 `screenshot-service` 截取加载较慢的 NexReport 或其他网页报表的 workflow。

### 22. n8n 定时触发不会自动提供手动测试字段

**问题**: `Metal Price Sync - 每日金属价格同步` 的 `写入 SAP` 节点已经选了 `SAP Production System` 凭证，但正式定时运行仍可能打到测试 SAP URL，导致“凭证是生产、URL 是测试”的混合状态。

**根因**: `system_type` 只来自手动触发或上游输入；定时触发本身不提供这个字段。`获取 SAP 配置` Code 节点用 `$input.first().json.system_type || 'test'` 时，定时链路会默认走 `test`，而 HTTP Request 节点的 credential 只控制认证，不决定 URL。

**解决**: 生产 workflow 中移除 `选择系统` Switch 节点，让 `手动触发` 和 `定时触发` 都直接进入 `获取 SAP 配置`；`获取 SAP 配置` 固定输出生产 SAP endpoint 和 `SAP Production System`，同时确认 `写入 SAP` 节点使用 `httpBasicAuth` 和生产凭证。

**预防规则**:
```
n8n 手动/定时共用 workflow 做环境切换时：
1. 先检查定时触发路径是否真的会产生 system_type 等环境字段
2. 凭证选择不等于 URL 环境选择，二者必须分别验证
3. 若 workflow 已切正式生产，优先移除测试/生产切换节点，固定生产配置
4. 验证时查看“获取 SAP 配置”节点输出的 url，而不是只看“写入 SAP”节点 credential
```

**影响范围**: 所有同一 workflow 通过 `system_type`、`env`、`target` 等输入字段切换测试/生产外部系统的 n8n 定时任务。

### 23. n8n Docker 内 CLI 执行会与主进程 Task Broker 端口冲突

**问题**: 在运行中的 n8n Docker 容器里执行 `n8n execute --id=<workflow-id>` 时报错：`n8n Task Broker's port 5679 is already in use`。同一版本的公共 API 也不支持 `POST /api/v1/workflows/{id}/execute`，会返回 405。

**根因**: n8n 主进程已经启动了 task broker 并占用默认 `5679` 端口；容器内另起 CLI 执行时会再尝试启动一个 broker。公共 API 主要用于 workflow CRUD 和 execution 查询，不保证支持直接执行 workflow。

**解决**: CLI 手动执行时给本次命令指定临时 broker 端口，例如：
```
docker exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n-n8n-1 n8n execute --id=<workflow-id> --rawOutput
```
如果需要改变入口或测试特定路径，不要直接改生产 workflow；可临时创建一个未激活 workflow，执行后立即删除。

**预防规则**:
```
n8n Docker 线上手动执行 workflow：
1. 不要假设公共 API 有 /execute，可先确认端点是否返回 405
2. 容器内 n8n execute 需要避开主进程 task broker 端口
3. 用 N8N_RUNNERS_BROKER_PORT 指定未占用临时端口
4. 测特定路径时优先创建临时未激活 workflow，跑完删除，避免污染生产 workflow
```

**影响范围**: n8n 2.x Docker 部署中，通过 CLI 手动执行 workflow 或调试定时/手动触发路径的场景。

### 24. PowerShell 构造 n8n connections 二维数组会被自动压扁

**问题**: 用 PowerShell 通过 n8n API 更新 workflow connections 时，写成 `@(@(@{ node = ... }))` 后，PUT `/workflows/{id}` 返回 `connections.<node>.main[0] (invalid_type): Expected array, received object`。

**根因**: PowerShell 的数组展开规则会把嵌套单元素数组自动压扁，导致 n8n 需要的 `main: [[{...}]]` 被序列化成 `main: [{...}]`。

**解决**: 用显式 `System.Collections.Generic.List[object]` 构造外层和内层数组，再赋给 `connections.<node>.main`。

**预防规则**:
```
PowerShell 更新 n8n workflow connections：
1. n8n connections.main 必须是二维数组：[[{ node, type, index }]]
2. 单元素嵌套数组不要直接用 @(@(...))，容易被 PowerShell 压扁
3. PUT 前可先 ConvertTo-Json 检查 main 是否仍是 [[...]]
4. 若 n8n 报 Expected array, received object，优先检查连接数组维度
```

**影响范围**: 所有用 PowerShell 直接构造 n8n workflow JSON 并通过 API 更新连接结构的场景。

### 25. package.json 中声明的 workflow 脚本不一定真实存在

**问题**: 执行 `npm run validate` 报 `Cannot find module 'scripts/validate-workflows.js'`；`npm run deploy` 同样引用尚不存在的 `scripts/deploy.js`，根 README 还曾指向不存在的 `scripts/deploy.sh`。

**根因**: `package.json` 和 `scripts/README.md` 保留了脚手架阶段的命令与规划，但实际 JS 脚本从未加入仓库。

**解决**: 当前 workflow 验证、读取和部署统一使用项目 `.opencode/skill/n8n/`；README 明确标注 `scripts/` 只有规划文档。在真正补齐并验证脚本前，不把 npm validate/deploy 当作可用入口。

**预防规则**:
```
调用仓库脚本前：
1. ✅ 先确认 package.json 指向的实际文件存在
2. ✅ n8n 操作优先使用项目 n8n skill
3. ✅ 验证报告必须记录真实命令和退出码
4. ❌ 不要仅凭 package.json 或 scripts/README.md 推断脚本可运行
```

**影响范围**: 本仓库所有 workflow 验证和部署任务。

### 26. po-parser 测试依赖文件不是完整测试环境清单

**问题**: 直接按 `workflows/po-parser/tests/requirements.txt` 理解测试环境时，pytest 收集仍可能因缺少 `jsonschema` 失败；异步测试还会因缺少 `pytest-asyncio` 出现 unknown mark，n8n skill 的 Python 工具缺少 `requests` 时也无法启动。

**根因**: 当前测试依赖文件只列了 PDF 解析和模型调用依赖，没有覆盖测试框架、Schema 校验、异步插件及 n8n 工具依赖。

**解决**: 运行测试前先核对测试文件的 import 和 pytest mark，并使用已配置完整依赖的环境；若要建立可复现环境，应先补齐并验证依赖清单，本次知识库审计不修改全局 Python 环境。

**预防规则**:
```
po-parser 测试环境检查：
1. ✅ 不把 tests/requirements.txt 当作完整锁定清单
2. ✅ 至少检查 pytest、pytest-asyncio、jsonschema、requests 和服务运行依赖
3. ✅ 依赖缺失导致 collection error 时，报告“未运行”，不能报告“测试失败”或“测试通过”
4. ❌ 不为一次验证静默修改全局 Python 环境
```

**影响范围**: po-parser 本地回归测试、CI 初始化和项目 n8n Python 工具验证。

### 27. n8n Code 节点可能禁止读取环境变量

**问题**: 汇率 workflow 的 Code 节点读取 `$env.FORCE_MONTH_END` 时，执行立即失败并报 `access to env vars denied`，尚未进入后续 HTTP Request 节点。

**根因**: 当前 n8n 运行环境禁止节点访问环境变量；Code 节点或表达式里出现 `$env` 不代表部署环境一定允许读取。

**解决**: 不在 Code 节点依赖 `$env` 传入测试开关或业务配置；改用上游输入、固定配置节点或 n8n 支持的安全配置方式。上线前用真实执行验证，不只做结构校验。

**预防规则**:
```
n8n workflow 使用环境变量：
1. ✅ 先用最小手动执行确认当前实例是否允许节点读取 $env
2. ✅ 测试开关优先通过显式输入或配置节点传递
3. ✅ 结构 validate 通过后仍要做运行时验证
4. ❌ 不要假设容器里已设置变量，Code/Expression 节点就一定能读取
```

**影响范围**: 所有在 Code、Set、HTTP Request 等节点表达式中使用 `$env` 的 workflow。

### 28. Schedule 节点名称不决定实际执行时区

**问题**: 汇率 workflow 的节点名写着 `Daily 08:05 JST`，但 workflow 未设置独立时区；当前 n8n 容器的 `GENERIC_TIMEZONE` 和 `TZ` 均为 `Asia/Shanghai`，因此 cron 实际按北京时间 08:05 执行。

**根因**: Schedule Trigger 的 cron 表达式使用 workflow 或 n8n 实例时区，节点名称和 Code 节点里的日期计算时区不会改变调度时区。

**解决**: 明确设置 workflow 时区，或按实例时区换算 cron；同时让调度时区、日期计算时区和文档保持一致。

**预防规则**:
```
n8n 定时任务时区检查：
1. ✅ 核对 workflow timezone 和容器 GENERIC_TIMEZONE/TZ
2. ✅ 节点名称、cron、业务日期计算使用一致时区
3. ✅ 上线前用服务器当前时间和一次实际触发验证
4. ❌ 不要把节点名中的 JST/CST 当成真实调度配置
```

**影响范围**: 所有使用 Schedule Trigger，尤其是跨时区、日末或月末判断的 workflow。

### 29. SAP TCURR-GDATU 的外部日期与 RFC 内部日期可能不同

**问题**: 汇率 API 文档要求 `GDATU` 直接传 `YYYYMMDD`，但 QAS 实测传 `20260713` 时 SAP Function 对全部行返回“日期无效”；改传 TCURR 的内部倒置日期 `79739286` 后不再触发日期校验错误，而进入后续表锁检查。

**根因**: `TCURR-GDATU` 使用倒置日期存储。通过 RFC/PyRFC 直接映射 TCURR 结构时，不一定自动执行 SAP GUI/ABAP 屏幕层的日期转换；外部 API 若承诺接收普通 `YYYYMMDD`，必须在 API 或 Function 边界显式转换后再传入 TCURR 结构。

**解决**: 当前 NexCore 汇率 API 保持外部 `YYYYMMDD` 契约，并在 operation 边界完成 TCURR 内部日期转换。Workflow 发送普通日期，不得预转换；同时保留普通有效日期用于审计，并用 PRD/QAS 回归测试确认映射。

**预防规则**:
```
SAP 汇率 GDATU 集成：
1. ✅ 区分 API 外部日期契约和 TCURR-GDATU 内部存储值
2. ✅ 用 QAS 实际调用验证转换发生在哪一层
3. ✅ 转换集中在 NexCore/SAP API 边界，并补普通日期到倒置日期的回归测试
4. ❌ 不要仅凭字段名或 API 文档假设 RFC 会自动执行 INVDT 转换
```

**影响范围**: 所有通过 RFC/BAPI/自定义 Function 写入 TCURR 或复用 `TCURR-GDATU` 数据元素的集成。

### 30. Windows ZoneInfo 需要显式安装 tzdata

**问题**: exchange-rate-sync 在 Windows 测试环境调用 `ZoneInfo("Asia/Shanghai")` 时抛出 `ZoneInfoNotFoundError`，导致 API 测试失败。

**根因**: Windows 通常没有 Python `zoneinfo` 可直接读取的系统 IANA 时区数据库；项目依赖中也没有安装 PyPI `tzdata`。

**解决**: 在 exchange-rate-sync 的运行依赖中加入 `tzdata>=2024.1`，让 Windows 和缺少系统时区数据库的环境都能解析 `Asia/Shanghai`。

**预防规则**:
```
Python ZoneInfo 跨平台检查：
1. ✅ 使用 IANA 时区名称时把 tzdata 纳入运行依赖
2. ✅ 在 Windows 环境实际构造 ZoneInfo("Asia/Shanghai") 验证
3. ✅ CI 至少覆盖一个没有系统 tzdata 的环境
4. ❌ 不要因 Linux 服务器可用就假设 Windows 本地测试也可用
```

**影响范围**: 所有使用 Python `zoneinfo` 和 IANA 时区名称的跨平台 service 与测试。

### 31. Windows 运行 n8n Python 验证器要显式使用 UTF-8

**问题**: 项目 n8n 验证器读取包含中文节点名的 workflow JSON 时，在 Windows 上报 GBK 解码错误，无法完成结构验证。

**根因**: 验证脚本读取文本时依赖 Python 默认编码；中文 workflow 是 UTF-8，而当前 Windows Python 默认文本编码为 GBK。

**解决**: 运行验证器前设置 `PYTHONUTF8=1`，让 Python 以 UTF-8 模式读取 workflow JSON。

**预防规则**:
```
Windows 本地验证中文 workflow：
1. ✅ PowerShell 先执行 $env:PYTHONUTF8='1'
2. ✅ 再运行 .opencode/skill/n8n/scripts/n8n_tester.py validate
3. ✅ 区分编码失败和 workflow 结构失败
4. ❌ 不要因 GBK UnicodeDecodeError 误判 JSON 已损坏
```

**影响范围**: Windows 上所有包含中文节点名或中文参数的 n8n workflow Python 验证任务。

## 待登记模板

发现新踩坑时，按以下格式添加：

```markdown
### X. [踩坑标题]

**问题**: [问题描述]

**根因**: [根本原因]

**解决**: [解决方案]

**预防规则**:
```
[简明的预防规则，新会话可直接引用]
```

**影响范围**: [哪些场景可能复现]
```
