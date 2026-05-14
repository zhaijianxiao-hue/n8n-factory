import base64
from pathlib import Path

from .llm_client import JsonClient
from .text_candidate import build_empty_candidate


def generate_vision_candidate(pdf_path: Path, page_paths: list[Path]) -> dict:
    candidate = build_empty_candidate(source_file=pdf_path.name, source="vision")
    candidate["metadata"]["page_count"] = len(page_paths)
    return candidate


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def generate_vision_candidate_with_model(
    pdf_path: Path,
    page_paths: list[Path],
    prompt: str,
    model: str,
    client: JsonClient,
) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for page_path in page_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encode_image(page_path)}",
                },
            }
        )

    messages = [
        {
            "role": "user",
            "content": content,
        }
    ]
    candidate = client.create_json(messages=messages, model=model)
    candidate["source_file"] = pdf_path.name
    candidate.setdefault("items", [])
    candidate.setdefault("warnings", [])
    candidate.setdefault("confidence", 0.0)
    metadata = candidate.setdefault("metadata", {})
    metadata["candidate_source"] = "vision"
    metadata["model"] = model
    metadata["page_count"] = len(page_paths)
    return candidate
