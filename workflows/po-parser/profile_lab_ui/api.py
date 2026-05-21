import hmac
import os
import re
import shutil
from pathlib import Path
from typing import Any
from typing import Optional

from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import FileResponse

from profile_lab.commands import run_evaluate
from profile_lab.commands import run_draft
from profile_lab.commands import default_text_model
from profile_lab.commands import default_vision_model
from profile_lab.customer_assets import init_customer
from profile_lab.env_loader import load_profile_lab_env
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
from .models import CustomerCreateRequest
from .models import DraftRunRequest
from .models import ProfileMarkersRequest
from .notifications import build_approval_payload
from .notifications import send_approval_notification
from .static import mount_frontend


ADMIN_TOKEN_ENV = "PO_PROFILE_LAB_ADMIN_TOKEN"
ADMIN_TOKEN_HEADER = "X-PO-Profile-Lab-Admin-Token"
FIELD_PART_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)])?$")
SAFE_PDF_FILENAME_PATTERN = re.compile(r"^[^/\\]+\.pdf$", re.IGNORECASE)


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


def normalize_markers(markers: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for marker in markers:
        value = str(marker).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def validate_pdf_filename(filename: str) -> str:
    value = Path(filename).name.strip()
    if not SAFE_PDF_FILENAME_PATTERN.match(value):
        raise ValueError("sample filename must be a PDF file name")
    return value


def resolve_run_sample_pdf(current_run_dir: Path, sample_key: str) -> Path:
    manifest = read_json(current_run_dir / "manifest.json", default={})
    input_dir = current_run_dir / "inputs"
    for sample in manifest.get("samples", []):
        sample_name = Path(sample).name
        if Path(sample_name).stem == sample_key:
            return input_dir / sample_name
    return input_dir / f"{sample_key}.pdf"


def load_profile_status(lab_root: Path, production_dir: Path, customer: str) -> dict[str, Any]:
    lab_profile_path = lab_root / "customers" / customer / "profile.json"
    if not lab_profile_path.exists():
        raise ArtifactNotFoundError(str(lab_profile_path))

    lab_profile = read_json(lab_profile_path)
    production_profile_path = production_dir / f"{customer}.json"
    production_profile = read_json(production_profile_path, default={})
    markers = normalize_markers(
        production_profile.get("markers") or lab_profile.get("markers") or []
    )
    production_status = production_profile.get("status")
    runtime_ready = production_profile_path.exists() and production_status == "production" and bool(markers)

    return {
        "customer": customer,
        "profile_name": lab_profile.get("profile_name", customer),
        "markers": markers,
        "lab_status": lab_profile.get("status", "draft"),
        "production_status": production_status,
        "runtime_ready": runtime_ready,
        "lab_profile_path": str(lab_profile_path),
        "production_profile_path": str(production_profile_path),
        "production_exists": production_profile_path.exists(),
        "published_at": production_profile.get("published_at") or lab_profile.get("published_at"),
        "last_run_id": production_profile.get("last_run_id") or lab_profile.get("last_run_id"),
    }


def create_app(
    lab_root: Path = DEFAULT_LAB_ROOT,
    production_dir: Path = PRODUCTION_PROFILE_DIR,
) -> FastAPI:
    load_profile_lab_env()
    app = FastAPI(title="PO Profile Lab UI API")
    lab_root = Path(lab_root)
    production_dir = Path(production_dir)

    @app.get("/api/customers")
    def list_customers():
        return list_customer_artifacts(lab_root)

    @app.post("/api/customers")
    def create_customer(request: CustomerCreateRequest):
        customer_key = request.customer.strip()
        display_name = request.display_name.strip() or customer_key
        try:
            init_customer(
                root=lab_root,
                customer_key=customer_key,
                display_name=display_name,
            )
            return {
                "customer_key": customer_key,
                "display_name": display_name,
                "run_count": len(list_run_artifacts(lab_root, customer_key)),
                "sample_count": 0,
            }
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/customers/{customer}/runs")
    def list_runs(customer: str):
        return list_run_artifacts(lab_root, customer)

    @app.get("/api/customers/{customer}/samples")
    def list_samples(customer: str):
        samples_dir = lab_root / "customers" / customer / "samples"
        if not samples_dir.exists():
            return []
        return [
            {
                "filename": sample_path.name,
                "size": sample_path.stat().st_size,
            }
            for sample_path in sorted(samples_dir.iterdir())
            if sample_path.is_file() and sample_path.suffix.lower() == ".pdf"
        ]

    @app.post("/api/customers/{customer}/runs")
    def create_draft_run(customer: str, request: DraftRunRequest):
        try:
            run_draft(
                lab_root=lab_root,
                customer_key=customer,
                run_id=request.run_id.strip(),
                skip_render=request.skip_render,
                text_model=request.text_model or default_text_model(),
                vision_model=request.vision_model or default_vision_model(),
            )
            run_evaluate(lab_root=lab_root, customer_key=customer, run_id=request.run_id.strip())
            return load_run(lab_root, customer, request.run_id.strip())
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ArtifactNotFoundError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail="customer or sample not found") from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        pdf_path = resolve_run_sample_pdf(current_run_dir, sample_key)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="pdf not found")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_path.name,
            content_disposition_type="inline",
        )

    @app.get("/api/customers/{customer}/runs/{run_id}/samples/{sample_key}/page-image")
    def get_sample_page_image(customer: str, run_id: str, sample_key: str):
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        pdf_path = resolve_run_sample_pdf(current_run_dir, sample_key)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="pdf not found")

        image_path = current_run_dir / "pages" / f"{sample_key}.page-1.png"
        if not image_path.exists():
            try:
                import fitz

                image_path.parent.mkdir(parents=True, exist_ok=True)
                document = fitz.open(pdf_path)
                if document.page_count < 1:
                    raise ValueError("pdf has no pages")
                page = document.load_page(0)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
                pixmap.save(image_path)
                document.close()
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"failed to render pdf page: {exc}") from exc

        return FileResponse(image_path, media_type="image/png", filename=image_path.name)

    @app.put("/api/customers/{customer}/samples/{filename}")
    async def upload_sample_pdf(customer: str, filename: str, request: Request):
        try:
            safe_filename = validate_pdf_filename(filename)
            profile_path = lab_root / "customers" / customer / "profile.json"
            if not profile_path.exists():
                raise ArtifactNotFoundError(str(profile_path))
            body = await request.body()
            if not body:
                raise ValueError("sample PDF is empty")
            sample_path = lab_root / "customers" / customer / "samples" / safe_filename
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            sample_path.write_bytes(body)
            return {
                "customer": customer,
                "filename": safe_filename,
                "size": len(body),
            }
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="customer not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/customers/{customer}/profile")
    def get_profile(customer: str):
        try:
            return load_profile_status(lab_root, production_dir, customer)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc

    @app.put("/api/customers/{customer}/profile/markers")
    def update_profile_markers(
        customer: str,
        request: ProfileMarkersRequest,
        admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    ):
        require_admin_token(admin_token)
        try:
            markers = normalize_markers(request.markers)
            if not markers:
                raise ValueError("at least one marker is required")

            lab_profile_path = lab_root / "customers" / customer / "profile.json"
            if not lab_profile_path.exists():
                raise ArtifactNotFoundError(str(lab_profile_path))
            lab_profile = read_json(lab_profile_path)
            lab_profile["markers"] = markers
            write_json(lab_profile_path, lab_profile)

            production_profile_path = production_dir / f"{customer}.json"
            if production_profile_path.exists():
                production_profile = read_json(production_profile_path)
                production_profile["markers"] = markers
                write_json(production_profile_path, production_profile)

            return load_profile_status(lab_root, production_dir, customer)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="profile not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.delete("/api/customers/{customer}/runs/{run_id}")
    def delete_run(
        customer: str,
        run_id: str,
        admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
    ):
        require_admin_token(admin_token)
        try:
            current_run_dir = run_dir(lab_root, customer, run_id)
            shutil.rmtree(current_run_dir)
            return {"customer": customer, "run_id": run_id, "deleted": True}
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

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
