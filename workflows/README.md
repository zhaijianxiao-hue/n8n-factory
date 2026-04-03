# 工作流产品目录

每个子目录代表一个独立的工作流产品。

## 产品结构规范

```
workflows/{product-name}/
├── config/                 # 产品配置
│   ├── product.json        # 产品元数据
│   ├── env.example         # 环境变量示例
│   └── credentials.json    # 凭证配置（不提交）
│
├── schemas/                # JSON Schema 定义
│   ├── input.schema.json   # 输入数据结构
│   └── output.schema.json  # 输出数据结构
│
├── nodes/                  # 产品专用节点代码
│   └── README.md
│
├── tests/                  # 测试数据与用例
│   ├── samples/            # 样本 PDF/文件
│   └── expected/           # 预期输出
│
├── workflow.json           # n8n 工作流 JSON
└── README.md               # 产品文档
```

## 当前产品

| 目录 | 状态 | 描述 |
|------|------|------|
| po-parser | 🚧 | 采购订单 PDF 自动解析 |

## 开发流程

1. 创建新产品目录
2. 定义 input/output Schema
3. 开发工作流 JSON
4. 准备测试样本
5. 验证与部署