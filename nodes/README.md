# 自定义节点组件库

存放可复用的 n8n 自定义节点代码。

## 目录结构

```
nodes/
├── README.md
├── pdf-reader/          # PDF 读取节点
├── ocr-processor/       # OCR 处理节点
├── sap-rfc-client/      # SAP RFC 客户端节点
└── smb-watcher/         # SMB 文件监控节点
```

## 节点开发规范

### 1. 目录结构

```
{node-name}/
├── {NodeName}.node.ts   # 节点主文件
├── {NodeName}Description.ts  # 节点描述
├── credentials/         # 凭证定义
│   └── {NodeName}Credentials.credentials.ts
├── tests/              # 测试文件
└── README.md
```

### 2. 命名规范

- 节点目录：小写 kebab-case
- 节点类：PascalCase + Node
- 节点类型：`custom.{name}`

### 3. 开发流程

```bash
# 创建节点
npm create @n8n/node my-custom-node

# 本地链接测试
npm link

# 在 n8n 中使用
cd ~/.n8n/nodes
npm link my-custom-node
n8n start
```

## 待开发节点

| 节点名称 | 用途 | 优先级 |
|---------|------|--------|
| smb-watcher | SMB 共享文件夹监控 | P0 |
| pdf-extractor | PDF 文本/表格提取 | P0 |
| ollama-client | Ollama API 调用 | P1 |
| sap-rfc-client | SAP RFC 调用 | P1 |