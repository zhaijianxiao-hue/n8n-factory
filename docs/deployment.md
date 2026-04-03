# 部署指南

## 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         生产环境                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   SMB 共享   │     │    n8n     │     │   Ollama   │       │
│  │  文件服务器  │◀───▶│  工作流引擎  │◀───▶│   LLM 服务  │       │
│  │             │     │             │     │             │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                            │                                    │
│                            ▼                                    │
│                     ┌─────────────┐                           │
│                     │  SAP 网关   │                           │
│                     │  中间服务    │                           │
│                     └─────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 部署步骤

### 1. 环境准备

#### n8n 服务器

```bash
# 安装依赖
npm install -g n8n

# 或使用 Docker
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

#### SMB 挂载 (Linux)

```bash
# 安装 cifs-utils
sudo apt-get install cifs-utils

# 创建挂载点
sudo mkdir -p /mnt/smb/po-inbox

# 挂载
sudo mount -t cifs //fileserver/po-inbox /mnt/smb/po-inbox \
  -o username=user,password=pass,uid=1000,gid=1000
```

#### Ollama 服务

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动服务
ollama serve

# 拉取模型
ollama pull qwen2.5:7b
```

### 2. 配置

#### 环境变量

```bash
# ~/.bashrc 或 /etc/environment
export PO_INBOX_PATH=/mnt/smb/po-inbox/incoming
export PO_DONE_PATH=/mnt/smb/po-inbox/done
export PO_ERROR_PATH=/mnt/smb/po-inbox/error
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=qwen2.5:7b
export SAP_API_URL=http://sap-gateway:8080/api
```

#### n8n 配置

```bash
# ~/.n8n/config
N8N_HOST=0.0.0.0
N8N_PORT=5678
WEBHOOK_URL=https://n8n.company.com
N8N_ENCRYPTION_KEY=your-encryption-key
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=localhost
DB_POSTGRESDB_DATABASE=n8n
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=password
```

### 3. 导入工作流

#### 方式一：UI 导入

1. 打开 n8n UI (http://localhost:5678)
2. 点击 "+" → "Import from File"
3. 选择 `workflows/po-parser/workflow.json`

#### 方式二：API 导入

```bash
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: your-api-key" \
  -d @workflows/po-parser/workflow.json
```

### 4. 配置凭证

在 n8n UI 中配置：

1. Settings → Credentials
2. 添加所需凭证：
   - SAP API Key
   - SMB 访问凭证（如需要）
   - Ollama（如需认证）

### 5. 激活工作流

```bash
# 通过 API 激活
curl -X PATCH http://localhost:5678/api/v1/workflows/{id}/activate \
  -H "X-N8N-API-KEY: your-api-key"
```

## 监控

### n8n 内置监控

- Execution History：查看执行历史
- Settings → Executions：配置日志保留

### 外部监控

推荐集成：
- Prometheus + Grafana
- 或公司现有监控系统

### 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| 执行成功率 | 成功/总数 | < 90% |
| 平均执行时间 | 毫秒 | > 30000ms |
| 队列积压 | 待处理数 | > 100 |
| 错误率 | 错误/总数 | > 10% |

## 故障排查

### 常见问题

#### 1. SMB 挂载失败

```bash
# 检查挂载
mount | grep cifs

# 重新挂载
sudo umount /mnt/smb/po-inbox
sudo mount -a
```

#### 2. Ollama 连接失败

```bash
# 检查服务状态
systemctl status ollama

# 检查端口
netstat -tlnp | grep 11434

# 测试连接
curl http://localhost:11434/api/tags
```

#### 3. n8n 执行失败

```bash
# 查看日志
docker logs n8n -f

# 或
journalctl -u n8n -f
```

## 备份与恢复

### 备份

```bash
# 备份 n8n 数据
tar -czvf n8n-backup-$(date +%Y%m%d).tar.gz ~/.n8n

# 备份工作流 JSON
cp -r workflows/ workflows-backup-$(date +%Y%m%d)/
```

### 恢复

```bash
# 恢复 n8n 数据
tar -xzvf n8n-backup-20260324.tar.gz -C ~/
```

## 升级

### n8n 升级

```bash
# Docker
docker pull n8nio/n8n:latest
docker stop n8n
docker rm n8n
# 重新启动

# npm
npm update -g n8n
```

### 工作流升级

1. 导出当前工作流
2. 备份
3. 导入新版本
4. 验证测试
5. 切换激活