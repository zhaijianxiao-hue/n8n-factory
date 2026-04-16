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