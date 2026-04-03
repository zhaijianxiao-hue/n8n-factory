# 构建与部署脚本

存放自动化脚本。

## 目录结构

```
scripts/
├── README.md
├── deploy.js          # 部署工作流到 n8n
├── validate.js        # 验证工作流 JSON
├── test-sample.js     # 测试样本处理
└── backup.sh          # 备份脚本
```

## 可用脚本

### deploy.js - 部署工作流

```bash
# 部署指定产品
node scripts/deploy.js --product po-parser

# 部署所有产品
node scripts/deploy.js --all
```

### validate.js - 验证工作流

```bash
# 验证 JSON 格式
node scripts/validate.js workflows/po-parser/workflow.json
```

### test-sample.js - 测试样本

```bash
# 处理测试样本
node scripts/test-sample.js --product po-parser --file sample.pdf
```

## 待开发脚本

| 脚本 | 功能 | 优先级 |
|------|------|--------|
| deploy.js | 部署到 n8n | P0 |
| validate.js | 工作流验证 | P1 |
| test-sample.js | 样本测试 | P1 |