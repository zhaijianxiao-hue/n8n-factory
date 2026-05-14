from pathlib import Path

from .json_io import write_json


def choose_candidate(text_candidate: dict, vision_candidate: dict) -> tuple[dict, str]:
    text_items = text_candidate.get("items") or []
    vision_items = vision_candidate.get("items") or []
    if vision_items and not text_items:
        return vision_candidate, "vision"
    if text_items and not vision_items:
        return text_candidate, "text"
    if vision_candidate.get("confidence", 0) >= text_candidate.get("confidence", 0):
        return vision_candidate, "vision"
    return text_candidate, "text"


def build_conflict_report(
    sample_key: str,
    chosen_source: str,
    text_candidate: dict,
    vision_candidate: dict,
) -> str:
    text_items = len(text_candidate.get("items") or [])
    vision_items = len(vision_candidate.get("items") or [])
    return "\n".join([
        f"# Adjudication Conflict Report: {sample_key}",
        "",
        "## Summary",
        "",
        f"- chosen_source: {chosen_source}",
        f"- text_items: {text_items}",
        f"- vision_items: {vision_items}",
        "- human_review_required: true",
        "",
        "Human must approve expected JSON before this draft becomes a profile fixture.",
        "",
    ])


def build_field_evidence(chosen: dict, chosen_source: str) -> dict:
    header = chosen.get("header") or {}
    confidence = chosen.get("confidence", 0)
    return {
        "chosen_source": chosen_source,
        "human_review_required": True,
        "header": {
            key: {
                "chosen_value": value,
                "chosen_source": chosen_source,
                "confidence": confidence,
                "human_review_required": True,
            }
            for key, value in header.items()
        },
    }


def build_profile_suggestions() -> str:
    return "\n".join([
        "# Profile Suggestions",
        "",
        "- Review number format and decimal separators.",
        "- Review item row boundaries.",
        "- Review date format and delivery date rules.",
        "",
    ])


def adjudicate_sample(
    sample_key: str,
    text_candidate: dict,
    vision_candidate: dict,
    output_dir: Path,
) -> None:
    chosen, chosen_source = choose_candidate(text_candidate, vision_candidate)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / f"{sample_key}.merged_draft.json", chosen)
    write_json(
        output_dir / f"{sample_key}.field_evidence.json",
        build_field_evidence(chosen, chosen_source),
    )
    (output_dir / f"{sample_key}.conflict_report.md").write_text(
        build_conflict_report(sample_key, chosen_source, text_candidate, vision_candidate),
        encoding="utf-8",
    )
    (output_dir / f"{sample_key}.profile_suggestions.md").write_text(
        build_profile_suggestions(),
        encoding="utf-8",
    )
