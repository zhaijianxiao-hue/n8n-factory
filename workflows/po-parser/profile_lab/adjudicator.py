from copy import deepcopy
from pathlib import Path

from .json_io import write_json

NO_USABLE_CANDIDATE_WARNING = (
    "no usable candidate was produced; human review required before expected JSON approval"
)


def candidate_has_content(candidate: dict) -> bool:
    if candidate.get("items"):
        return True

    header = candidate.get("header") or {}
    if any(value is not None and str(value).strip() for value in header.values()):
        return True

    return candidate.get("confidence", 0) > 0


def choose_candidate(text_candidate: dict, vision_candidate: dict) -> tuple[dict, str]:
    if not candidate_has_content(text_candidate) and not candidate_has_content(vision_candidate):
        return vision_candidate, "vision"

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
    adjudication_status: str | None = None,
) -> str:
    text_items = len(text_candidate.get("items") or [])
    vision_items = len(vision_candidate.get("items") or [])
    lines = [
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
    ]
    if adjudication_status == "no_usable_candidate":
        lines.extend([
            "## No Usable Candidate",
            "",
            "No usable candidate was produced; human review is required before expected JSON approval.",
            "",
        ])
    return "\n".join(lines)


def build_field_evidence(
    chosen: dict,
    chosen_source: str,
    adjudication_status: str | None = None,
) -> dict:
    header = chosen.get("header") or {}
    confidence = chosen.get("confidence", 0)
    evidence = {
        "chosen_source": chosen_source,
        "human_review_required": True,
    }
    for key, value in header.items():
        evidence[f"header.{key}"] = {
            "chosen_value": value,
            "chosen_source": chosen_source,
            "confidence": confidence,
            "human_review_required": True,
        }
    if adjudication_status == "no_usable_candidate":
        evidence["_adjudication"] = {
            "status": adjudication_status,
            "chosen_source": chosen_source,
            "confidence": 0.0,
            "human_review_required": True,
            "reason": NO_USABLE_CANDIDATE_WARNING,
        }
    return evidence


def mark_no_usable_candidate(chosen: dict) -> dict:
    draft = deepcopy(chosen)
    warnings = list(draft.get("warnings") or [])
    if NO_USABLE_CANDIDATE_WARNING not in warnings:
        warnings.append(NO_USABLE_CANDIDATE_WARNING)
    draft["warnings"] = warnings
    draft["status"] = "review"
    draft["confidence"] = 0.0
    metadata = dict(draft.get("metadata") or {})
    metadata["adjudication_status"] = "no_usable_candidate"
    draft["metadata"] = metadata
    return draft


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
    no_usable_candidate = (
        not candidate_has_content(text_candidate)
        and not candidate_has_content(vision_candidate)
    )
    adjudication_status = "no_usable_candidate" if no_usable_candidate else None
    if no_usable_candidate:
        chosen = mark_no_usable_candidate(chosen)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / f"{sample_key}.merged_draft.json", chosen)
    write_json(
        output_dir / f"{sample_key}.field_evidence.json",
        build_field_evidence(chosen, chosen_source, adjudication_status),
    )
    (output_dir / f"{sample_key}.conflict_report.md").write_text(
        build_conflict_report(
            sample_key,
            chosen_source,
            text_candidate,
            vision_candidate,
            adjudication_status,
        ),
        encoding="utf-8",
    )
    (output_dir / f"{sample_key}.profile_suggestions.md").write_text(
        build_profile_suggestions(),
        encoding="utf-8",
    )
