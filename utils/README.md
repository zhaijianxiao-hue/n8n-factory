# 公共工具函数

存放可复用的工具函数和辅助模块。

## 目录结构

```
utils/
├── README.md
├── parsers/           # 解析器
│   ├── pdf.js         # PDF 解析
│   └── ocr.js         # OCR 处理
├── validators/        # 校验器
│   └── po-schema.js   # PO Schema 校验
├── transformers/      # 数据转换
│   └── sap-mapper.js  # SAP 字段映射
└── helpers/           # 辅助函数
    ├── file.js        # 文件操作
    └── logger.js      # 日志工具
```

## 使用方式

这些工具主要用于：
1. n8n Code 节点引用
2. 自定义节点开发
3. 独立脚本处理

## 待开发工具

| 工具名称 | 用途 | 优先级 |
|---------|------|--------|
| pdf-extractor | PDF 文本/表格提取 | P0 |
| ollama-client | Ollama API 封装 | P0 |
| schema-validator | JSON Schema 校验 | P1 |
| sap-field-mapper | SAP 字段映射 | P1 |