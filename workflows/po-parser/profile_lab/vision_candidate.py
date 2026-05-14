from pathlib import Path

from .text_candidate import build_empty_candidate


def generate_vision_candidate(pdf_path: Path, page_paths: list[Path]) -> dict:
    candidate = build_empty_candidate(source_file=pdf_path.name, source="vision")
    candidate["metadata"]["page_count"] = len(page_paths)
    return candidate
