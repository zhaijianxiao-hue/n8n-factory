# PDF 解析技术选型

本项目采用 **OpenDataLoader PDF** 作为 PDF 解析引擎。

## 为什么选择 OpenDataLoader PDF

| 对比项 | OpenDataLoader | pdfplumber | PyMuPDF |
|--------|----------------|------------|---------|
| 表格准确率 | **93%** | ~70% | ~40% |
| 总体准确率 | **90%** | ~75% | ~57% |
| 边界框输出 | ✅ 原生支持 | ❌ | 部分 |
| 中文 OCR | ✅ Hybrid 模式 | ❌ | ❌ |
| 本地部署 | ✅ 无需云端 | ✅ | ✅ |
| GPU 依赖 | ❌ 不需要 | ❌ | ❌ |

## 安装

### 前置要求

1. **Java 11+**
   ```bash
   # Windows: 从 https://adoptium.net/ 下载安装
   # Linux:
   sudo apt install openjdk-17-jdk
   
   # 验证
   java -version
   ```

2. **Python 3.10+**
   ```bash
   python --version
   ```

### 安装库

```bash
# 基础版（文字型 PDF）
pip install opendataloader-pdf

# Hybrid 版（扫描件、复杂表格、OCR）
pip install "opendataloader-pdf[hybrid]"
```

## 使用方式

### 基础模式（文字型 PDF）

```python
import opendataloader_pdf

result = opendataloader_pdf.convert(
    input_path=["采购订单.pdf"],
    output_dir="output/",
    format="json,markdown"
)
```

### Hybrid 模式（扫描件、复杂表格）

```bash
# 终端 1：启动后端服务
opendataloader-pdf-hybrid --port 5002 --force-ocr --ocr-lang "ch_sim,en"
```

```python
# 终端 2：处理 PDF
import opendataloader_pdf

result = opendataloader_pdf.convert(
    input_path=["采购订单.pdf"],
    output_dir="output/",
    format="json",
    hybrid="docling-fast"
)
```

## 输出格式

### JSON 输出结构

```json
{
  "type": "table",
  "id": 5,
  "page number": 1,
  "bounding box": [72.0, 400.0, 540.0, 650.0],
  "content": [
    ["物料编码", "数量", "单价", "金额"],
    ["ABC-001", "100", "12.5", "1250"],
    ["ABC-002", "50", "8.0", "400"]
  ]
}
```

### Markdown 输出

```markdown
# 采购订单

**客户**: ABC Corp
**PO 号**: PO-2025-001

| 物料编码 | 数量 | 单价 | 金额 |
|---------|------|------|------|
| ABC-001 | 100 | 12.5 | 1250 |
```

## 与 Ollama 集成

OpenDataLoader 负责 PDF → 结构化文本，Ollama 负责 字段抽取：

```python
import opendataloader_pdf
import requests

# 1. 解析 PDF
opendataloader_pdf.convert(
    input_path=["po.pdf"],
    output_dir="output/",
    format="markdown"
)

# 2. 读取 Markdown
with open("output/po.md", "r") as f:
    pdf_text = f.read()

# 3. 调用 Ollama 抽取字段
response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:7b",
        "prompt": f"""
        从以下采购订单文本中提取关键字段，输出 JSON 格式：
        - customer_name: 客户名称
        - po_number: PO 号
        - po_date: 订单日期
        - items: 物料明细列表
        
        采购订单内容：
        {pdf_text}
        """
    }
)

po_json = response.json()
```

## 参考资料

- [GitHub 仓库](https://github.com/opendataloader-project/opendataloader-pdf)
- [Python 快速开始](https://opendataloader.org/docs/quick-start-python)
- [JSON Schema](https://opendataloader.org/docs/json-schema)
- [Hybrid 模式指南](https://opendataloader.org/docs/hybrid-mode)