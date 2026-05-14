from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException

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
from .artifacts import list_customers as list_customer_artifacts
from .artifacts import list_runs as list_run_artifacts
from .artifacts import load_run
from .artifacts import run_dir
from .models import AdminDecisionRequest
from .models import ApprovalRequest
from .notifications import build_approval_payload
from .notifications import send_approval_notification
from .static import mount_frontend


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

    @app.post("/api/customers/{customer}/runs/{run_id}/approve")
    def approve(customer: str, run_id: str, request: AdminDecisionRequest):
        try:
            approval = approve_run(run_dir(lab_root, customer, run_id), admin_by=request.actor, note=request.note)
            return dump_model(approval)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        except ApprovalGateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/reject")
    def reject(customer: str, run_id: str, request: AdminDecisionRequest):
        try:
            approval = reject_run(run_dir(lab_root, customer, run_id), admin_by=request.actor, note=request.note)
            return dump_model(approval)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/customers/{customer}/runs/{run_id}/publish")
    def publish(customer: str, run_id: str):
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
