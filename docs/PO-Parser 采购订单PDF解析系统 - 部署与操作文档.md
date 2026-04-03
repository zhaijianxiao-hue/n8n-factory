# PO-Parser 采购订单PDF解析系统 - 部署与操作文档

> 版本: 1.0.0 | 更新日期: 2026-03-24

---

## 第一部分：系统架构

### 1.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PO-Parser 系统架构                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐    │
│  │   业助操作    │         │  n8n服务器    │         │  Ollama服务   │    │
│  │              │         │              │         │              │    │
│  │ 放入PDF到    │────────▶│ 定时扫描     │────────▶│ 字段抽取     │    │
│  │ SMB共享目录  │         │ 调用Python   │         │ qwen3.5:27b  │    │
│  │              │         │ 解析服务      │         │              │    │
│  └──────────────┘         └──────────────┘         └──────────────┘    │
│         │                        │                        │             │
│         │                        ▼                        │             │
│         │               ┌──────────────┐                 │             │
│         │               │ 文件归档      │                 │             │
│         │               │ done/error   │                 │             │
│         │               └──────────────┘                 │             │
│         │                        │                        │             │
│         ▼                        ▼                        ▼             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    SMB 共享目录                                   │  │
│  │  \\10.142.3.78\users\公司共享文件夹\IT部\customer_po_pdfs\        │  │
│  │  ├── incoming/     ← 业助放入PDF                                  │  │
│  │  ├── processing/   ← 处理中                                       │  │
│  │  ├── done/         ← 成功归档                                     │  │
│  │  ├── error/        ← 失败归档                                     │  │
│  │  ├── review/       ← 需人工复核                                   │  │
│  │  └── output/       ← JSON结果输出                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 组件说明

| 组件 | 地址 | 用途 |
|------|------|------|
| n8n | http://10.142.1.135:5678 | 工作流引擎 |
| Ollama | http://10.142.1.112:11434 | LLM服务 |
| SMB共享 | \\10.142.3.78\users\公司共享文件夹\IT部\customer_po_pdfs | 文件存储 |
| Python服务 | http://localhost:8765 (n8n服务器本地) | PDF解析服务 |

### 1.3 工作流程

```
定时触发(1分钟) → 扫描incoming目录 → 有PDF? 
                                    ↓ 是
                              调用Python服务解析PDF
                                    ↓
                              调用Ollama抽取字段
                                    ↓
                              生成标准JSON到output/
                                    ↓
                              移动PDF到done/error/
```

---

## 第二部分：SMB共享目录挂载

### 2.1 场景说明

将 Windows 共享目录 `\\10.142.3.78\users\公司共享文件夹\IT部\customer_po_pdfs` 挂载到 Linux 服务器 `/mnt/smb/po_pdfs` 目录，实现 Linux 对共享文件的读写访问。

### 2.2 前置条件

**Linux 已安装 cifs-utils 工具：**

```bash
sudo apt update && sudo apt install -y cifs-utils
```

**拥有 Windows 域账号：**

| 项目 | 值 |
|------|-----|
| 域 | tpc2 |
| 用户名 | n8n |
| 密码 | tpc2@n8n2026 |

**目标挂载目录已创建：**

```bash
sudo mkdir -p /mnt/smb/po_pdfs
sudo chown 1000:1000 /mnt/smb/po_pdfs
```

### 2.3 手动挂载命令

**完整挂载命令：**

```bash
sudo mount -t cifs "//10.142.3.78/users/公司共享文件夹/IT部/customer_po_pdfs" /mnt/smb/po_pdfs \
  -o username=n8n,domain=tpc2,password="tpc2@n8n2026",uid=1000,gid=1000,vers=3.0,iocharset=utf8,file_mode=0755,dir_mode=0755
```

**参数说明：**

| 参数 | 作用 |
|------|------|
| -t cifs | 指定挂载类型为 SMB/CIFS |
| //10.142.3.78/... | Windows 共享路径（用 / 代替 \） |
| /mnt/smb/po_pdfs | Linux 本地挂载点 |
| username=n8n,domain=tpc2 | 域账号拆分写法 |
| password="tpc2@n8n2026" | 账号密码 |
| uid=1000,gid=1000 | 挂载后文件归属 |
| vers=3.0 | SMB 协议版本 |
| iocharset=utf8 | 支持中文路径 |
| file_mode=0755,dir_mode=0755 | 文件/目录权限 |

**验证挂载：**

```bash
cd /mnt/smb/po_pdfs
ls
# 应看到 done/error/incoming/processing/review 等目录

cd incoming
ls
# 应看到共享目录中的 PDF 文件
```

### 2.4 卸载命令

```bash
# 正常卸载
sudo umount /mnt/smb/po_pdfs

# 强制卸载（若提示 busy）
sudo umount -f /mnt/smb/po_pdfs

# 懒卸载（不等待进程结束）
sudo umount -l /mnt/smb/po_pdfs
```

### 2.5 开机自动挂载

**编辑 /etc/fstab：**

```bash
sudo nano /etc/fstab
```

**在文件末尾添加：**

```
//10.142.3.78/users/公司共享文件夹/IT部/customer_po_pdfs /mnt/smb/po_pdfs cifs username=n8n,domain=tpc2,password=tpc2@n8n2026,uid=1000,gid=1000,vers=3.0,iocharset=utf8,file_mode=0755,dir_mode=0755 0 0
```

**测试自动挂载：**

```bash
sudo mount -a
```

无报错即配置生效，重启后会自动挂载。

### 2.6 一键修复脚本

若挂载异常，可执行以下脚本快速恢复：

```bash
#!/bin/bash
# 一键修复 SMB 挂载脚本
sudo umount -f /mnt/smb/po_pdfs 2>/dev/null
sudo rm -rf /mnt/smb/po_pdfs
sudo mkdir -p /mnt/smb/po_pdfs
sudo chown 1000:1000 /mnt/smb/po_pdfs
sudo mount -t cifs "//10.142.3.78/users/公司共享文件夹/IT部/customer_po_pdfs" /mnt/smb/po_pdfs \
  -o username=n8n,domain=tpc2,password="tpc2@n8n2026",uid=1000,gid=1000,vers=3.0,iocharset=utf8,file_mode=0755,dir_mode=0755
echo "挂载完成，验证文件："
ls /mnt/smb/po_pdfs/incoming
```

---

## 第三部分：Python服务部署

### 3.1 环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Ubuntu/Debian | 20.04+ | 操作系统 |
| Python | 3.10+ | Python服务运行环境 |

### 3.2 创建服务目录

```bash
sudo mkdir -p /opt/po-parser
sudo chown prd-n8n:prd-n8n /opt/po-parser
```

### 3.3 安装Python依赖

```bash
pip3 install fastapi uvicorn pymupdf openai requests
```

### 3.4 上传服务代码

将 `po_parser_service.py` 上传到 `/opt/po-parser/`

代码文件位置：`D:\Workbench\n8n-projects\workflows\po-parser\service\po_parser_service.py`

如果遇到root权限，先复制到下载目录，然后再转移
sudo mv ~/下载/po_parser_service.py /opt/po-parser/

### 3.5 创建systemd服务

```bash
sudo nano /etc/systemd/system/po-parser.service
```

**内容：**

```ini
[Unit]
Description=PO Parser Service - 采购订单PDF解析服务
After=network.target

[Service]
Type=simple
User=prd-n8n
WorkingDirectory=/opt/po-parser
Environment="OLLAMA_URL=http://10.142.1.112:11434/v1"
Environment="OLLAMA_MODEL=qwen3.5:27b"
ExecStart=/usr/bin/python3 /opt/po-parser/po_parser_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3.6 启动服务

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start po-parser

# 设置开机自启
sudo systemctl enable po-parser

# 查看状态
sudo systemctl status po-parser

# 查看日志
sudo journalctl -u po-parser -f
```

### 3.7 验证服务

```bash
# 健康检查
curl http://localhost:8765/health

# 预期返回
{"status": "healthy", "ollama_url": "http://10.142.1.112:11434/v1"}
```

---

## 第四部分：n8n工作流配置

### 4.1 工作流信息

| 项目 | 值 |
|------|-----|
| 名称 | PO-Parser - 采购订单PDF解析 |
| ID | BCPYC0kDhe8s9fVJ |
| 地址 | http://10.142.1.135:5678/workflow/BCPYC0kDhe8s9fVJ |

### 4.2 工作流节点

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 定时触发  │───▶│ 扫描目录  │───▶│ 有文件?  │───▶│ 拆分文件  │
│ (1分钟)  │    │          │    │          │    │          │
└──────────┘    └──────────┘    └────┬─────┘    └────┬─────┘
                                    │ 否              │
                                    ▼                 ▼
                               ┌──────────┐    ┌──────────┐
                               │   结束    │    │ 解析PDF  │
                               └──────────┘    └────┬─────┘
                                                    │
                                               ┌────┴─────┐
                                               │ 成功?    │
                                               └────┬─────┘
                                           ┌───────┴───────┐
                                           ▼               ▼
                                      ┌──────────┐   ┌──────────┐
                                      │ 移到done │   │ 移到error│
                                      └──────────┘   └──────────┘
```

### 4.3 激活工作流

1. 访问 http://10.142.1.135:5678/workflow/BCPYC0kDhe8s9fVJ
2. 点击右上角 **Inactive** 开关，变为 **Active**
3. 工作流将每分钟自动扫描 `incoming/` 目录

### 4.4 手动触发测试

在工作流编辑页面点击 **Execute Workflow** 按钮手动执行。

---

## 第五部分：测试验证

### 5.1 服务连通性测试

```bash
# Python服务
curl http://localhost:8765/health

# Ollama服务
curl http://10.142.1.112:11434/api/tags

# n8n服务
curl http://10.142.1.135:5678/healthz
```

### 5.2 单文件解析测试

```bash
curl -X POST http://localhost:8765/parse \
  -H "Content-Type: application/json" \
  -d '{"pdf_path": "/mnt/smb/po_pdfs/incoming/PO-SSVF (7011)-1106979164.pdf", "output_dir": "/mnt/smb/po_pdfs/output"}'
```

### 5.3 完整流程测试

```bash
# 1. 确认incoming有测试文件
ls /mnt/smb/po_pdfs/incoming/

# 2. 激活n8n工作流（访问UI激活）

# 3. 等待1分钟（工作流自动执行）

# 4. 检查结果
ls -la /mnt/smb/po_pdfs/output/
cat /mnt/smb/po_pdfs/output/*_result.json

# 5. 检查文件归档
ls /mnt/smb/po_pdfs/done/
```

### 5.4 验证清单

- [x] SMB目录正确挂载
- [ ] Python服务运行正常 (`systemctl status po-parser`)
- [ ] Ollama可访问 (`curl http://10.142.1.112:11434/api/tags`)
- [ ] n8n工作流已激活
- [ ] 测试PDF解析成功
- [ ] JSON结果正确生成
- [ ] 文件正确归档到 `done/` 或 `error/`

---

## 第六部分：日常运维

### 6.1 服务管理

```bash
# 查看服务状态
sudo systemctl status po-parser

# 重启服务
sudo systemctl restart po-parser

# 查看日志
sudo journalctl -u po-parser -f --since "1 hour ago"

# 查看n8n日志
sudo journalctl -u n8n -f
```

### 6.2 监控指标

| 指标 | 检查方式 | 正常值 |
|------|---------|--------|
| Python服务状态 | `systemctl is-active po-parser` | active |
| SMB挂载状态 | `mount \| grep po_pdfs` | 已挂载 |
| 磁盘空间 | `df -h /mnt/smb/po_pdfs` | > 10% 可用 |
| incoming文件数 | `ls /mnt/smb/po_pdfs/incoming/ \| wc -l` | < 100 |

### 6.3 定期清理

```bash
# 清理30天前的done文件
find /mnt/smb/po_pdfs/done -name "*.pdf" -mtime +30 -delete

# 清理30天前的output文件
find /mnt/smb/po_pdfs/output -name "*.json" -mtime +30 -delete
```

---

## 第七部分：故障排查

### 7.1 SMB挂载问题

**报错：cannot mount ... read-only**

- 原因：域账号格式错误/认证失败
- 解决：
  ```bash
  sudo umount -f /mnt/smb/po_pdfs
  sudo rm -rf /mnt/smb/po_pdfs && sudo mkdir -p /mnt/smb/po_pdfs
  # 使用正确格式重新挂载
  ```

**中文路径/文件名乱码**

- 解决：挂载命令添加 `iocharset=utf8` 参数

**普通用户无读写权限**

- 解决：挂载命令添加 `uid=1000,gid=1000` 参数

### 7.2 Python服务问题

**服务无法启动**

```bash
# 检查Python版本
python3 --version

# 检查依赖
pip3 list | grep -E "fastapi|uvicorn|pymupdf|openai"

# 手动启动测试
cd /opt/po-parser && python3 po_parser_service.py
```

### 7.3 Ollama问题

```bash
# 检查Ollama服务
curl http://10.142.1.112:11434/api/tags

# 检查模型
curl http://10.142.1.112:11434/api/ps
```

### 7.4 n8n工作流问题

1. 检查工作流是否激活
2. 检查n8n执行日志
3. 检查节点配置中的URL是否正确
4. 检查Python服务是否运行

### 7.5 紧急处理

```bash
# 重启所有服务
sudo systemctl restart po-parser
sudo systemctl restart n8n

# 手动移动卡住的文件
mv /mnt/smb/po_pdfs/processing/* /mnt/smb/po_pdfs/error/
```

---

## 附录A：API接口说明

### 健康检查

```
GET /health
Response: {"status": "healthy", "ollama_url": "..."}
```

### 扫描目录

```
POST /scan
Body: {"directory": "/path/to/dir", "pattern": "*.pdf"}
Response: {"count": 1, "files": ["/path/to/file.pdf"]}
```

### 解析PDF

```
POST /parse
Body: {"pdf_path": "/path/to/file.pdf", "output_dir": "/path/to/output"}
Response: {
  "source_file": "file.pdf",
  "file_hash": "md5...",
  "header": {...},
  "items": [...],
  "confidence": 0.86,
  "status": "success"
}
```

### 移动文件

```
POST /move
Body: {"source": "/path/source", "destination": "/path/dest"}
Response: {"status": "moved"}
```

---

## 附录B：输出JSON格式

```json
{
  "source_file": "PO-SSVF (7011)-1106979164.pdf",
  "file_hash": "d10b1a783c4e5a95e76d9ca71a32dd90",
  "process_time": "2026-03-24T12:07:50.089014",
  "header": {
    "customer_name": "Schneider Electric Asia Pte Ltd",
    "po_number": "1106979164",
    "po_date": "2025-12-23",
    "currency": "CNY",
    "total_amount": 19671.9
  },
  "items": [
    {
      "line_no": "00010",
      "material": "363112114",
      "description": "4L-TG130-LFHAL-15up by board",
      "qty": 3450,
      "unit_price": 5.702,
      "amount": 19671.9
    }
  ],
  "confidence": 0.5,
  "warnings": [
    "PO number appears in multiple locations"
  ],
  "status": "success"
}
```

---

*文档维护: n8n-projects/workflows/po-parser/*
