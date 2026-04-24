"""
PO Parser 服务
FastAPI 服务，供 n8n 调用
"""

import os
import re
import json
import uuid
import hashlib
import fitz
import requests
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

app = FastAPI(title="PO Parser Service", version="1.0.0")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://10.142.1.112:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:27b")

SAP_URL = os.getenv(
    "SAP_URL",
    "http://10.142.1.20:8000/sap/bc/srt/rfc/sap/zws_general/600/zws_general/zbd_general?sap-client=600",
)
SAP_USER = os.getenv("SAP_USER", "")
SAP_PASS = os.getenv("SAP_PASS", "")


class POHeader(BaseModel):
    customer_name: Optional[str] = None
    customer_code: Optional[str] = None
    po_number: Optional[str] = None
    po_date: Optional[str] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    buyer_address: Optional[str] = None
    supplier_id_at_customer: Optional[str] = None
    customer_contact_person: Optional[str] = None
    customer_contact_phone: Optional[str] = None
    customer_contact_email: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact_person: Optional[str] = None
    supplier_address: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    shipment_mode: Optional[str] = None
    delivery_tolerance_positive_pct: Optional[float] = None
    delivery_tolerance_negative_pct: Optional[float] = None
    delivery_tolerance_raw: Optional[str] = None
    blanket_order_note: Optional[str] = None
    production_note: Optional[str] = None
    packaging_note: Optional[str] = None


class POItem(BaseModel):
    line_no: Optional[int] = None
    material: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[float] = None
    unit: Optional[str] = None
    customer_material: Optional[str] = None
    material_description: Optional[str] = None
    customer_release_no: Optional[str] = None
    customer_release_pos: Optional[str] = None
    delivery_date: Optional[str] = None
    price_basis_qty: Optional[float] = None
    price_basis_unit: Optional[str] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    description_raw: Optional[str] = None
    article_raw: Optional[str] = None


class POResult(BaseModel):
    source_file: str
    customer_profile: Optional[str] = None
    file_hash: str
    process_time: str
    header: POHeader
    items: List[POItem]
    confidence: float
    warnings: List[str]
    status: str
    output_file: Optional[str] = None


class ParseRequest(BaseModel):
    pdf_path: str
    output_dir: Optional[str] = None


class ScanRequest(BaseModel):
    directory: str
    pattern: str = "*.pdf"


class MoveRequest(BaseModel):
    source: str
    destination: str


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def collapse_for_matching(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def parse_eu_number(value: str) -> float:
    cleaned = value.replace(".", "").replace(",", ".").strip()
    return float(cleaned)


def parse_evytra_date(value: str) -> str:
    day, month, year = value.split(".")
    return f"{year}-{month}-{day}"


def detect_customer_profile(text_content: str) -> Optional[str]:
    collapsed = collapse_for_matching(text_content)
    markers = [
        "evytragmbh",
        "yoursupplierid",
        "orderconfirmationevytracom",
    ]
    if all(marker in collapsed for marker in markers) and re.search(
        r"\bOrder\s+\d+\b", text_content
    ):
        return "evytra"
    return None


def extract_between(
    text_content: str, start_marker: str, end_marker: str
) -> Optional[str]:
    pattern = re.escape(start_marker) + r"\s*(.*?)\s*" + re.escape(end_marker)
    match = re.search(pattern, text_content, re.DOTALL)
    if not match:
        return None
    return normalize_whitespace(match.group(1))


def parse_evytra_text(text_content: str) -> dict:
    warnings = []

    po_number_match = re.search(r"\bOrder\s+(\d+)\b", text_content)
    po_date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text_content)
    supplier_id_match = re.search(
        r"Your supplier ID:\s*(?:\n|\s)+([\d]+)", text_content
    )
    # OCR layout is misaligned: contact name appears BEFORE "Our contact:" label
    contact_match = re.search(r"([^\n]+)\nOur contact:", text_content)
    # Email appears AFTER "Our contact:" label
    email_match = re.search(r"Our contact:\s*\n\s*([^\n]+@[^\n]+)", text_content)
    # Due to OCR layout shift, phone appears after "Fax no.:" label
    phone_match = re.search(r"Fax no\.:\s*\n\s*([+\d][\d\s/.-]+)", text_content)
    # Fax is typically empty; if present would be after Phone-no:. but usually blank
    fax_match = None  # No fax in current EVYTRA PDFs
    total_amount_match = re.search(
        r"Order amount\s*(?:\n|\s)+EUR\s*(?:\n|\s)+([\d\.,]+)", text_content
    )
    incoterms_match = re.search(
        r"([A-Z]{3}\s+Schwenningen)\s*\nIncoterms:", text_content
    )
    payment_terms_match = re.search(
        r"(90\s+days\s+net)\s*\nTerms of payment:", text_content
    )
    shipment_mode_match = re.search(r"(Airfreight)\s*\nMode of shipment:", text_content)
    tolerance_match = re.search(
        r"(>>>\s*Deliver:\s*\+\s*/\s*-\s*(\d+)\s*%\s*<<<)", text_content
    )

    blanket_match = re.search(
        r">>>\s*Blanket order quantity:.*?<<<",
        text_content,
        re.DOTALL,
    )
    blanket_note = normalize_whitespace(blanket_match.group(0)) if blanket_match else None

    production_match = re.search(
        r">>>\s*Production lot:.*?<<<",
        text_content,
        re.DOTALL,
    )
    production_note = (
        normalize_whitespace(production_match.group(0)) if production_match else None
    )
    # Extract full packaging note: >>> Please pack ... <<<
    packaging_match = re.search(
        r">>>\s*Please pack the boards.*?<<<",
        text_content,
        re.DOTALL
    )
    packaging_note = normalize_whitespace(packaging_match.group(0)) if packaging_match else None

    item_header_pattern = re.compile(
        r"(?P<line_no>10|20|30|40)\s+"
        r"(?P<material_description>\d+)\s+"
        r"(?P<qty>[\d\.]+)\s+"
        r"(?P<customer_material>\d+)\s+TA\s+"
        r"(?P<unit>pcs)",
        re.DOTALL,
    )

    detail_pattern = re.compile(
        r"Order:\s+"
        r"(?P<release_no>\d+)(?:\s+Pos\.\s+(?P<release_pos>[\d\.]+))?\s+"
        r"Delivery date:\s+"
        r"(?P<delivery_date>\d{2}\.\d{2}\.\d{4})\s+"
        r"(?P<price_section>.*)$",
        re.DOTALL,
    )

    header_matches = list(item_header_pattern.finditer(text_content))
    items = []
    for index, match in enumerate(header_matches):
        block_start = match.start()
        block_end = (
            header_matches[index + 1].start()
            if index + 1 < len(header_matches)
            else len(text_content)
        )
        block_text = text_content[block_start:block_end]
        detail_match = detail_pattern.search(block_text)
        if not detail_match:
            continue

        price_section = normalize_whitespace(detail_match.group("price_section"))

        amount_match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})", price_section)
        price_match = re.search(
            r"for\s+(\d+(?:\.\d+)?)\s+pcs:\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s+EUR",
            price_section,
        )

        if price_match:
            basis_qty_value = parse_eu_number(price_match.group(1))
            basis_unit_value = "pcs"
            unit_price_value = parse_eu_number(price_match.group(2))
            amount_candidates = re.findall(
                r"(\d{1,3}(?:\.\d{3})*,\d{2})", price_section
            )
            amount_value = (
                parse_eu_number(amount_candidates[0]) if amount_candidates else None
            )
        else:
            number_candidates = re.findall(
                r"(\d{1,3}(?:\.\d{3})*,\d{2})", price_section
            )
            unit_price_value = (
                parse_eu_number(number_candidates[-1]) if number_candidates else None
            )
            amount_value = (
                parse_eu_number(number_candidates[0]) if number_candidates else None
            )
            basis_qty_value = 1.0
            basis_unit_value = match.group("unit")

        if amount_value is None or unit_price_value is None:
            continue

        item = {
            "line_no": int(match.group("line_no")),
            "qty": parse_eu_number(match.group("qty")),
            "unit": match.group("unit"),
            "customer_material": match.group("customer_material"),
            "material_description": match.group("material_description"),
            "customer_release_no": detail_match.group("release_no"),
            "customer_release_pos": detail_match.group("release_pos"),
            "delivery_date": parse_evytra_date(detail_match.group("delivery_date")),
            "price_basis_qty": basis_qty_value,
            "price_basis_unit": basis_unit_value,
            "unit_price": unit_price_value,
            "amount": amount_value,
            "currency": "EUR",
            "description_raw": f"{match.group('customer_material')} TA",
            "article_raw": match.group("material_description"),
        }
        items.append(item)

    if any(item["price_basis_qty"] == 1 and item["amount"] > 1000 for item in items):
        warnings.append("Suspicious item 30 amount or price basis detected")

    item_total = sum(item["amount"] for item in items)
    total_amount = (
        parse_eu_number(total_amount_match.group(1)) if total_amount_match else None
    )
    if total_amount is not None and abs(item_total - total_amount) > 0.01:
        warnings.append("Parsed item amounts do not reconcile to order total")

    tolerance_value = float(tolerance_match.group(2)) if tolerance_match else None

    header = {
        "customer_name": "EVYTRA GmbH",
        "customer_code": "evytra",
        "po_number": po_number_match.group(1) if po_number_match else None,
        "po_date": parse_evytra_date(po_date_match.group(1)) if po_date_match else None,
        "currency": "EUR",
        "total_amount": total_amount,
        "buyer_address": "Sturmbuhlstr. 180 - 184, 78054 VS-Schwenningen",
        "supplier_id_at_customer": supplier_id_match.group(1)
        if supplier_id_match
        else None,
        "customer_contact_person": contact_match.group(1).strip() if contact_match else None,
        "customer_contact_phone": phone_match.group(1).strip() if phone_match else None,
        "customer_contact_fax": "",  # EVYTRA PDFs do not contain fax
        "customer_contact_email": email_match.group(1).strip() if email_match else None,
        "supplier_name": "Tianjin Printronics Circuit Corp.",
        "supplier_contact_person": "Mrs Tina Zhang",
        "supplier_address": "No. 53 Hanghai Rd, Airport Economic Area, 300308 Tianjin / China, VR CHINA",
        "delivery_terms": incoterms_match.group(1) if incoterms_match else None,
        "payment_terms": payment_terms_match.group(1) if payment_terms_match else None,
        "shipment_mode": shipment_mode_match.group(1) if shipment_mode_match else None,
        "delivery_tolerance_positive_pct": tolerance_value,
        "delivery_tolerance_negative_pct": tolerance_value,
        "delivery_tolerance_raw": tolerance_match.group(1) if tolerance_match else None,
        "blanket_order_note": blanket_note,
        "production_note": production_note,
        "packaging_note": packaging_note,
    }

    return {
        "customer_profile": "evytra",
        "header": header,
        "items": items,
        "confidence": 0.95,
        "warnings": warnings,
        "status": "review" if warnings else "success",
    }


def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text_parts = []
    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        text_parts.append(f"--- Page {page_num} ---\n{text}")
    doc.close()
    return "\n".join(text_parts)


def extract_fields_with_ollama(text_content: str) -> dict:
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
        from openai import OpenAI

        client = OpenAI(base_url=OLLAMA_URL, api_key="ollama")

        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional purchase order data extraction assistant. Output pure JSON only.",
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

        return json.loads(content)

    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "ollama_url": OLLAMA_URL}


@app.post("/parse", response_model=POResult)
async def parse_po(request: ParseRequest):
    """解析采购订单 PDF"""

    pdf_path = request.pdf_path
    output_dir = request.output_dir or str(Path(pdf_path).parent / "output")

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail=f"PDF file not found: {pdf_path}")

    start_time = datetime.now()

    text_content = extract_text_from_pdf(pdf_path)

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="PDF contains no extractable text")

    customer_profile = detect_customer_profile(text_content)
    if customer_profile == "evytra":
        fields = parse_evytra_text(text_content)
    else:
        fields = extract_fields_with_ollama(text_content)

    file_hash = hashlib.md5(open(pdf_path, "rb").read()).hexdigest()

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{Path(pdf_path).stem}_result.json")

    result = {
        "source_file": Path(pdf_path).name,
        "customer_profile": fields.get("customer_profile"),
        "file_hash": file_hash,
        "process_time": start_time.isoformat(),
        "header": fields.get(
            "header",
            {
                "customer_name": fields.get("customer_name"),
                "po_number": fields.get("po_number"),
                "po_date": fields.get("po_date"),
                "currency": fields.get("currency"),
                "total_amount": fields.get("total_amount"),
            },
        ),
        "items": fields.get("items", []),
        "confidence": fields.get("confidence", 0.5),
        "warnings": fields.get("warnings", []),
        "status": "error" if fields.get("error") else fields.get("status", "success"),
        "output_file": output_file,
    }

    if fields.get("error"):
        result["warnings"].append(f"LLM error: {fields['error']}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


@app.post("/scan")
async def scan_directory(request: ScanRequest):
    """扫描目录中的 PDF 文件"""

    if not os.path.exists(request.directory):
        raise HTTPException(
            status_code=404, detail=f"Directory not found: {request.directory}"
        )

    directory = Path(request.directory)
    if request.pattern.lower() == "*.pdf":
        files = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ]
    else:
        files = list(directory.glob(request.pattern))

    return {
        "directory": request.directory,
        "pattern": request.pattern,
        "count": len(files),
        "files": [str(f) for f in files],
    }


@app.post("/move")
async def move_file(request: MoveRequest):
    """移动文件"""

    import shutil

    if not os.path.exists(request.source):
        raise HTTPException(
            status_code=404, detail=f"Source file not found: {request.source}"
        )

    os.makedirs(os.path.dirname(request.destination), exist_ok=True)
    shutil.move(request.source, request.destination)

    return {
        "source": request.source,
        "destination": request.destination,
        "status": "moved",
    }


class ToSapRequest(BaseModel):
    parse_result: dict


def _build_sap_input(parse_result: dict) -> dict:
    header = parse_result.get("header", {})
    items = parse_result.get("items", [])

    # Use a fresh random GUID for each SAP submission to prevent duplicate primary keys
    guid = uuid.uuid4().hex.upper()[:32]

    po_date_raw = header.get("po_date", "")
    erdat = po_date_raw.replace("-", "") if po_date_raw else ""

    notes_cleanup = lambda s: re.sub(r">>>\s*", "", s).replace("<<<", "").strip() if s else ""

    sap_header = {
        "GUID": guid,
        "ZKUNNR_NAME": header.get("customer_name", ""),
        "ZKUNNR_SNAME": header.get("customer_code", ""),
        "BSTNK": header.get("po_number", ""),
        "ERDAT": erdat,
        "ZKUNNR_ADD": header.get("buyer_address", ""),
        "ZKUNNR_CONTACT": header.get("customer_contact_person", ""),
        "ZKUNNR_PHONE": header.get("customer_contact_phone", ""),
        "ZKUNNR_FAX": header.get("customer_contact_fax", ""),
        "ZKUNNR_EMAIL": header.get("customer_contact_email", ""),
        "ZVENDOR_NO": header.get("supplier_id_at_customer", ""),
        "ZVENDOR_NAME": header.get("supplier_name", ""),
        "ZVENDOR_ADD": header.get("supplier_address", ""),
        "ZVENDOR_CONTACT": header.get("supplier_contact_person", ""),
        "ZDELIVERY_TOLERANCE_P": header.get("delivery_tolerance_positive_pct"),
        "ZDELIVERY_TOLERANCE_N": header.get("delivery_tolerance_negative_pct"),
        "ZINCOTERMS_TEXT": header.get("delivery_terms", ""),
        "ZINCOTERMS_LOC_TEXT": "",
        "ZPAYMENT_TERM_TEXT": header.get("payment_terms", ""),
        "ZSHIPMENT_MODE_TEXT": header.get("shipment_mode", ""),
        "NETWR": header.get("total_amount"),
        "WAERK": header.get("currency", ""),
        "ZORDERS_REQ_REMARK": notes_cleanup(header.get("blanket_order_note")),
        "ZOVERLOADING_REQ": notes_cleanup(header.get("delivery_tolerance_raw")),
        "ZPACKING_REQ": notes_cleanup(header.get("packaging_note")),
        "ZORDERS_REMARK": notes_cleanup(header.get("production_note")),
        "ZFILE_NAME": parse_result.get("source_file", ""),
    }

    delivery_date_raw = ""
    sap_items = []
    for item in items:
        delivery_date_raw = item.get("delivery_date", "")
        zcust_delivery_date = delivery_date_raw.replace("-", "") if delivery_date_raw else ""

        sap_items.append({
            "GUID": guid,
            "BSTNK": header.get("po_number", ""),
            "ZITEM_NUM": str(item.get("line_no", "")),
            "MAKTX": str(item.get("material_description", "")),
            "ZCUST_MAT_NUM": str(item.get("material_description", "")),
            "ZCUST_MAT_DESC": "",
            "ZENDCUST_MAT_NUM": str(item.get("customer_material", "")),
            "ZENDCUST_MAT_DESC": "",
            "KWMENG": item.get("qty"),
            "VRKME": item.get("unit", ""),
            "ZINT_PO_NUM": str(item.get("customer_release_no", "")),
            "ZCUSTOMER_DELIVERY_DATE": zcust_delivery_date,
            "ZPRICE_QTY": item.get("price_basis_qty"),
            "ZPRICE_UNIT": item.get("price_basis_unit", ""),
            "ZPRICE_AMOUNT": item.get("unit_price"),
            "ZPRICE_WAERK": item.get("currency", ""),
            "NETWR": item.get("amount"),
            "WAERK": item.get("currency", ""),
        })

    sap_header["ZCUST_REQ_ITEM"] = sap_items
    return sap_header


def _build_soap_xml(sap_input: dict) -> str:
    now = datetime.utcnow()
    rdate = now.strftime("%Y%m%d")
    rtime = now.strftime("%H%M%S")
    guid = sap_input.get("GUID", "")

    i_input_json = json.dumps(sap_input, ensure_ascii=False, indent=2)

    soap = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions">
   <soapenv:Header/>
   <soapenv:Body>
      <urn:Z_FMBC_IF_INBOUND>
         <I_DATA_GD>
            <GUID>{guid}</GUID>
            <BUTYPE>SD0026</BUTYPE>
            <SYSID>n8n</SYSID>
            <HOST>n8n</HOST>
            <IPADDR>n8n</IPADDR>
            <USERID>n8n</USERID>
            <UNAME>n8n</UNAME>
            <RDATE>{rdate}</RDATE>
            <RTIME>{rtime}</RTIME>
         </I_DATA_GD>
         <I_INPUT>{i_input_json}
         </I_INPUT>
      </urn:Z_FMBC_IF_INBOUND>
   </soapenv:Body>
</soapenv:Envelope>"""
    return soap


def _parse_sap_response(soap_response_text: str) -> dict:
    match = re.search(r"<E_OUTPUT>([^<]+)</E_OUTPUT>", soap_response_text)
    if not match:
        return {
            "success": False,
            "type": "E",
            "message": "E_OUTPUT not found in SOAP response",
            "raw": soap_response_text[:500],
        }
    try:
        e_output_raw = json.loads(match.group(1))
        e_output = e_output_raw[0] if isinstance(e_output_raw, list) else e_output_raw
        return {
            "success": e_output.get("TYPE") == "S",
            "type": e_output.get("TYPE", ""),
            "message": e_output.get("MESSAGE", ""),
            "error": e_output.get("MESSAGE") if e_output.get("TYPE") != "S" else None,
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "type": "E",
            "message": f"Failed to parse E_OUTPUT: {e}",
            "raw": match.group(1),
        }


@app.post("/to-sap")
async def send_to_sap(request: ToSapRequest):
    """将解析结果转换并发送到 SAP"""

    if not SAP_USER or not SAP_PASS:
        raise HTTPException(
            status_code=500,
            detail="SAP credentials not configured (SAP_USER / SAP_PASS env vars)",
        )

    sap_input = _build_sap_input(request.parse_result)
    soap_xml = _build_soap_xml(sap_input)

    try:
        resp = requests.post(
            SAP_URL,
            data=soap_xml.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            auth=(SAP_USER, SAP_PASS),
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"SAP request failed: {str(e)}",
        )

    result = _parse_sap_response(resp.text)
    return {
        "sap_status": result,
        "guid": sap_input.get("GUID"),
        "bstnk": sap_input.get("BSTNK"),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
