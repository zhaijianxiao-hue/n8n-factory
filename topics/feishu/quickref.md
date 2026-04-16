# 飞书多维表格 API 快速参考

## 认证

### 获取 tenant_access_token
```bash
curl -X POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -H "Content-Type: application/json" \
  -d '{"app_id":"YOUR_FEISHU_APP_ID","app_secret":"YOUR_FEISHU_APP_SECRET"}'
```

## 本项目配置

```
App ID:        YOUR_FEISHU_APP_ID
App Secret:    YOUR_FEISHU_APP_SECRET
app_token:     YOUR_BITABLE_APP_TOKEN
table_id:      YOUR_BITABLE_TABLE_ID
n8n workflow:  LQ7ZKNlKz4KCIhv4
```

## 批量写入记录

```bash
curl -X POST \
  'https://open.feishu.cn/open-apis/bitable/v1/apps/YOUR_BITABLE_APP_TOKEN/tables/YOUR_BITABLE_TABLE_ID/records/batch_create' \
  -H 'Authorization: Bearer {tenant_access_token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "records": [
      {
        "fields": {
          "ProcName": "测试",
          "zdate": "2026/04/02"
        }
      }
    ]
  }'
```

## 字段映射

| ERP 字段 | 飞书字段 | 类型 |
|----------|----------|------|
| ProcName | ProcName | 文本 |
| ProcOrd  | ProcOrd  | 文本 |
| ProcNo   | ProcNo   | 文本 |
| EliArea  | EliArea  | 文本 |
| EliPNL   | EliPNL   | 文本 |
| ...      | ...      | 文本 |
| (计算)   | zdate    | 文本 |

## 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 91403   | 权限不足 | 检查应用权限配置 |
| 1254001 | 请求体错误 | 检查 records 格式 |
| 1254004 | table_id 错误 | 检查 table_id |
| 1254040 | app_token 错误 | 检查 app_token |

## Node.js 测试脚本

```javascript
const https = require('https');

// 获取 token
const tokenReq = https.request({
  hostname: 'open.feishu.cn',
  path: '/open-apis/auth/v3/tenant_access_token/internal',
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
}, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const { tenant_access_token } = JSON.parse(data);
    // 使用 token 调用 API
  });
});

tokenReq.write(JSON.stringify({
  app_id: 'YOUR_FEISHU_APP_ID',
  app_secret: 'YOUR_FEISHU_APP_SECRET'
}));
tokenReq.end();
```
