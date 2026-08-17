# n8n 服务器运维知识

> 跨产品的 n8n 服务器部署、升级、备份和恢复知识。
> 产品级 workflow 规则仍放在各 `workflows/*/KNOWLEDGE.md` 中，踩坑简表放在根 `LEARNINGS.md`。

---

## 当前生产实例

| 项目 | 值 |
|------|----|
| SSH alias | `n8n` |
| 主机名 | `prdn8n-virtual-machine` |
| n8n URL | `http://10.142.1.135:5678` |
| Compose 目录 | `/home/prd-n8n/n8n` |
| Compose 文件 | `/home/prd-n8n/n8n/docker-compose.yml` |
| 容器名 | `n8n-n8n-1` |
| Compose service | `n8n` |
| 当前镜像引用 | `n8nio/n8n:latest` |
| 对外端口 | `5678:5678` |
| 数据目录 | `/home/prd-n8n/n8n/n8n_data` |
| 容器内挂载点 | `/home/node/.n8n` |

`n8n_data` 是核心持久化目录，里面包含 SQLite 数据库、加密配置和事件日志。升级镜像不会自动删除 workflow、credential、用户和执行数据；这些数据是否保留，取决于这个目录是否仍然正确挂载。

---

## 2026-06-09 升级记录

| 项目 | 值 |
|------|----|
| 升级前版本 | `2.12.2` |
| 升级后版本 | `2.23.4` |
| 目标版本来源 | npm `latest/stable`，n8n release notes |
| 代理 | `http://10.142.192.59:10808` |
| 备份目录 | `/home/prd-n8n/n8n/backups/pre-n8n-upgrade-20260609-093245` |
| 数据备份 | `n8n_data.tgz`，约 `146M` |
| 备份校验 | `sha256sum -c n8n_data.tgz.sha256` 通过 |
| 旧镜像回滚 tag | `n8nio/n8n:preupgrade-20260609-093245` |
| 升级后 workflow 数量 | `40` |
| 升级后 active workflow 数量 | `10` |
| 健康检查 | `http://10.142.1.135:5678/healthz` 返回 `{"status":"ok"}` |

升级后日志显示数据库迁移完成，active workflows 已重新激活。日志中出现过两个非阻断提醒：

- Python task runner internal mode 缺 Python 3。当前 JS task runner 已注册，现有 workflow 未因此失败。
- 事件日志解析超过默认内存消息数，可能跳过部分未完成 execution recovery；可通过 `N8N_EVENTBUS_LOGWRITER_MAXMESSAGESPERPARSE` 调整。

---

## 升级前检查

```bash
ssh n8n "hostname"
ssh n8n "cd /home/prd-n8n/n8n && docker compose ps"
ssh n8n "docker exec n8n-n8n-1 n8n --version"
ssh n8n "docker inspect n8n-n8n-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'"
ssh n8n "curl -sS http://localhost:5678/healthz"
```

本地用项目 n8n skill 或 API 工具记录升级前 workflow 基线，至少保存：

- workflow 总数
- active workflow 数量
- active workflow 名称

如果只是为了清点，不要输出完整 workflow JSON，历史 workflow 里可能有硬写的第三方密钥字段。

---

## Docker daemon 代理

受限网络里，`curl -x http://10.142.192.59:10808 ...` 成功，不等于 `docker pull` 会成功。`docker pull` 的出网请求由 Docker daemon 发起，需要把代理配置到 `docker.service`。

```bash
ssh n8n "sudo mkdir -p /etc/systemd/system/docker.service.d"

ssh n8n "sudo tee /etc/systemd/system/docker.service.d/http-proxy.conf >/dev/null <<'EOF'
[Service]
Environment=\"HTTP_PROXY=http://10.142.192.59:10808\"
Environment=\"HTTPS_PROXY=http://10.142.192.59:10808\"
Environment=\"NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,10.142.0.0/16,172.16.0.0/12,192.168.0.0/16\"
EOF"

ssh n8n "sudo systemctl daemon-reload && sudo systemctl restart docker"
ssh n8n "systemctl show docker --property=Environment --no-pager"
```

当前服务器 `LiveRestore=false`，重启 Docker daemon 会让 n8n 短暂闪断。重启后立刻确认容器已恢复：

```bash
ssh n8n "docker ps --filter name=n8n-n8n-1 --format '{{.Names}} {{.Status}} {{.Image}}'"
```

---

## 标准升级流程

不要盲拉 beta/next。先确认 stable 版本，再拉明确版本镜像。

```powershell
npm view n8n dist-tags version --json
```

服务器拉取目标镜像：

```bash
ssh n8n "docker pull n8nio/n8n:2.23.4"
```

执行升级：

```bash
ssh n8n "set -euo pipefail
cd /home/prd-n8n/n8n
TS=\$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=/home/prd-n8n/n8n/backups/pre-n8n-upgrade-\$TS
mkdir -p \"\$BACKUP_DIR\"

OLD_VERSION=\$(docker exec n8n-n8n-1 n8n --version)
docker tag n8nio/n8n:latest n8nio/n8n:preupgrade-\$TS
cp docker-compose.yml \"\$BACKUP_DIR/docker-compose.yml\"

docker compose stop n8n
tar -C /home/prd-n8n/n8n -czf \"\$BACKUP_DIR/n8n_data.tgz\" n8n_data
sha256sum \"\$BACKUP_DIR/n8n_data.tgz\" > \"\$BACKUP_DIR/n8n_data.tgz.sha256\"

docker tag n8nio/n8n:2.23.4 n8nio/n8n:latest
docker compose up -d --no-deps n8n

docker exec n8n-n8n-1 n8n --version
curl -sS http://localhost:5678/healthz
echo \"old_version=\$OLD_VERSION backup_dir=\$BACKUP_DIR\"
"
```

说明：

- 当前 compose 文件使用 `n8nio/n8n:latest`，所以先拉明确版本，再把该版本 tag 成 `latest`，避免 compose 启动到不可控版本。
- 停服务后再备份 `n8n_data`，可以避免 SQLite WAL 仍在写入导致备份不一致。
- 旧镜像 tag 和数据备份必须成对保留；只保留旧镜像不够，因为新版本启动后会迁移数据库。

---

## 升级后验证

```bash
ssh n8n "docker exec n8n-n8n-1 n8n --version"
ssh n8n "curl -sS http://localhost:5678/healthz"
ssh n8n "docker logs --tail 160 n8n-n8n-1"
```

从本机验证外部访问：

```powershell
Invoke-WebRequest -Uri "http://10.142.1.135:5678/healthz" -UseBasicParsing -TimeoutSec 10
```

使用 n8n API 工具再次清点 workflow：

- 总数应与升级前一致
- active 数量应与升级前一致
- active workflow 名称应与升级前一致

2026-06-09 升级后 active workflow 为：

- `test002`
- `PO-Parser - 采购订单PDF解析`
- `Metal Price Sync - 每日金属价格同步`
- `老 ERP 数据同步飞书多维表格_各工站生产数报表`
- `厚铜样品订单MI上线数据- 同步飞书多维表格`
- `工站成本-飞书群推送`
- `经营日报-飞书群推送`
- `PO-Parser - 采购订单PDF解析 - 生产`
- `8D报告流程`
- `每日负毛利-飞书群推送`

---

## 回滚流程

如果新版本启动失败，优先用升级前备份恢复数据目录，再把旧镜像 tag 回 `latest`。因为新版本可能已执行数据库迁移，不能只换回旧镜像而继续使用迁移后的数据库。

```bash
ssh n8n "set -euo pipefail
cd /home/prd-n8n/n8n
BACKUP_DIR=/home/prd-n8n/n8n/backups/pre-n8n-upgrade-20260609-093245
ROLLBACK_TAG=n8nio/n8n:preupgrade-20260609-093245
TS=\$(date +%Y%m%d-%H%M%S)

docker compose stop n8n
mv n8n_data n8n_data.failed-\$TS
tar -C /home/prd-n8n/n8n -xzf \"\$BACKUP_DIR/n8n_data.tgz\"
docker tag \"\$ROLLBACK_TAG\" n8nio/n8n:latest
docker compose up -d --no-deps n8n

docker exec n8n-n8n-1 n8n --version
curl -sS http://localhost:5678/healthz
"
```

回滚成功后，再用 n8n API 工具核对 workflow 总数和 active 数量。

---

## 常见坑

### Docker pull 不走当前 shell 代理

`curl -x` 能访问 Docker Hub，只证明当前 shell 可通过代理访问；`docker pull` 仍可能直连失败。必须配置 Docker daemon 的 systemd proxy drop-in。

### 数据不在容器里

workflow、credential 和用户数据在 `/home/node/.n8n`，当前通过 bind mount 落在 `/home/prd-n8n/n8n/n8n_data`。升级或重建容器前先确认挂载，避免启动成一个全新的空实例。

### 回滚必须恢复数据

n8n 启动新版本后会自动执行数据库迁移。要回滚到旧版本，通常必须同时恢复升级前 `n8n_data`，否则旧版本可能无法识别新结构。

### 不要输出完整 workflow JSON

生产 workflow 里可能存在历史硬编码 token、secret 或业务接口信息。清点时输出名称、ID、active 状态即可。

---

## 相关文件

- 根知识库索引：`KNOWLEDGE.md`
- 踩坑汇总：`LEARNINGS.md`
- 当前 n8n compose：`/home/prd-n8n/n8n/docker-compose.yml`
- 当前 n8n 数据目录：`/home/prd-n8n/n8n/n8n_data`
- 2026-06-09 备份：`/home/prd-n8n/n8n/backups/pre-n8n-upgrade-20260609-093245`
