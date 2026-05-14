import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from profile_lab.publisher import PublishGateError
from profile_lab.publisher import validate_publish_summary

from .models import ApprovalRecord


class ApprovalGateError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def approval_path(run_dir: Path) -> Path:
    return Path(run_dir) / "approval.json"


def summary_path(run_dir: Path) -> Path:
    return Path(run_dir) / "evaluation" / "summary.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _model_to_dict(model: ApprovalRecord) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def load_approval(run_dir: Path) -> ApprovalRecord:
    path = approval_path(run_dir)
    if not path.exists():
        return ApprovalRecord()
    return ApprovalRecord(**read_json(path))


def save_approval(run_dir: Path, approval: ApprovalRecord) -> ApprovalRecord:
    write_json(approval_path(run_dir), _model_to_dict(approval))
    return approval


def load_summary(run_dir: Path) -> dict[str, Any]:
    path = summary_path(run_dir)
    if not path.exists():
        raise ApprovalGateError("evaluation summary is required")
    return read_json(path)


def summary_is_publishable(summary: dict[str, Any]) -> bool:
    try:
        validate_publish_summary(summary)
    except PublishGateError:
        return False
    return True


def summary_p0_passes(summary: dict[str, Any]) -> bool:
    reports = summary.get("reports", [])
    if not reports:
        return False
    return all(report.get("p0_pass") is True for report in reports)


def submit_run(run_dir: Path, submitted_by: str, note: str = "") -> ApprovalRecord:
    load_summary(run_dir)
    timestamp = now_iso()
    approval = load_approval(run_dir)
    approval.state = "submitted"
    approval.submitted_by = submitted_by
    approval.admin_decision = None
    approval.admin_by = None
    approval.admin_at = None
    approval.note = note
    approval.submitted_at = timestamp
    return save_approval(run_dir, approval)


def approve_run(run_dir: Path, admin_by: str, note: str = "") -> ApprovalRecord:
    summary = load_summary(run_dir)
    try:
        validate_publish_summary(summary)
    except PublishGateError as error:
        raise ApprovalGateError(str(error)) from error
    if not summary_p0_passes(summary):
        raise ApprovalGateError("P0 must pass")

    approval = load_approval(run_dir)
    if approval.state != "submitted":
        raise ApprovalGateError("approval state must be submitted")

    timestamp = now_iso()
    approval.state = "approved"
    approval.admin_decision = "approved"
    approval.admin_by = admin_by
    approval.note = note
    approval.admin_at = timestamp
    return save_approval(run_dir, approval)


def reject_run(run_dir: Path, admin_by: str, note: str = "") -> ApprovalRecord:
    approval = load_approval(run_dir)
    timestamp = now_iso()
    approval.state = "changes_requested"
    approval.admin_decision = "rejected"
    approval.admin_by = admin_by
    approval.note = note
    approval.admin_at = timestamp
    return save_approval(run_dir, approval)


def publish_allowed(run_dir: Path) -> bool:
    return load_approval(run_dir).state == "approved"
