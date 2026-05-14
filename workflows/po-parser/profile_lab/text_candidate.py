from pathlib import Path


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
