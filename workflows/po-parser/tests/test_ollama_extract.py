"""
Ollama 字段抽取测试（不需要 Java/OpenDataLoader）
直接测试 Ollama 的字段抽取能力
"""

import json
import requests
from pathlib import Path

OLLAMA_URL = "http://10.142.1.112:11434/v1"
OLLAMA_MODEL = "qwen3.5:27b"


def test_ollama_connection():
    """测试 Ollama 连接"""
    print(f"测试 Ollama 连接: {OLLAMA_URL}")

    try:
        response = requests.get(f"{OLLAMA_URL.replace('/v1', '')}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✓ Ollama 连接成功")
            print(f"  可用模型: {[m['name'] for m in models]}")
            return True
    except Exception as e:
        print(f"✗ Ollama 连接失败: {e}")
        return False


def extract_fields_with_ollama(text_content: str) -> dict:
    """使用 Ollama 抽取字段"""

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
{text_content[:6000]}

请输出 JSON："""

    try:
        from openai import OpenAI

        client = OpenAI(base_url=OLLAMA_URL, api_key="ollama")

        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
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

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())

    except Exception as e:
        return {
            "error": str(e),
            "raw_response": content if "content" in dir() else None,
        }


def test_with_sample_text():
    """使用样本文本测试"""

    sample_po = """
采购订单
PURCHASE ORDER

客户名称: ABC Corporation Ltd.
订单编号: PO-2024-001234
订单日期: 2024年12月15日

币种: USD

交货地址: 广东省深圳市南山区科技园

物料明细:
序号  物料编码      描述              数量    单价(USD)   金额(USD)
1     MAT-001      电子产品A         100     25.50       2,550.00
2     MAT-002      电子元件B         500     5.20        2,600.00
3     MAT-003      包装材料C         200     3.00        600.00

总计: 5,750.00 USD

联系人: 张经理
电话: 0755-12345678
"""

    print("\n" + "=" * 60)
    print("测试样本文本字段抽取")
    print("=" * 60)
    print(f"输入文本:\n{sample_po[:200]}...")

    result = extract_fields_with_ollama(sample_po)

    print("\n抽取结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return result


def test_with_pdf_text(pdf_path: str):
    """使用 PDF 文本测试（需要你手动提取文本后粘贴）"""

    print(f"\n{'=' * 60}")
    print(f"测试 PDF 内容字段抽取: {pdf_path}")
    print("=" * 60)

    text = input("\n请粘贴 PDF 文本内容（按 Enter 使用样本文本）:\n").strip()

    if not text:
        return test_with_sample_text()

    result = extract_fields_with_ollama(text)

    print("\n抽取结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return result


def main():
    print("=" * 60)
    print("Ollama 字段抽取测试")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Model: {OLLAMA_MODEL}")
    print("=" * 60)

    if not test_ollama_connection():
        print("\n请检查 Ollama 服务是否运行")
        return

    print("\n选择测试模式:")
    print("1. 使用内置样本文本测试")
    print("2. 手动输入 PDF 文本测试")

    choice = input("\n请选择 (1/2): ").strip()

    if choice == "2":
        test_with_pdf_text("")
    else:
        test_with_sample_text()


if __name__ == "__main__":
    main()
