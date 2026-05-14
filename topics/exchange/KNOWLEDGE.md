# Exchange EWS 集成知识

> 自建 Exchange（非 Exchange Online）的 EWS 集成知识，供所有需要从邮箱获取附件的产品使用。

---

## 连接配置

| 配置项 | 示例值 | 说明 |
|--------|--------|------|
| Server | `mail.tcl.com` | Exchange 服务器地址（解析到 `10.74.128.200`） |
| EWS Endpoint | `https://mail.tcl.com/EWS/Exchange.asmx` | EWS 服务端点 |
| Login Username | `yanan1.zhai@tcl.com` | 登录认证用的用户名 |
| Mailbox Address | `zhaiyanan@tianjin-pcb.com` | 主邮箱地址（primary_smtp_address） |
| Password | 存储在环境变量中，不提交代码 | — |
| exchangelib 版本 | `5.6.0` | — |

**重要提示**：自建 Exchange 不支持 IMAP，也**不支持 Microsoft Graph API**（Graph 仅适用于 Exchange Online）。必须使用 EWS（`exchangelib`）。

---

## 环境变量（systemd 配置）

```ini
Environment=EXCHANGE_SERVER=mail.tcl.com
Environment=EXCHANGE_EMAIL=zhaiyanan@tianjin-pcb.com
Environment=EXCHANGE_USERNAME=yanan1.zhai@tcl.com
Environment=EXCHANGE_PASSWORD=实际密码（不提交）
Environment=EXCHANGE_INCOMING_DIR=/mnt/smb/po_pdfs/incoming
```

---

## Python 代码示例

```python
import exchangelib as ewl

creds = ewl.Credentials(
    username=exchange_username or exchange_email,
    password=exchange_password,
)
config = ewl.Configuration(
    server=exchange_server,
    credentials=creds,
)
account = ewl.Account(
    primary_smtp_address=exchange_email,
    config=config,
    autodiscover=False,  # 自建环境必须关闭自动发现
    access_type=ewl.DELEGATE,
)

# 时间窗口过滤（推荐）
since = ewl.EWSDateTime.now(tz=ewl.EWSTimeZone("UTC")) - timedelta(days=days_back)
filter_kwargs = {"datetime_received__gte": since}
if unread_only:
    filter_kwargs["is_read"] = False
items = account.inbox.filter(**filter_kwargs).order_by("-datetime_received")[:max_emails]
```

---

## 查询优化策略

| 过滤方式 | 性能 | 说明 |
|----------|------|------|
| `datetime_received__gte` only | ✅ 快 | 仅按时间窗口过滤，客户端再检查附件和已读状态 |
| `has_attachments=True` + `is_read=False` | ❌ 极慢 | 在大邮箱（1300+ 封邮件）上超时 >120s |

**推荐做法**：服务端只按时间窗口过滤，附件检查和已读标记在客户端处理。

---

## n8n 集成

在 n8n 的 HTTP Request 节点中调用 `/check-email`：

```json
{
  "url": "http://10.142.1.135:8765/check-email",
  "method": "POST",
  "body": {
    "days_back": 1,
    "max_emails": 10
  },
  "options": {
    "timeout": 180000   // 180 秒，毫秒
  }
}
```

**超时设置**：默认 60 秒不够，必须设为 180 秒（180000 毫秒）。

---

## 踩坑记录

### 坑 1：密码中的特殊字符

**问题**：密码包含 `!` 等特殊字符时，通过命令行或 `scp` 直接传递会被 shell 解析。

**解决**：先写临时文件，再用 `scp` 传输，最后 `ssh sudo cp` 部署，避免转义。

### 坑 2：autodiscover 超时

**问题**：自建 Exchange 的自动发现 DNS 查询慢或失败。

**解决**：设置 `autodiscover=False`，手动指定服务器。

### 坑 3：登录用户名与邮箱地址不同

**问题**：认证时用户名是 `yanan1.zhai@tcl.com`，但邮箱地址是 `zhaiyanan@tianjin-pcb.com`。

**解决**：`Credentials` 使用 `username` 参数传入登录用户名，`Account` 的 `primary_smtp_address` 使用邮箱地址。

### 坑 4：慢查询导致超时

**问题**：`has_attachments=True` + `is_read=False` 组合在大邮箱上耗时超过 120 秒。

**解决**：改用 `datetime_received__gte` 仅按时间窗口过滤。

---

## 快速参考

```bash
# 测试 Exchange 连接（在服务器上）
python -c "
import exchangelib as ewl
creds = ewl.Credentials('yanan1.zhai@tcl.com', '密码')
cfg = ewl.Configuration(server='mail.tcl.com', credentials=creds)
acc = ewl.Account('zhaiyanan@tianjin-pcb.com', config=cfg, autodiscover=False)
print('Inbox:', len(acc.inbox.all()[:1]))
"

# 测试 /check-email 端点
curl -X POST http://10.142.1.135:8765/check-email \
  -H "Content-Type: application/json" \
  -d '{"days_back":1,"max_emails":5}'

# 查看 service 日志
ssh n8n "journalctl -u po-parser --no-pager -n 50 | grep -i exchange"
```

---

## 相关文档

- [exchangelib 文档](https://ecederstrand.github.io/exchangelib/)
- 产品内实现：`workflows/po-parser/service/po_parser_service.py` 中的 `/check-email` 端点
