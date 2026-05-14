from pathlib import Path

from .json_io import read_json, write_json
from .models import current_timestamp


class PublishGateError(RuntimeError):
    pass


def require_publish_gate(condition: bool, reason: str) -> None:
    if not condition:
        raise PublishGateError(reason)


def is_positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def score_at_least(scores: dict, field: str, threshold: float) -> bool:
    value = scores.get(field)
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= threshold


def validate_publish_summary(summary: dict) -> None:
    require_publish_gate(
        summary.get("publishable") is True,
        "summary.publishable must be true",
    )
    require_publish_gate(
        is_positive_int(summary.get("sample_count")),
        "sample_count must be greater than 0",
    )

    reports = summary.get("reports")
    require_publish_gate(
        isinstance(reports, list) and len(reports) > 0,
        "reports must be a non-empty list",
    )

    for index, report in enumerate(reports):
        require_publish_gate(
            isinstance(report, dict),
            f"reports[{index}] must be an object",
        )
        require_publish_gate(
            report.get("publishable") is True,
            f"reports[{index}].publishable must be true",
        )
        require_publish_gate(
            not report.get("blocking_errors"),
            f"reports[{index}].blocking_errors must be empty",
        )
        require_publish_gate(
            report.get("schema_pass") is True,
            f"reports[{index}].schema_pass must be true",
        )
        require_publish_gate(
            report.get("p0_pass") is True,
            f"reports[{index}].p0_pass must be true",
        )

        scores = report.get("scores")
        require_publish_gate(
            isinstance(scores, dict),
            f"reports[{index}].scores must be an object",
        )
        require_publish_gate(
            score_at_least(scores, "p1", 0.95),
            f"reports[{index}].scores.p1 must be at least 0.95",
        )
        require_publish_gate(
            score_at_least(scores, "business_rules", 0.95),
            f"reports[{index}].scores.business_rules must be at least 0.95",
        )


def publish_profile(root: Path, customer_key: str, run_id: str, production_dir: Path) -> Path:
    customer_dir = root / "customers" / customer_key
    summary_path = customer_dir / "runs" / run_id / "evaluation" / "summary.json"
    summary = read_json(summary_path)
    try:
        validate_publish_summary(summary)
    except PublishGateError as error:
        raise PublishGateError(
            f"profile is not publishable for customer={customer_key} run={run_id}: {error}"
        ) from error

    profile = read_json(customer_dir / "profile.json")
    profile["status"] = "production"
    profile["last_run_id"] = run_id
    profile["last_score"] = summary
    profile["published_at"] = current_timestamp()

    production_dir.mkdir(parents=True, exist_ok=True)
    output_path = production_dir / f"{customer_key}.json"
    write_json(output_path, profile)
    write_json(customer_dir / "profile.json", profile)
    return output_path
