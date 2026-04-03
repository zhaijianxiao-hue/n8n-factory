# 开发指南

## 环境准备

### 1. 基础环境

```bash
# Node.js >= 18
node --version

# n8n 全局安装
npm install -g n8n

# 启动 n8n
n8n start
```

### 2. 项目依赖

```bash
cd n8n-projects
npm install
```

### 3. 开发工具

推荐 VS Code 扩展：
- n8n Workflow Designer
- JSON Schema Validator
- ESLint

## 开发流程

### 创建新产品

```bash
# 1. 创建产品目录
mkdir -p workflows/{product-name}/{config,schemas,tests}

# 2. 复制模板文件
cp workflows/po-parser/config/product.json workflows/{product-name}/config/

# 3. 定义 Schema
# 编辑 schemas/input.schema.json 和 output.schema.json

# 4. 开发工作流
# 在 n8n UI 中设计，导出为 workflow.json
```

### 开发自定义节点

```bash
# 1. 初始化节点
npm create @n8n/node nodes/{node-name}

# 2. 开发
# 编辑 {NodeName}.node.ts

# 3. 本地测试
cd nodes/{node-name}
npm link

# 4. 在 n8n 中链接
cd ~/.n8n/nodes
npm link n8n-nodes-{node-name}

# 5. 重启 n8n
n8n start
```

### 使用 Code 节点

Code 节点用于复杂逻辑，建议：
- 代码量 < 100 行：直接在节点中编写
- 代码量 > 100 行：考虑开发自定义节点

**JavaScript 示例**：

```javascript
// PDF 解析逻辑
const items = $input.all();

const results = items.map(item => {
  const pdfText = item.json.text;
  // 解析逻辑...
  return {
    json: {
      po_number: extractPONumber(pdfText),
      customer: extractCustomer(pdfText),
      items: extractItems(pdfText)
    }
  };
});

return results;
```

## 调试技巧

### 1. 节点输出检查

在 n8n UI 中点击节点，查看输出数据。

### 2. 临时日志

```javascript
// 在 Code 节点中
console.log('Debug:', JSON.stringify($json, null, 2));
```

### 3. 测试模式

使用 Manual Trigger 手动触发测试。

### 4. 错误处理

```javascript
try {
  // 业务逻辑
} catch (error) {
  return {
    json: {
      error: error.message,
      input: $json
    }
  };
}
```

## 测试

### 单元测试

```bash
npm test
```

### 集成测试

1. 准备测试样本文件
2. 手动触发工作流
3. 验证输出符合 Schema

### 回归测试

使用历史样本数据验证修改后的工作流。

## 版本管理

### 工作流版本

- 每次重大修改更新 `product.json` 中的 version
- 保留历史版本在 `workflow.v{version}.json`

### Git 提交规范

```
feat(po-parser): 添加客户 X 模板支持
fix(po-parser): 修复日期解析错误
docs: 更新开发指南
chore: 更新依赖
```

## 最佳实践

1. **模块化**：复杂逻辑拆分为多个节点
2. **错误处理**：每个可能失败的节点添加错误分支
3. **日志记录**：关键步骤记录日志
4. **幂等性**：同一输入多次执行结果一致
5. **可观测性**：添加监控和告警