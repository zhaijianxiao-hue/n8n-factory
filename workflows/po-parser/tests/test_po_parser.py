"""
PO Parser 测试脚本
使用 OpenDataLoader PDF 解析 + Ollama 字段抽取
"""

import os
import sys
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path

try:
    import opendataloader_pdf
except ImportError:
    print("错误: 请先安装 opendataloader-pdf")
    print("  pip install opendataloader-pdf")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("错误: 请先安装 openai")
    print("  pip install openai")
    sys.exit(1)


class POParserTest:
    def __init__(self, ollama_url: str, ollama_model: str):
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.client = OpenAI(base_url=ollama_url, api_key="ollama")

    def parse_pdf(self, pdf_path: str, output_dir: str = None) -> dict:
        """
        使用 OpenDataLoader PDF 解析 PDF
        """
        print(f"\n{'=' * 60}")
        print(f"Step 1: 解析 PDF - {pdf_path}")
        print(f"{'=' * 60}")

        if output_dir is None:
            output_dir = str(Path(pdf_path).parent / "output")

        os.makedirs(output_dir, exist_ok=True)

        try:
            opendataloader_pdf.convert(
                input_path=[pdf_path], output_dir=output_dir, format="json,markdown"
            )
            print(f"✓ PDF 解析完成，输出目录: {output_dir}")

            pdf_name = Path(pdf_path).stem

            json_path = os.path.join(output_dir, f"{pdf_name}.json")
            md_path = os.path.join(output_dir, f"{pdf_name}.md")

            result = {
                "json_path": json_path if os.path.exists(json_path) else None,
                "md_path": md_path if os.path.exists(md_path) else None,
                "output_dir": output_dir,
            }

            if result["md_path"]:
                with open(result["md_path"], "r", encoding="utf-8") as f:
                    result["markdown_content"] = f.read()

            return result

        except Exception as e:
            print(f"✗ PDF 解析失败: {e}")
            raise

    def extract_fields_with_ollama(self, markdown_content: str) -> dict:
        """
        使用 Ollama 从 Markdown 内容中抽取字段
        """
        print(f"\n{'=' * 60}")
        print(f"Step 2: Ollama 字段抽取 - {self.ollama_model}")
        print(f"{'=' * 60}")

        prompt = f"""你是一个采购订单解析助手。请从以下采购订单文本中提取关键字段，输出 JSON 格式。

要求：
1. 必须提取的字段：
   - customer_name: 客户名称
   - po_number: 采购订单号
   - po_date: 订单日期 (格式: YYYY-MM-DD)
   - currency: 币种
   - items: 物料明细列表，每项包含：
     - line_no: 行号
     - material: 物料编码/描述
     - qty: 数量
     - unit_price: 单价
     - amount: 金额

2. 如果某个字段无法确定，设为 null
3. 输出纯 JSON，不要有其他说明文字
4. 给出整体置信度评分 confidence (0-1)

采购订单内容：
{markdown_content[:8000]}

请输出 JSON："""

        try:
            response = self.client.chat.completions.create(
                model=self.ollama_model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的采购订单数据提取助手，只输出 JSON 格式数据。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            json_match = content
            if "```json" in content:
                json_match = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_match = content.split("```")[1].split("```")[0]

            result = json.loads(json_match.strip())
            print(f"✓ 字段抽取完成")
            return result

        except json.JSONDecodeError as e:
            print(f"✗ JSON 解析失败: {e}")
            print(f"原始响应: {content}")
            return {"error": str(e), "raw_response": content}
        except Exception as e:
            print(f"✗ Ollama 调用失败: {e}")
            raise

    def calculate_file_hash(self, file_path: str) -> str:
        """计算文件 MD5 哈希"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def process_po(self, pdf_path: str) -> dict:
        """
        完整的采购订单处理流程
        """
        print(f"\n{'#' * 60}")
        print(f"# 采购订单解析测试")
        print(f"# 文件: {pdf_path}")
        print(f"{'#' * 60}")

        start_time = datetime.now()

        result = {
            "source_file": os.path.basename(pdf_path),
            "file_hash": self.calculate_file_hash(pdf_path),
            "process_time": start_time.isoformat(),
            "status": "processing",
        }

        try:
            parse_result = self.parse_pdf(pdf_path)

            if parse_result.get("markdown_content"):
                fields = self.extract_fields_with_ollama(
                    parse_result["markdown_content"]
                )

                result["header"] = {
                    "customer_name": fields.get("customer_name"),
                    "customer_code": fields.get("customer_code"),
                    "po_number": fields.get("po_number"),
                    "po_date": fields.get("po_date"),
                    "currency": fields.get("currency"),
                    "total_amount": fields.get("total_amount"),
                }

                result["items"] = fields.get("items", [])
                result["confidence"] = fields.get("confidence", 0.5)
                result["warnings"] = []

                if not result["header"].get("po_number"):
                    result["warnings"].append("PO 号未能识别")
                if not result["header"].get("customer_name"):
                    result["warnings"].append("客户名称未能识别")
                if not result["items"]:
                    result["warnings"].append("未能识别物料明细")

                result["status"] = (
                    "success" if result["confidence"] >= 0.7 else "review"
                )

            result["output_dir"] = parse_result.get("output_dir")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        end_time = datetime.now()
        result["process_duration_ms"] = int(
            (end_time - start_time).total_seconds() * 1000
        )

        return result


def main():
    OLLAMA_URL = "http://10.142.1.112:11434/v1"
    OLLAMA_MODEL = "qwen3.5:27b"

    PDF_PATH = r"D:\Workbench\n8n-projects\test-pdfs\PO-SSVF (7011)-1106979164.pdf"

    print("=" * 60)
    print("PO Parser 测试")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    print(f"PDF 文件: {PDF_PATH}")
    print("=" * 60)

    if not os.path.exists(PDF_PATH):
        print(f"错误: PDF 文件不存在: {PDF_PATH}")
        sys.exit(1)

    parser = POParserTest(OLLAMA_URL, OLLAMA_MODEL)

    result = parser.process_po(PDF_PATH)

    print(f"\n{'=' * 60}")
    print("解析结果")
    print(f"{'=' * 60}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    output_path = (
        Path(PDF_PATH).parent / "output" / f"{Path(PDF_PATH).stem}_result.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
