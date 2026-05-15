import hmac
import os
import re
from pathlib import Path
from typing import Any
from typing import Optional

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi.responses import FileResponse

from profile_lab.commands import run_evaluate
from profile_lab.json_io import write_json
from profile_lab.paths import DEFAULT_LAB_ROOT
from profile_lab.paths import PRODUCTION_PROFILE_DIR
from profile_lab.publisher import PublishGateError
from profile_lab.publisher import publish_profile

from .approval import ApprovalGateError
from .approval import approve_run
from .approval import load_approval
from .approval import load_summary
from .approval import reject_run
from .approval import save_approval
from .approval import submit_run
from .artifacts import ArtifactNotFoundError
from .artifacts import dump_model
from .artifacts import read_json
from .artifacts import list_customers as list_customer_artifacts
from .artifacts import list_runs as list_run_artifacts
from .artifacts import load_run
from .artifacts import run_dir
from .models import AdminDecisionRequest
from .models import ApprovalRequest
from .models import CorrectionRequest
from .notifications import build_approval_payload
from .notifications import send_approval_notification
from .static import mount_frontend


ADMIN_TOKEN_ENV = "PO_PROFILE_LAB_ADMIN_TOKEN"
ADMIN_TOKEN_HEADER = "X-PO-Profile-Lab-Admin-Token"
FIELD_PART_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)])?$")


def require_admin_token(token: Optional[str]) -> None:
    expected_token = os.getenv(ADMIN_TOKEN_ENV)
    if not expected_token:
        raise HTTPException(status_code=503, detail=f"{ADMIN_TOKEN_ENV} is not configured")
    if not token or not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=403, detail="invalid admin token")


def parse_field_path(field: str) -> list[str | int]:
    parts: list[str | int] = []
    for raw_part in field.split("."):
        match = FIELD_PART_PATTERN.match(raw_part)
        if not match:
            raise ValueError(f"unsupported correction field path: {field}")
        parts.append(match.group(1))
        if match.group(2) is not None:
            parts.append(int(match.group(2)))
    return parts


def get_nested_value(payload: Any, field: str) -> Any:
    current = payload
    for part in parse_field_path(field):
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
        else:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
    return current


def coerce_correct_value(value: Any, current_value: Any) -> Any:
    if isinstance(current_value, bool):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes"}
        return bool(value)
    if isinstance(current_value, int) and not isinstance(current_value, bool):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if isinstance(current_value, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def set_nested_value(payload: dict, field: str, value: Any) -> None:
    parts = parse_field_path(field)
    current: Any = payload
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if isinstance(part, int):
            if not isinstance(current, list):
                raise ValueError(f"cannot index non-list field: {field}")
            while len(current) <= part:
                current.append({} if isinstance(next_part, str) else [])
            current = current[part]
        else:
            if not isinstance(current, dict):
                raise ValueError(f"cannot set nested field: {field}")
            current = current.setdefault(part, [] if isinstance(next_part, int) else {})

    last = parts[-1]
    if isinstance(last, int):
        if not isinstance(current, list):
            raise ValueError(f"cannot index non-list field: {field}")
        while len(current) <= last:
            current.append(None)
        current[last] = value
    elif isinstance(current, dict):
        current[last] = value
    else:
        raise ValueError(f"cannot set nested field: {field}")


def create_app(
    lab_root: Path = DEFAULT_LAB_ROOT,
    production_dir: Path = PRODUCTION_PROFILE_DIR,
) -> FastAPI:
    app = FastAPI(title="PO Profile Lab UI API")
    lab_root = Path(lab_root)
    production_dir = Path(production_dir)

    @app.get("/api/customers")
    def list_customers():
        return list_customer_artifacts(lab_root)

    @app.get("/api/customers/{customer}/runs")
    def list_runs(customer: str):
        return list_run_artifacts(lab_root, customer)

    @app.get("/api/customers/{customer}/runs/{run_id}")
    def get_run(customer: str, run_id: str):
        try:
            return load_run(lab_root, customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/submit")
    def submit(customer: str, run_id: str, request: ApprovalRequest):
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
            approval = submit_run(current_run_dir, submitted_by=request.actor, note=request.note)
            summary = load_summary(current_run_dir)
            review_url = f"/profile-lab/customers/{customer}/runs/{run_id}"
            payload = build_approval_payload(customer, run_id, summary, review_url)
            notification = send_approval_notification(payload)
            approval.notification_status = notification.status
            approval.notification_error = notification.error
            return dump_model(save_approval(current_run_dir, approval))
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        except ApprovalGateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/samples/{sample_key}/confirm-expected")
    def confirm_expected(customer: str, run_id: str, sample_key: str):
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
            merged_draft = read_json(current_run_dir / "adjudication" / f"{sample_key}.merged_draft.json")
            write_json(lab_root / "customers" / customer / "expected" / f"{sample_key}.json", merged_draft)
            run_evaluate(lab_root=lab_root, customer_key=customer, run_id=run_id)
            return load_run(lab_root, customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="sample not found") from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/samples/{sample_key}/corrections")
    def save_corrections(customer: str, run_id: str, sample_key: str, request: CorrectionRequest):
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
            merged_draft = read_json(current_run_dir / "adjudication" / f"{sample_key}.merged_draft.json")
            expected = read_json(lab_root / "customers" / customer / "expected" / f"{sample_key}.json", default=merged_draft)
            corrections_path = current_run_dir / "corrections" / f"{sample_key}.corrections.json"
            previous_corrections = read_json(corrections_path, default={}).get("corrections", [])
            recorded = list(previous_corrections)
            for correction in request.corrections:
                wrong_value = get_nested_value(merged_draft, correction.field)
                current_expected_value = get_nested_value(expected, correction.field)
                correct_value = coerce_correct_value(
                    correction.correct_value,
                    current_expected_value if current_expected_value is not None else wrong_value,
                )
                set_nested_value(expected, correction.field, correct_value)
                recorded.append(
                    {
                        "field": correction.field,
                        "wrong_value": wrong_value,
                        "correct_value": correct_value,
                        "note": correction.note,
                        "actor": request.actor,
                    }
                )

            write_json(lab_root / "customers" / customer / "expected" / f"{sample_key}.json", expected)
            write_json(
                corrections_path,
                {
                    "sample_key": sample_key,
                    "source_file": f"{sample_key}.pdf",
                    "actor": request.actor,
                    "corrections": recorded,
                },
            )
            run_evaluate(lab_root=lab_root, customer_key=customer, run_id=run_id)
            return load_run(lab_root, customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="sample not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/customers/{customer}/runs/{run_id}/samples/{sample_key}/pdf")
    def get_sample_pdf(customer: str, run_id: str, sample_key: str):
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        pdf_path = current_run_dir / "inputs" / f"{sample_key}.pdf"
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="pdf not found")
        return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)

    @app.post("/api/customers/{customer}/runs/{run_id}/approve")
    def approve(
        customer: str,
        run_id: str,
        request: AdminDecisionRequest,
        admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    ):
        require_admin_token(admin_token)
        try:
            approval = approve_run(run_dir(lab_root, customer, run_id), admin_by=request.actor, note=request.note)
            return dump_model(approval)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        except ApprovalGateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/reject")
    def reject(
        customer: str,
        run_id: str,
        request: AdminDecisionRequest,
        admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    ):
        require_admin_token(admin_token)
        try:
            approval = reject_run(run_dir(lab_root, customer, run_id), admin_by=request.actor, note=request.note)
            return dump_model(approval)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/publish")
    def publish(
        customer: str,
        run_id: str,
        admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    ):
        require_admin_token(admin_token)
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
            approval = load_approval(current_run_dir)
            if approval.state != "approved":
                raise ApprovalGateError("approval state must be approved before publish")

            profile_path = publish_profile(
                root=lab_root,
                customer_key=customer,
                run_id=run_id,
                production_dir=production_dir,
            )
            approval.state = "published"
            saved = save_approval(current_run_dir, approval)
            data = dump_model(saved)
            data["profile_path"] = str(profile_path)
            return data
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        except (ApprovalGateError, PublishGateError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    frontend_dist_dir = Path(__file__).parent / "frontend" / "dist"
    if (frontend_dist_dir / "index.html").exists():
        mount_frontend(app, frontend_dist_dir)

    return app
