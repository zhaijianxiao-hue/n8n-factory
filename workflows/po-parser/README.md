# po-parser: 采购订单 PDF 自动解析工作流

> 市场部业助收到客户采购订单 PDF，自动解析并写入 SAP 中间表

## 业务背景

- **现状**：业助需要人工查看每个客户的 PDF（格式各异），手动录入 SAP
- **目标**：自动解析 PDF → 统一 JSON → 调 SAP RFC → 业助复核

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| PDF 解析 | OpenDataLoader PDF | #1 基准测试，表格准确率 93% |
| 字段抽取 | Ollama + qwen2.5:7b | 本地 LLM，中文支持好 |
| SAP 集成 | RFC / 中间服务 | 待确认 |

## 工作流架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  定时扫描    │───▶│  PDF 解析   │───▶│  字段校验   │───▶│  SAP RFC    │
│  (1分钟)    │    │  (规则/LLM) │    │  (规则)     │    │  (中间表)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
│  文件归档    │
│ done/review/error │
                                       └─────────────┘
```

## 文件夹结构

```
po-parser/
├── config/
│   ├── product.json          # 产品配置
│   └── env.example           # 环境变量
├── schemas/
│   ├── po-input.schema.json  # PDF 解析输入
│   └── po-output.schema.json # 标准 PO JSON
├── tests/
│   └── samples/              # 测试 PDF 样本
├── workflow.json             # n8n 工作流定义
└── README.md
```

## 当前扩展策略

- 主流程保持一个共享 n8n workflow，不为每个客户复制一套分支。
- 客户差异下沉到 Python parser service，通过 customer profile 识别和规则解析处理。
- `EVYTRA` 是第一个显式 customer profile，采用“规则优先，LLM 补充”的方式解析。
- 对可疑金额、合计不一致、字段缺失等情况，结果状态返回 `review`，由 workflow 路由到复核目录。

## 配置项

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `PO_INBOX_PATH` | 输入文件夹路径 | `/mnt/smb/po-inbox/incoming` |
| `PO_DONE_PATH` | 成功归档路径 | `/mnt/smb/po-inbox/done` |
| `PO_ERROR_PATH` | 失败归档路径 | `/mnt/smb/po-inbox/error` |
| `OLLAMA_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` | 使用的模型 | `qwen2.5:7b` |
| `SAP_API_URL` | SAP 中间服务地址 | `http://sap-gateway:8080/api` |

## 输出 JSON Schema

```json
{
  "source_file": "客户A_PO_20250101.pdf",
  "file_hash": "abc123...",
  "header": {
    "customer_name": "ABC Corp",
    "po_number": "PO-2025-001",
    "po_date": "2025-01-01",
    "currency": "USD"
  },
  "items": [
    {
      "line_no": 10,
      "customer_material": "ABC-001",
      "qty": 100,
      "unit_price": 12.5
    }
  ],
  "confidence": 0.86,
  "warnings": []
}
```

## 部署步骤

1. 配置 SMB 挂载
2. 设置环境变量
3. 导入工作流到 n8n
4. 配置凭证
5. 激活工作流

## 监控与告警

- 成功/失败计数
- 置信度分布
- 异常文件告警

## 待办事项

- [ ] 收集 PDF 样本 (10-30 份)
- [ ] 确认 SAP RFC 接口
- [ ] 测试 Ollama 解析效果
- [ ] 完成工作流 JSON
