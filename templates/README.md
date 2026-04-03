# 工作流模板库

存放可复用的工作流模板，作为新产品开发的起点。

## 目录结构

```
templates/
├── README.md
├── scheduled-file-processor/   # 定时文件处理模板
├── webhook-api-integration/    # Webhook API 集成模板
├── database-sync/              # 数据库同步模板
└── ai-agent-workflow/          # AI Agent 工作流模板
```

## 模板规范

### 1. 模板结构

```
{template-name}/
├── template.json       # 工作流 JSON
├── config.json         # 配置说明
├── README.md           # 使用文档
└── preview.png         # 预览图（可选）
```

### 2. 模板内容

- **可参数化**：路径、URL、凭证等使用占位符
- **完整文档**：说明用途、配置方式、依赖项
- **可导入**：直接导入 n8n 即可使用

## 当前模板

| 模板名称 | 用途 | 状态 |
|---------|------|------|
| scheduled-file-processor | 定时扫描文件夹处理文件 | 📝 规划中 |

## 使用方式

1. 复制模板到 `workflows/{product-name}/`
2. 修改配置参数
3. 导入 n8n
4. 根据业务需求调整