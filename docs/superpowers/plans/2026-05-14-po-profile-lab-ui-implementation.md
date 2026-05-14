# PO Profile Lab UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local/internal PO Profile Lab UI with a Review First workbench, file-backed approval workflow, notification webhook, admin approval gate, and publish integration.

**Architecture:** Add a focused FastAPI UI service under `workflows/po-parser/profile_lab_ui/` that wraps the existing `profile_lab` core and reads/writes run artifacts. Add a Vite React app under `workflows/po-parser/profile_lab_ui/frontend/` for the precision-console UI, with API calls routed to the FastAPI service. Keep state file-backed in `profile-lab/customers/<customer>/runs/<run-id>/` and enforce approval server-side before publishing.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, pytest, httpx/TestClient, Vite, React, TypeScript, CSS variables, lucide-react, Playwright for final smoke verification.

---

## File Structure

Create and modify these files:

- Create: `workflows/po-parser/profile_lab_ui/__init__.py`
- Create: `workflows/po-parser/profile_lab_ui/models.py`
- Create: `workflows/po-parser/profile_lab_ui/artifacts.py`
- Create: `workflows/po-parser/profile_lab_ui/approval.py`
- Create: `workflows/po-parser/profile_lab_ui/notifications.py`
- Create: `workflows/po-parser/profile_lab_ui/api.py`
- Create: `workflows/po-parser/profile_lab_ui/static.py`
- Create: `workflows/po-parser/profile_lab_ui/__main__.py`
- Create: `workflows/po-parser/tests/test_profile_lab_ui_approval.py`
- Create: `workflows/po-parser/tests/test_profile_lab_ui_api.py`
- Create: `workflows/po-parser/profile_lab_ui/frontend/package.json`
- Create: `workflows/po-parser/profile_lab_ui/frontend/index.html`
- Create: `workflows/po-parser/profile_lab_ui/frontend/tsconfig.json`
- Create: `workflows/po-parser/profile_lab_ui/frontend/vite.config.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/main.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/App.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/api.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/types.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/styles.css`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/RunTopBar.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/ScoreStrip.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/PdfEvidencePane.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/CandidateDiffPane.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/StandardJsonPane.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/AdjudicationPanel.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/ApprovalGate.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/Dashboard.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/components/AdminReview.tsx`
- Modify: `workflows/po-parser/tests/requirements.txt` if local test dependencies do not include FastAPI test dependencies.
- Modify: `workflows/po-parser/profile-lab/README.md` with UI run commands.
- Modify: `KNOWLEDGE.md` to list the UI service after implementation.
- Modify: root `package.json` only if adding repository-level convenience scripts is useful after the frontend package works locally.

Do not modify:

- `workflows/po-parser/workflow.json`
- existing n8n production flow behavior
- `workflows/po-parser/service/po_parser_service.py`

---

## Task 1: Approval Domain And File Store

**Files:**
- Create: `workflows/po-parser/profile_lab_ui/__init__.py`
- Create: `workflows/po-parser/profile_lab_ui/models.py`
- Create: `workflows/po-parser/profile_lab_ui/approval.py`
- Test: `workflows/po-parser/tests/test_profile_lab_ui_approval.py`

- [ ] **Step 1: Write approval state tests**

Create `workflows/po-parser/tests/test_profile_lab_ui_approval.py`:

```python
from pathlib import Path

import pytest

from profile_lab_ui.approval import (
    ApprovalGateError,
    approve_run,
    load_approval,
    publish_allowed,
    reject_run,
    submit_run,
)


def write_summary(run_dir: Path, publishable: bool = True, p0_pass: bool = True) -> None:
    evaluation_dir = run_dir / "evaluation"
    evaluation_dir.mkdir(parents=True)
    (evaluation_dir / "summary.json").write_text(
        (
            '{"publishable": %s, "sample_count": 1, "reports": ['
            '{"publishable": %s, "p0_pass": %s, "blocking_errors": [], '
            '"schema_pass": true, "scores": {"p1": 1.0, "business_rules": 1.0}}]}'
        )
        % (
            "true" if publishable else "false",
            "true" if publishable else "false",
            "true" if p0_pass else "false",
        ),
        encoding="utf-8",
    )


def test_submit_run_writes_submitted_state(tmp_path):
    run_dir = tmp_path / "profile-lab" / "customers" / "evytra" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    write_summary(run_dir)

    approval = submit_run(run_dir, submitted_by="business", note="ready")

    assert approval.state == "submitted"
    assert approval.submitted_by == "business"
    assert approval.note == "ready"
    assert (run_dir / "approval.json").exists()
    assert load_approval(run_dir).state == "submitted"


def test_submit_run_requires_evaluation_summary(tmp_path):
    run_dir = tmp_path / "profile-lab" / "customers" / "evytra" / "runs" / "run-1"
    run_dir.mkdir(parents=True)

    with pytest.raises(ApprovalGateError, match="evaluation summary is required"):
        submit_run(run_dir, submitted_by="business", note="")


def test_approve_run_requires_publishable_p0_pass(tmp_path):
    run_dir = tmp_path / "profile-lab" / "customers" / "evytra" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    write_summary(run_dir, publishable=True, p0_pass=False)
    submit_run(run_dir, submitted_by="business", note="")

    with pytest.raises(ApprovalGateError, match="P0 must pass"):
        approve_run(run_dir, admin_by="admin", note="checked")


def test_approve_and_reject_transitions(tmp_path):
    run_dir = tmp_path / "profile-lab" / "customers" / "evytra" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    write_summary(run_dir)
    submit_run(run_dir, submitted_by="business", note="ready")

    approved = approve_run(run_dir, admin_by="admin", note="ok")

    assert approved.state == "approved"
    assert approved.admin_by == "admin"
    assert publish_allowed(run_dir) is True

    rejected = reject_run(run_dir, admin_by="admin", note="change delivery date rule")

    assert rejected.state == "changes_requested"
    assert rejected.note == "change delivery date rule"
    assert publish_allowed(run_dir) is False
```

- [ ] **Step 2: Run approval tests to verify failure**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_approval.py -v
```

Expected: FAIL because `profile_lab_ui` does not exist.

- [ ] **Step 3: Implement approval models**

Create `workflows/po-parser/profile_lab_ui/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `workflows/po-parser/profile_lab_ui/models.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


ApprovalState = Literal[
    "draft",
    "generated",
    "evaluated",
    "submitted",
    "changes_requested",
    "approved",
    "published",
]


class ApprovalRecord(BaseModel):
    state: ApprovalState = "draft"
    submitted_by: str | None = None
    submitted_at: str | None = None
    admin_decision: str | None = None
    admin_by: str | None = None
    admin_at: str | None = None
    note: str = ""
    notification_status: str | None = None
    notification_error: str | None = None


class ApprovalRequest(BaseModel):
    actor: str = Field(default="business", min_length=1)
    note: str = ""


class AdminDecisionRequest(BaseModel):
    actor: str = Field(default="admin", min_length=1)
    note: str = ""
```

- [ ] **Step 4: Implement approval file store**

Create `workflows/po-parser/profile_lab_ui/approval.py`:

```python
import json
from datetime import datetime
from pathlib import Path

from .models import ApprovalRecord


class ApprovalGateError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def approval_path(run_dir: Path) -> Path:
    return run_dir / "approval.json"


def summary_path(run_dir: Path) -> Path:
    return run_dir / "evaluation" / "summary.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_approval(run_dir: Path) -> ApprovalRecord:
    path = approval_path(run_dir)
    if not path.exists():
        return ApprovalRecord()
    return ApprovalRecord(**read_json(path))


def save_approval(run_dir: Path, approval: ApprovalRecord) -> ApprovalRecord:
    if hasattr(approval, "model_dump"):
        payload = approval.model_dump()
    else:
        payload = approval.dict()
    write_json(approval_path(run_dir), payload)
    return approval


def load_summary(run_dir: Path) -> dict:
    path = summary_path(run_dir)
    if not path.exists():
        raise ApprovalGateError("evaluation summary is required before submission")
    return read_json(path)


def summary_is_publishable(summary: dict) -> bool:
    if summary.get("publishable") is not True:
        return False
    reports = summary.get("reports")
    if not isinstance(reports, list) or not reports:
        return False
    return all(report.get("publishable") is True for report in reports if isinstance(report, dict))


def summary_p0_passes(summary: dict) -> bool:
    reports = summary.get("reports")
    if not isinstance(reports, list) or not reports:
        return False
    return all(report.get("p0_pass") is True for report in reports if isinstance(report, dict))


def submit_run(run_dir: Path, submitted_by: str, note: str) -> ApprovalRecord:
    load_summary(run_dir)
    approval = load_approval(run_dir)
    approval.state = "submitted"
    approval.submitted_by = submitted_by
    approval.submitted_at = now_iso()
    approval.admin_decision = None
    approval.admin_by = None
    approval.admin_at = None
    approval.note = note
    return save_approval(run_dir, approval)


def approve_run(run_dir: Path, admin_by: str, note: str) -> ApprovalRecord:
    summary = load_summary(run_dir)
    if not summary_is_publishable(summary):
        raise ApprovalGateError("evaluation must be publishable before admin approval")
    if not summary_p0_passes(summary):
        raise ApprovalGateError("P0 must pass before admin approval")
    approval = load_approval(run_dir)
    if approval.state != "submitted":
        raise ApprovalGateError("run must be submitted before admin approval")
    approval.state = "approved"
    approval.admin_decision = "approved"
    approval.admin_by = admin_by
    approval.admin_at = now_iso()
    approval.note = note
    return save_approval(run_dir, approval)


def reject_run(run_dir: Path, admin_by: str, note: str) -> ApprovalRecord:
    approval = load_approval(run_dir)
    approval.state = "changes_requested"
    approval.admin_decision = "rejected"
    approval.admin_by = admin_by
    approval.admin_at = now_iso()
    approval.note = note
    return save_approval(run_dir, approval)


def publish_allowed(run_dir: Path) -> bool:
    return load_approval(run_dir).state == "approved"
```

- [ ] **Step 5: Run approval tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_approval.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/__init__.py workflows/po-parser/profile_lab_ui/models.py workflows/po-parser/profile_lab_ui/approval.py workflows/po-parser/tests/test_profile_lab_ui_approval.py
git commit -m "feat: add profile lab ui approval gate"
```

---

## Task 2: Artifact Repository And Read APIs

**Files:**
- Create: `workflows/po-parser/profile_lab_ui/artifacts.py`
- Create: `workflows/po-parser/profile_lab_ui/api.py`
- Test: `workflows/po-parser/tests/test_profile_lab_ui_api.py`

- [ ] **Step 1: Write API read tests**

Create `workflows/po-parser/tests/test_profile_lab_ui_api.py`:

```python
import json
from pathlib import Path

from fastapi.testclient import TestClient

from profile_lab_ui.api import create_app


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_run(root: Path) -> Path:
    run_dir = root / "customers" / "evytra" / "runs" / "run-1"
    write_json(root / "customers" / "evytra" / "customer.json", {"customer_key": "evytra", "display_name": "EVYTRA GmbH"})
    write_json(run_dir / "manifest.json", {"run_id": "run-1", "customer": "evytra", "samples": ["sample.pdf"], "created_at": "2026-05-14T18:30:00+08:00"})
    write_json(run_dir / "evaluation" / "summary.json", {"publishable": True, "sample_count": 1, "reports": []})
    write_json(run_dir / "approval.json", {"state": "submitted", "note": "ready"})
    write_json(run_dir / "candidates" / "text" / "sample.json", {"header": {"po_number": "PO-1"}, "items": []})
    write_json(run_dir / "candidates" / "vision" / "sample.json", {"header": {"po_number": "PO-1"}, "items": []})
    write_json(run_dir / "adjudication" / "sample.merged_draft.json", {"header": {"po_number": "PO-1"}, "items": []})
    return run_dir


def test_list_customers_and_runs(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    customers = client.get("/api/customers").json()
    runs = client.get("/api/customers/evytra/runs").json()

    assert customers == [{"customer_key": "evytra", "display_name": "EVYTRA GmbH", "run_count": 1}]
    assert runs[0]["run_id"] == "run-1"
    assert runs[0]["approval"]["state"] == "submitted"


def test_get_run_returns_artifacts(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    response = client.get("/api/customers/evytra/runs/run-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["run_id"] == "run-1"
    assert payload["evaluation"]["publishable"] is True
    assert payload["samples"][0]["sample_key"] == "sample"
    assert payload["samples"][0]["text_candidate"]["header"]["po_number"] == "PO-1"


def test_missing_run_returns_404(tmp_path):
    client = TestClient(create_app(lab_root=tmp_path / "profile-lab"))

    response = client.get("/api/customers/evytra/runs/missing")

    assert response.status_code == 404
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_api.py -v
```

Expected: FAIL because `profile_lab_ui.api` does not exist.

- [ ] **Step 3: Implement artifact loading**

Create `workflows/po-parser/profile_lab_ui/artifacts.py`:

```python
import json
from pathlib import Path
from typing import Any

from .approval import load_approval


class ArtifactNotFoundError(FileNotFoundError):
    pass


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise ArtifactNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def customer_dir(lab_root: Path, customer: str) -> Path:
    return lab_root / "customers" / customer


def run_dir(lab_root: Path, customer: str, run_id: str) -> Path:
    path = customer_dir(lab_root, customer) / "runs" / run_id
    if not path.exists():
        raise ArtifactNotFoundError(str(path))
    return path


def list_customers(lab_root: Path) -> list[dict]:
    customers_root = lab_root / "customers"
    if not customers_root.exists():
        return []
    rows = []
    for path in sorted(customers_root.iterdir()):
        if not path.is_dir():
            continue
        customer = read_json(path / "customer.json", {"customer_key": path.name, "display_name": path.name})
        run_count = len([child for child in (path / "runs").glob("*") if child.is_dir()]) if (path / "runs").exists() else 0
        rows.append({
            "customer_key": customer.get("customer_key", path.name),
            "display_name": customer.get("display_name", path.name),
            "run_count": run_count,
        })
    return rows


def list_runs(lab_root: Path, customer: str) -> list[dict]:
    runs_root = customer_dir(lab_root, customer) / "runs"
    if not runs_root.exists():
        return []
    rows = []
    for path in sorted(runs_root.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        manifest = read_json(path / "manifest.json", {"run_id": path.name, "customer": customer, "samples": []})
        rows.append({
            "run_id": manifest.get("run_id", path.name),
            "customer": customer,
            "created_at": manifest.get("created_at"),
            "sample_count": len(manifest.get("samples", [])),
            "evaluation": read_json(path / "evaluation" / "summary.json", {}),
            "approval": load_approval(path).model_dump() if hasattr(load_approval(path), "model_dump") else load_approval(path).dict(),
        })
    return rows


def sample_key_from_name(name: str) -> str:
    return Path(name).stem


def load_run(lab_root: Path, customer: str, run_id: str) -> dict:
    path = run_dir(lab_root, customer, run_id)
    manifest = read_json(path / "manifest.json")
    samples = []
    for sample_name in manifest.get("samples", []):
        sample_key = sample_key_from_name(sample_name)
        samples.append({
            "sample_key": sample_key,
            "source_file": sample_name,
            "text_candidate": read_json(path / "candidates" / "text" / f"{sample_key}.json", {}),
            "vision_candidate": read_json(path / "candidates" / "vision" / f"{sample_key}.json", {}),
            "merged_draft": read_json(path / "adjudication" / f"{sample_key}.merged_draft.json", {}),
            "report": read_json(path / "evaluation" / f"{sample_key}.report.json", {}),
        })
    approval = load_approval(path)
    return {
        "manifest": manifest,
        "evaluation": read_json(path / "evaluation" / "summary.json", {}),
        "approval": approval.model_dump() if hasattr(approval, "model_dump") else approval.dict(),
        "samples": samples,
    }
```

- [ ] **Step 4: Implement FastAPI read routes**

Create `workflows/po-parser/profile_lab_ui/api.py`:

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException

from profile_lab.paths import DEFAULT_LAB_ROOT

from .artifacts import ArtifactNotFoundError, list_customers, list_runs, load_run


def create_app(lab_root: Path = DEFAULT_LAB_ROOT) -> FastAPI:
    app = FastAPI(title="PO Profile Lab UI")
    app.state.lab_root = Path(lab_root)

    @app.get("/api/customers")
    def api_list_customers() -> list[dict]:
        return list_customers(app.state.lab_root)

    @app.get("/api/customers/{customer}/runs")
    def api_list_runs(customer: str) -> list[dict]:
        return list_runs(app.state.lab_root, customer)

    @app.get("/api/customers/{customer}/runs/{run_id}")
    def api_get_run(customer: str, run_id: str) -> dict:
        try:
            return load_run(app.state.lab_root, customer, run_id)
        except ArtifactNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return app
```

- [ ] **Step 5: Run API read tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/artifacts.py workflows/po-parser/profile_lab_ui/api.py workflows/po-parser/tests/test_profile_lab_ui_api.py
git commit -m "feat: expose profile lab ui read api"
```

---

## Task 3: Actions, Notification, And Publish Gate

**Files:**
- Create: `workflows/po-parser/profile_lab_ui/notifications.py`
- Modify: `workflows/po-parser/profile_lab_ui/api.py`
- Test: `workflows/po-parser/tests/test_profile_lab_ui_api.py`

- [ ] **Step 1: Add action API tests**

Append to `workflows/po-parser/tests/test_profile_lab_ui_api.py`:

```python
def test_submit_approve_reject_actions(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    submitted = client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})
    approved = client.post("/api/customers/evytra/runs/run-1/approve", json={"actor": "admin", "note": "ok"})
    rejected = client.post("/api/customers/evytra/runs/run-1/reject", json={"actor": "admin", "note": "fix date"})

    assert submitted.status_code == 200
    assert submitted.json()["state"] == "submitted"
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert rejected.status_code == 200
    assert rejected.json()["state"] == "changes_requested"


def test_publish_requires_admin_approval(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    write_json(lab_root / "customers" / "evytra" / "profile.json", {"profile_name": "evytra", "version": "0.1.0"})
    client = TestClient(create_app(lab_root=lab_root, production_dir=tmp_path / "profiles"))

    blocked = client.post("/api/customers/evytra/runs/run-1/publish")
    client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})
    client.post("/api/customers/evytra/runs/run-1/approve", json={"actor": "admin", "note": "ok"})
    published = client.post("/api/customers/evytra/runs/run-1/publish")

    assert blocked.status_code == 409
    assert published.status_code == 200
    assert published.json()["state"] == "published"
    assert (tmp_path / "profiles" / "evytra.json").exists()
```

- [ ] **Step 2: Run action tests to verify failure**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_api.py::test_submit_approve_reject_actions tests/test_profile_lab_ui_api.py::test_publish_requires_admin_approval -v
```

Expected: FAIL because routes are missing.

- [ ] **Step 3: Implement notification adapter**

Create `workflows/po-parser/profile_lab_ui/notifications.py`:

```python
import os
from dataclasses import dataclass

import httpx


@dataclass
class NotificationResult:
    status: str
    error: str | None = None


def build_approval_payload(customer: str, run_id: str, summary: dict, review_url: str) -> dict:
    return {
        "event": "po_profile_lab.approval_requested",
        "customer": customer,
        "run_id": run_id,
        "overall_score": summary.get("overall_score"),
        "publishable": summary.get("publishable") is True,
        "review_url": review_url,
    }


def send_approval_notification(payload: dict, webhook_url: str | None = None) -> NotificationResult:
    url = webhook_url or os.getenv("PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL")
    if not url:
        return NotificationResult(status="skipped", error="PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL is not configured")
    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
    except Exception as error:
        return NotificationResult(status="failed", error=str(error))
    return NotificationResult(status="sent")
```

- [ ] **Step 4: Add action routes**

Modify `workflows/po-parser/profile_lab_ui/api.py` so `create_app` accepts `production_dir` and includes action routes:

```python
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from profile_lab.paths import DEFAULT_LAB_ROOT, PRODUCTION_PROFILE_DIR
from profile_lab.publisher import PublishGateError, publish_profile

from .approval import ApprovalGateError, approve_run, load_approval, load_summary, reject_run, save_approval, submit_run
from .artifacts import ArtifactNotFoundError, list_customers, list_runs, load_run, run_dir
from .models import AdminDecisionRequest, ApprovalRequest
from .notifications import build_approval_payload, send_approval_notification


def approval_payload(approval) -> dict:
    return approval.model_dump() if hasattr(approval, "model_dump") else approval.dict()


def create_app(
    lab_root: Path = DEFAULT_LAB_ROOT,
    production_dir: Path = PRODUCTION_PROFILE_DIR,
) -> FastAPI:
    app = FastAPI(title="PO Profile Lab UI")
    app.state.lab_root = Path(lab_root)
    app.state.production_dir = Path(production_dir)

    @app.get("/api/customers")
    def api_list_customers() -> list[dict]:
        return list_customers(app.state.lab_root)

    @app.get("/api/customers/{customer}/runs")
    def api_list_runs(customer: str) -> list[dict]:
        return list_runs(app.state.lab_root, customer)

    @app.get("/api/customers/{customer}/runs/{run_id}")
    def api_get_run(customer: str, run_id: str) -> dict:
        try:
            return load_run(app.state.lab_root, customer, run_id)
        except ArtifactNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/customers/{customer}/runs/{run_id}/submit")
    def api_submit_run(customer: str, run_id: str, body: ApprovalRequest, request: Request) -> dict:
        try:
            path = run_dir(app.state.lab_root, customer, run_id)
            approval = submit_run(path, submitted_by=body.actor, note=body.note)
            summary = load_summary(path)
            review_url = str(request.url_for("api_get_run", customer=customer, run_id=run_id))
            result = send_approval_notification(build_approval_payload(customer, run_id, summary, review_url))
            approval.notification_status = result.status
            approval.notification_error = result.error
            save_approval(path, approval)
            return approval_payload(approval)
        except (ArtifactNotFoundError, ApprovalGateError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/customers/{customer}/runs/{run_id}/approve")
    def api_approve_run(customer: str, run_id: str, body: AdminDecisionRequest) -> dict:
        try:
            approval = approve_run(run_dir(app.state.lab_root, customer, run_id), admin_by=body.actor, note=body.note)
            return approval_payload(approval)
        except (ArtifactNotFoundError, ApprovalGateError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/customers/{customer}/runs/{run_id}/reject")
    def api_reject_run(customer: str, run_id: str, body: AdminDecisionRequest) -> dict:
        try:
            approval = reject_run(run_dir(app.state.lab_root, customer, run_id), admin_by=body.actor, note=body.note)
            return approval_payload(approval)
        except ArtifactNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/customers/{customer}/runs/{run_id}/publish")
    def api_publish_run(customer: str, run_id: str) -> dict:
        path = run_dir(app.state.lab_root, customer, run_id)
        approval = approval_payload(load_approval(path))
        if approval.get("state") != "approved":
            raise HTTPException(status_code=409, detail="admin approval is required before publishing")
        try:
            output_path = publish_profile(app.state.lab_root, customer, run_id, app.state.production_dir)
        except PublishGateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        updated = load_approval(path)
        updated.state = "published"
        save_approval(path, updated)
        payload = approval_payload(updated)
        payload["profile_path"] = str(output_path)
        return payload

    return app
```

- [ ] **Step 5: Run action tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_api.py tests/test_profile_lab_ui_approval.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/notifications.py workflows/po-parser/profile_lab_ui/api.py workflows/po-parser/tests/test_profile_lab_ui_api.py
git commit -m "feat: add profile lab ui approval actions"
```

---

## Task 4: Frontend Scaffold And API Client

**Files:**
- Create: `workflows/po-parser/profile_lab_ui/frontend/package.json`
- Create: `workflows/po-parser/profile_lab_ui/frontend/index.html`
- Create: `workflows/po-parser/profile_lab_ui/frontend/tsconfig.json`
- Create: `workflows/po-parser/profile_lab_ui/frontend/vite.config.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/types.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/api.ts`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/main.tsx`
- Create: `workflows/po-parser/profile_lab_ui/frontend/src/App.tsx`

- [ ] **Step 1: Create frontend package files**

Create `workflows/po-parser/profile_lab_ui/frontend/package.json`:

```json
{
  "name": "po-profile-lab-ui",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5174",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview --host 0.0.0.0 --port 4174"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.11",
    "typescript": "^5.6.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

Create `workflows/po-parser/profile_lab_ui/frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PO Profile Lab</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `workflows/po-parser/profile_lab_ui/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `workflows/po-parser/profile_lab_ui/frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8768"
    }
  }
});
```

- [ ] **Step 2: Create TypeScript contracts**

Create `workflows/po-parser/profile_lab_ui/frontend/src/types.ts`:

```ts
export type ApprovalState =
  | "draft"
  | "generated"
  | "evaluated"
  | "submitted"
  | "changes_requested"
  | "approved"
  | "published";

export interface ApprovalRecord {
  state: ApprovalState;
  submitted_by?: string | null;
  submitted_at?: string | null;
  admin_decision?: string | null;
  admin_by?: string | null;
  admin_at?: string | null;
  note: string;
  notification_status?: string | null;
  notification_error?: string | null;
}

export interface CustomerSummary {
  customer_key: string;
  display_name: string;
  run_count: number;
}

export interface RunSummary {
  run_id: string;
  customer: string;
  created_at?: string | null;
  sample_count: number;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
}

export interface EvaluationSummary {
  publishable?: boolean;
  sample_count?: number;
  reports?: EvaluationReport[];
}

export interface EvaluationReport {
  sample_key?: string;
  publishable?: boolean;
  p0_pass?: boolean;
  schema_pass?: boolean;
  blocking_errors?: FieldIssue[];
  scores?: Record<string, number>;
}

export interface FieldIssue {
  field: string;
  expected: unknown;
  actual: unknown;
  reason: string;
}

export interface RunSample {
  sample_key: string;
  source_file: string;
  text_candidate: Record<string, unknown>;
  vision_candidate: Record<string, unknown>;
  merged_draft: Record<string, unknown>;
  report: EvaluationReport;
}

export interface RunDetail {
  manifest: Record<string, unknown>;
  evaluation: EvaluationSummary;
  approval: ApprovalRecord;
  samples: RunSample[];
}
```

- [ ] **Step 3: Create API client**

Create `workflows/po-parser/profile_lab_ui/frontend/src/api.ts`:

```ts
import type { ApprovalRecord, CustomerSummary, RunDetail, RunSummary } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  customers: () => request<CustomerSummary[]>("/api/customers"),
  runs: (customer: string) => request<RunSummary[]>(`/api/customers/${customer}/runs`),
  run: (customer: string, runId: string) => request<RunDetail>(`/api/customers/${customer}/runs/${runId}`),
  submit: (customer: string, runId: string, actor: string, note: string) =>
    request<ApprovalRecord>(`/api/customers/${customer}/runs/${runId}/submit`, {
      method: "POST",
      body: JSON.stringify({ actor, note }),
    }),
  approve: (customer: string, runId: string, actor: string, note: string) =>
    request<ApprovalRecord>(`/api/customers/${customer}/runs/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify({ actor, note }),
    }),
  reject: (customer: string, runId: string, actor: string, note: string) =>
    request<ApprovalRecord>(`/api/customers/${customer}/runs/${runId}/reject`, {
      method: "POST",
      body: JSON.stringify({ actor, note }),
    }),
  publish: (customer: string, runId: string) =>
    request<ApprovalRecord>(`/api/customers/${customer}/runs/${runId}/publish`, { method: "POST" }),
};
```

- [ ] **Step 4: Create minimal app shell**

Create `workflows/po-parser/profile_lab_ui/frontend/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `workflows/po-parser/profile_lab_ui/frontend/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";

import { api } from "./api";
import type { CustomerSummary } from "./types";

export default function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .customers()
      .then(setCustomers)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="app-shell">
      <header className="topline">
        <div>
          <span className="eyebrow">PO PROFILE LAB</span>
          <h1>Review Workbench</h1>
        </div>
        <div className="status-pill">{loading ? "Loading" : `${customers.length} customers`}</div>
      </header>
      {error ? <section className="panel danger">{error}</section> : null}
      {!error && loading ? <section className="panel">Loading customer assets...</section> : null}
      {!error && !loading ? (
        <section className="panel">
          <h2>Customer Assets</h2>
          <p>{customers.length === 0 ? "No customer assets found." : "API connected."}</p>
        </section>
      ) : null}
    </main>
  );
}
```

Create `workflows/po-parser/profile_lab_ui/frontend/src/styles.css`:

```css
:root {
  color: #edfffc;
  background: #051013;
  font-family: "Aptos", "Segoe UI", sans-serif;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% 8%, rgba(119, 247, 232, 0.22), transparent 30%),
    linear-gradient(135deg, #051013, #07171b 54%, #10262a);
}

.app-shell {
  min-height: 100vh;
  padding: 28px;
}

.topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  color: #77f7e8;
  font-size: 12px;
  letter-spacing: 0.14em;
}

h1 {
  margin: 6px 0 0;
  font-size: 28px;
  letter-spacing: 0;
}

.status-pill {
  border: 1px solid rgba(119, 247, 232, 0.26);
  border-radius: 999px;
  padding: 8px 12px;
  color: #77f7e8;
  background: rgba(119, 247, 232, 0.1);
}

.panel {
  margin-top: 20px;
  border: 1px solid rgba(119, 247, 232, 0.18);
  border-radius: 16px;
  padding: 18px;
  background: rgba(8, 23, 28, 0.78);
}

.panel.danger {
  border-color: rgba(255, 107, 117, 0.34);
  color: #ffb8bd;
}
```

- [ ] **Step 5: Install and build**

Run:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm install
npm run build
```

Expected: Vite build succeeds and creates `dist/`.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/frontend package-lock.json
git commit -m "feat: scaffold po profile lab frontend"
```

---

## Task 5: Review Workbench UI

**Files:**
- Create/modify frontend components listed in File Structure
- Modify: `workflows/po-parser/profile_lab_ui/frontend/src/styles.css`
- Modify: `workflows/po-parser/profile_lab_ui/frontend/src/App.tsx`

- [ ] **Step 1: Implement precision-console styles**

Create CSS variables for `--bg`, `--panel`, `--panel-strong`, `--cyan`, `--amber`, `--red`, `--line`, and stable panel dimensions. Include keyframes for `scan-in` and `status-pulse`; use them only on active run/gate states.

- [ ] **Step 2: Implement workbench components**

Implement:

- `RunTopBar`: customer, run id, state, and actions.
- `ScoreStrip`: overall, P0, rows, business rules, gate state.
- `PdfEvidencePane`: rendered evidence area; if no page image is available, show a structured empty state with sample filename.
- `CandidateDiffPane`: list field conflicts from report blocking errors and P1 quality issues.
- `StandardJsonPane`: tree view from merged draft with status badges.
- `AdjudicationPanel`: agent recommendations derived from blocking errors, notification state, and action buttons.
- `ApprovalGate`: submit, approve, reject, publish buttons with disabled states.

- [ ] **Step 3: Wire first run selection**

In `App.tsx`, load customers, select the first customer with runs, then load the latest run. Keep this simple so MVP opens directly into the workbench.

- [ ] **Step 4: Build frontend**

Run:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/frontend/src
git commit -m "feat: build po profile lab review workbench"
```

---

## Task 6: Dashboard And Admin Review Views

**Files:**
- Modify: `workflows/po-parser/profile_lab_ui/frontend/src/App.tsx`
- Create/modify: `Dashboard.tsx`
- Create/modify: `AdminReview.tsx`
- Modify: `styles.css`

- [ ] **Step 1: Add in-app view switch**

Add a three-tab navigation: `Workbench`, `Dashboard`, `Admin Review`. Use local React state for routing in MVP.

- [ ] **Step 2: Implement Dashboard**

Show:

- customer count;
- total run count;
- submitted count;
- published count;
- latest run list;
- customers with blocking P0 issues.

- [ ] **Step 3: Implement Admin Review**

Show all runs where `approval.state === "submitted"` with score, sample count, notification status, and buttons to open the run.

- [ ] **Step 4: Build frontend**

Run:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/frontend/src
git commit -m "feat: add profile lab dashboard and admin review"
```

---

## Task 7: Serve UI From FastAPI And Document Run Commands

**Files:**
- Create: `workflows/po-parser/profile_lab_ui/static.py`
- Create: `workflows/po-parser/profile_lab_ui/__main__.py`
- Modify: `workflows/po-parser/profile_lab_ui/api.py`
- Modify: `workflows/po-parser/profile-lab/README.md`
- Modify: `KNOWLEDGE.md`

- [ ] **Step 1: Add static serving helper**

Create `static.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_index() -> FileResponse:
        return FileResponse(dist_dir / "index.html")

    @app.get("/{path:path}")
    def serve_spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            return FileResponse(dist_dir / "index.html", status_code=404)
        return FileResponse(dist_dir / "index.html")
```

- [ ] **Step 2: Add runnable module**

Create `__main__.py`:

```python
import uvicorn

from .api import create_app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="0.0.0.0", port=8768)
```

- [ ] **Step 3: Mount frontend when dist exists**

Modify `create_app` to call `mount_frontend(app, Path(__file__).parent / "frontend" / "dist")` if `index.html` exists.

- [ ] **Step 4: Update docs**

Add commands to `workflows/po-parser/profile-lab/README.md`:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm install
npm run build

cd workflows/po-parser
python -m profile_lab_ui
```

Document that the UI runs on `http://localhost:8768` and approval notifications use `PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL`.

- [ ] **Step 5: Run backend tests and frontend build**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_ui_api.py tests/test_profile_lab_ui_approval.py -v

cd profile_lab_ui/frontend
npm run build
```

Expected: tests PASS and frontend build PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab_ui/static.py workflows/po-parser/profile_lab_ui/__main__.py workflows/po-parser/profile_lab_ui/api.py workflows/po-parser/profile-lab/README.md KNOWLEDGE.md
git commit -m "feat: serve profile lab ui"
```

---

## Task 8: End-To-End Verification

**Files:**
- Modify docs only if verification reveals command mismatches.

- [ ] **Step 1: Run existing Profile Lab tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py tests/test_profile_lab_evaluator.py tests/test_profile_lab_publisher.py tests/test_profile_lab_ui_api.py tests/test_profile_lab_ui_approval.py -v
```

Expected: PASS.

- [ ] **Step 2: Build frontend**

Run:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Start local UI service**

Run:

```bash
cd workflows/po-parser
python -m profile_lab_ui
```

Expected: service listens on `http://localhost:8768`.

- [ ] **Step 4: Browser smoke test**

Open `http://localhost:8768` with Playwright or the in-app browser. Verify:

- Dashboard tab renders.
- Workbench tab renders with score strip and three review panes.
- Admin Review tab renders.
- Submit action records `approval.state = "submitted"`.
- Approve action records `approval.state = "approved"`.
- Publish action is blocked before approval and succeeds after approval with publishable evaluation.

- [ ] **Step 5: Commit verification docs if changed**

If command corrections were needed:

```bash
git add workflows/po-parser/profile-lab/README.md KNOWLEDGE.md
git commit -m "docs: update profile lab ui verification notes"
```

If no docs changed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Review First workbench is covered by Tasks 4 and 5.
- Dashboard and admin review are covered by Task 6.
- File-backed approval workflow is covered by Tasks 1 and 3.
- Notification webhook is covered by Task 3.
- Server-side publish gate is covered by Task 3.
- Local/internal service boundary is covered by Tasks 2, 7, and 8.

Execution note:

- Run Task 1 through Task 3 before frontend work. The UI should consume real API shapes, not invented mock shapes.
- Keep visual polish in Task 5 focused on the approved precision-console direction.
- Do not introduce login or role infrastructure in this MVP; use actor fields in action payloads for audit metadata.
