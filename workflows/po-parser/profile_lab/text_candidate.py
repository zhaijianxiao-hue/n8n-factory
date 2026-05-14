from pathlib import Path

from .llm_client import JsonClient


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to extract PDF text") from exc

    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def build_empty_candidate(source_file: str, source: str) -> dict:
    return {
        "source_file": source_file,
        "customer_profile": None,
        "header": {
            "customer_name": None,
            "po_number": None,
            "po_date": None,
            "currency": None,
            "total_amount": None,
        },
        "items": [],
        "confidence": 0.0,
        "warnings": [
            f"{source} candidate is empty because model extraction is not configured"
        ],
        "status": "review",
        "metadata": {"candidate_source": source},
    }


def generate_text_candidate(pdf_path: Path) -> dict:
    return build_empty_candidate(source_file=pdf_path.name, source="text")


def generate_text_candidate_with_model(
    pdf_path: Path,
    extracted_text: str,
    prompt: str,
    model: str,
    client: JsonClient,
) -> dict:
    messages = [
        {
            "role": "system",
            "content": prompt,
        },
        {
            "role": "user",
            "content": extracted_text,
        },
    ]
    candidate = client.create_json(messages=messages, model=model)
    candidate["source_file"] = pdf_path.name
    candidate.setdefault("items", [])
    candidate.setdefault("warnings", [])
    candidate.setdefault("confidence", 0.0)
    metadata = candidate.setdefault("metadata", {})
    metadata["candidate_source"] = "text"
    metadata["model"] = model
    return candidate
