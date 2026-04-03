# -*- coding: utf-8 -*-
"""
PO Parser 完整测试脚本
使用 PyMuPDF 提取文本 + Ollama 字段抽取
"""

import json
import hashlib
import fitz
import sys
import requests
from openai import OpenAI
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OLLAMA_URL = "http://10.142.1.112:11434/v1"
OLLAMA_MODEL = "qwen3.5:27b"

PDF_PATH = r"D:\Workbench\n8n-projects\test-pdfs\PO-SSVF (7011)-1106979164.pdf"


def extract_text_from_pdf(pdf_path: str, output_dir: str = None) -> str:
    """使用 PyMuPDF 提取 PDF 文本"""
    print(f"\n{'=' * 60}")
    print("Step 1: 提取 PDF 文本")
    print(f"{'=' * 60}")

    doc = fitz.open(pdf_path)
    page_count = len(doc)
    text_parts = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        text_parts.append(f"--- Page {page_num} ---\n{text}")

    doc.close()
    full_text = "\n".join(text_parts)
    print(f"[OK] 提取完成，共 {page_count} 页，{len(full_text)} 字符")

    if output_dir:
        txt_path = Path(output_dir) / f"{Path(pdf_path).stem}_text.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"[OK] 文本已保存到: {txt_path}")

    return full_text


def extract_fields_with_ollama(text_content: str) -> dict:
    """使用 Ollama 抽取字段"""
    print(f"\n{'=' * 60}")
    print(f"Step 2: Ollama 字段抽取 ({OLLAMA_MODEL})")
    print(f"{'=' * 60}")

    client = OpenAI(base_url=OLLAMA_URL, api_key="ollama")

    prompt = f"""You are a purchase order parsing assistant. Extract key fields from the following purchase order text and output in JSON format.

Requirements:
1. Extract these fields:
   - customer_name: Customer/Supplier name
   - po_number: Purchase Order number
   - po_date: Order date (format: YYYY-MM-DD)
   - currency: Currency (USD, CNY, EUR, etc.)
   - total_amount: Total amount (number only)
   - items: List of line items, each containing:
     - line_no: Line number
     - material: Material code/Part number
     - description: Material description
     - qty: Quantity (number)
     - unit_price: Unit price (number)
     - amount: Line amount (number)

2. If a field cannot be determined, set to null
3. Output pure JSON format only, no markdown or extra text
4. Provide confidence score (0-1)
5. List any uncertain or missing fields in warnings array

Purchase Order content:
{text_content[:8000]}

Output JSON directly:"""

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional purchase order data extraction assistant. Output pure JSON only, no markdown or extra text.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                lines[1:-1] if lines[-1].startswith("```") else lines[1:]
            )

        result = json.loads(content)
        print(f"[OK] 字段抽取完成")
        return result

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        return {
            "error": str(e),
            "raw_response": content[:1000] if "content" in dir() else None,
        }
    except Exception as e:
        print(f"[ERROR] Ollama 调用失败: {e}")
        raise


def process_po(pdf_path: str) -> dict:
    """完整处理流程"""
    print(f"\n{'#' * 60}")
    print(f"# Purchase Order Parsing Test")
    print(f"# File: {pdf_path}")
    print(f"{'#' * 60}")

    start_time = datetime.now()
    output_dir = Path(pdf_path).parent / "output"

    text_content = extract_text_from_pdf(pdf_path, str(output_dir))

    fields = extract_fields_with_ollama(text_content)

    file_hash = hashlib.md5(open(pdf_path, "rb").read()).hexdigest()

    result = {
        "source_file": Path(pdf_path).name,
        "file_hash": file_hash,
        "process_time": start_time.isoformat(),
        "header": {
            "customer_name": fields.get("customer_name"),
            "po_number": fields.get("po_number"),
            "po_date": fields.get("po_date"),
            "currency": fields.get("currency"),
            "total_amount": fields.get("total_amount"),
        },
        "items": fields.get("items", []),
        "confidence": fields.get("confidence", 0.5),
        "warnings": fields.get("warnings", []),
        "raw_text_length": len(text_content),
        "process_duration_ms": int(
            (datetime.now() - start_time).total_seconds() * 1000
        ),
    }

    return result


def main():
    print("=" * 60)
    print("PO Parser Test")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    print(f"PDF File: {PDF_PATH}")
    print("=" * 60)

    result = process_po(PDF_PATH)

    print(f"\n{'=' * 60}")
    print("Result")
    print(f"{'=' * 60}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    output_dir = Path(PDF_PATH).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{Path(PDF_PATH).stem}_result.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Result saved to: {output_path}")


if __name__ == "__main__":
    main()
