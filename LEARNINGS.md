# 踩坑记录与避坑指南

> 本文件记录开发过程中遇到的踩坑点，防止新会话重复犯错。
> **所有 agent 发现新踩坑时，必须登记到此文件。**

---

## 2026-04-16

### 1. n8n Docker 调用本地服务 URL 问题

**问题**: n8n workflow 调用本地服务，URL 用 `localhost:8766` 报错连接失败。

**根因**: n8n 运行在 Docker 容器内，`localhost` 指向容器自己，不是宿主机。

**解决**: 改用宿主机 IP `10.142.1.135:8766`。

**预防规则**:
```
新服务部署到 n8n 同机时，workflow 中 HTTP Request URL：
❌ localhost:port（容器内部）
✅ 宿主机IP:port（10.142.1.135:port）
```

**影响范围**: 所有 n8n workflow 调用同机部署的服务（po-parser 8765、metal-price-sync 8766 等）。

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