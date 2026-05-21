import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from profile_lab.env_loader import ENV_FILE_ENV
from profile_lab.env_loader import SKIP_ENV_FILE_ENV
from profile_lab_ui.api import ADMIN_TOKEN_ENV
from profile_lab_ui.api import ADMIN_TOKEN_HEADER
from profile_lab_ui.api import create_app
from profile_lab_ui.artifacts import ArtifactNotFoundError
from profile_lab_ui.artifacts import run_dir
from profile_lab_ui.notifications import build_approval_payload


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_run(root: Path) -> Path:
    run_dir = root / "customers" / "evytra" / "runs" / "run-1"
    write_json(root / "customers" / "evytra" / "customer.json", {"customer_key": "evytra", "display_name": "EVYTRA GmbH"})
    write_json(run_dir / "manifest.json", {"run_id": "run-1", "customer": "evytra", "samples": ["sample.pdf"], "created_at": "2026-05-14T18:30:00+08:00"})
    write_json(
        run_dir / "evaluation" / "summary.json",
        {
            "publishable": True,
            "sample_count": 1,
            "reports": [
                {
                    "publishable": True,
                    "schema_pass": True,
                    "p0_pass": True,
                    "blocking_errors": [],
                    "scores": {"p1": 1.0, "business_rules": 1.0},
                }
            ],
        },
    )
    write_json(run_dir / "approval.json", {"state": "submitted", "note": "ready"})
    write_json(run_dir / "candidates" / "text" / "sample.json", {"header": {"po_number": "PO-1"}, "items": []})
    write_json(run_dir / "candidates" / "vision" / "sample.json", {"header": {"po_number": "PO-1"}, "items": []})
    write_json(run_dir / "adjudication" / "sample.merged_draft.json", {"header": {"po_number": "PO-1"}, "items": []})
    return run_dir


def create_profile(root: Path, markers: list[str] | None = None) -> None:
    write_json(
        root / "customers" / "evytra" / "profile.json",
        {
            "profile_name": "evytra",
            "version": "0.1.0",
            "markers": markers or [],
        },
    )


def admin_headers(token: str = "secret-admin-token") -> dict:
    return {ADMIN_TOKEN_HEADER: token}


def test_list_customers_and_runs(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    newer_run = lab_root / "customers" / "evytra" / "runs" / "run-2"
    write_json(newer_run / "manifest.json", {"run_id": "run-2", "customer": "evytra", "samples": [], "created_at": "2026-05-15T18:30:00+08:00"})
    write_json(newer_run / "evaluation" / "summary.json", {"publishable": True, "sample_count": 0, "reports": []})
    client = TestClient(create_app(lab_root=lab_root))

    customers = client.get("/api/customers").json()
    runs = client.get("/api/customers/evytra/runs").json()

    assert customers == [{"customer_key": "evytra", "display_name": "EVYTRA GmbH", "run_count": 2, "sample_count": 0}]
    assert [run["run_id"] for run in runs] == ["run-2", "run-1"]
    assert runs[1]["approval"]["state"] == "submitted"


def test_create_customer_and_upload_sample_pdf(tmp_path):
    lab_root = tmp_path / "profile-lab"
    client = TestClient(create_app(lab_root=lab_root))

    created = client.post("/api/customers", json={"customer": "acme", "display_name": "ACME Corp"})
    uploaded = client.put(
        "/api/customers/acme/samples/order-1.pdf",
        content=b"%PDF-1.4\nsample",
        headers={"content-type": "application/pdf"},
    )

    assert created.status_code == 200
    assert created.json()["customer_key"] == "acme"
    assert created.json()["sample_count"] == 0
    assert uploaded.status_code == 200
    assert uploaded.json()["filename"] == "order-1.pdf"
    assert (lab_root / "customers" / "acme" / "samples" / "order-1.pdf").read_bytes().startswith(b"%PDF")

    samples = client.get("/api/customers/acme/samples")
    customers = client.get("/api/customers").json()
    assert samples.status_code == 200
    assert samples.json()[0]["filename"] == "order-1.pdf"
    assert customers[0]["sample_count"] == 1


def test_create_draft_run_from_ui_invokes_draft_and_evaluate(tmp_path, monkeypatch):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    calls = {}

    def fake_run_draft(lab_root, customer_key, run_id, skip_render, text_model=None, vision_model=None):
        calls["draft"] = {
            "customer_key": customer_key,
            "run_id": run_id,
            "skip_render": skip_render,
            "text_model": text_model,
            "vision_model": vision_model,
        }
        new_run = lab_root / "customers" / customer_key / "runs" / run_id
        write_json(new_run / "manifest.json", {"run_id": run_id, "customer": customer_key, "samples": ["sample.pdf"], "created_at": "2026-05-20T12:00:00+08:00"})
        write_json(new_run / "candidates" / "text" / "sample.json", {"header": {}, "items": []})
        write_json(new_run / "candidates" / "vision" / "sample.json", {"header": {}, "items": []})
        write_json(new_run / "adjudication" / "sample.merged_draft.json", {"header": {}, "items": []})
        return new_run

    def fake_run_evaluate(lab_root, customer_key, run_id):
        calls["evaluate"] = {"customer_key": customer_key, "run_id": run_id}
        evaluation_dir = lab_root / "customers" / customer_key / "runs" / run_id / "evaluation"
        write_json(evaluation_dir / "summary.json", {"publishable": False, "sample_count": 1, "reports": [{"sample_key": "sample", "publishable": False}]})
        write_json(evaluation_dir / "sample.report.json", {"sample_key": "sample", "publishable": False})
        return evaluation_dir

    monkeypatch.setattr("profile_lab_ui.api.run_draft", fake_run_draft)
    monkeypatch.setattr("profile_lab_ui.api.run_evaluate", fake_run_evaluate)
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post(
        "/api/customers/evytra/runs",
        json={"run_id": "ui-run-1", "text_model": "qwen3.5:27b", "vision_model": "qwen3.5:27b"},
    )

    assert response.status_code == 200
    assert calls["draft"]["customer_key"] == "evytra"
    assert calls["draft"]["text_model"] == "qwen3.5:27b"
    assert calls["evaluate"]["run_id"] == "ui-run-1"
    assert response.json()["manifest"]["run_id"] == "ui-run-1"


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
    assert payload["samples"][0]["source_file"] == "sample.pdf"
    assert payload["samples"][0]["pdf_url"] == "/api/customers/evytra/runs/run-1/samples/sample/pdf"
    assert payload["samples"][0]["text_candidate"]["header"]["po_number"] == "PO-1"


def test_missing_run_returns_404(tmp_path):
    client = TestClient(create_app(lab_root=tmp_path / "profile-lab"))

    response = client.get("/api/customers/evytra/runs/missing")

    assert response.status_code == 404


def test_run_dir_raises_for_missing_path(tmp_path):
    lab_root = tmp_path / "profile-lab"

    with pytest.raises(ArtifactNotFoundError):
        run_dir(lab_root, "evytra", "missing")


def test_submit_approve_reject_actions(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    submitted = client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})
    approved = client.post("/api/customers/evytra/runs/run-1/approve", headers=admin_headers(), json={"actor": "admin", "note": "ok"})
    rejected = client.post("/api/customers/evytra/runs/run-1/reject", headers=admin_headers(), json={"actor": "admin", "note": "fix date"})

    assert submitted.status_code == 200
    assert submitted.json()["state"] == "submitted"
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert rejected.status_code == 200
    assert rejected.json()["state"] == "changes_requested"


def test_admin_actions_require_admin_token(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    missing = client.post("/api/customers/evytra/runs/run-1/approve", json={"actor": "admin", "note": "ok"})
    wrong = client.post(
        "/api/customers/evytra/runs/run-1/approve",
        headers=admin_headers("wrong-token"),
        json={"actor": "admin", "note": "ok"},
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert (lab_root / "customers" / "evytra" / "runs" / "run-1" / "approval.json").read_text(encoding="utf-8").find('"approved"') == -1


def test_admin_actions_block_when_token_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv(ADMIN_TOKEN_ENV, raising=False)
    monkeypatch.setenv(SKIP_ENV_FILE_ENV, "1")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post("/api/customers/evytra/runs/run-1/approve", headers=admin_headers(), json={"actor": "admin", "note": "ok"})

    assert response.status_code == 503
    assert ADMIN_TOKEN_ENV in response.json()["detail"]


def test_admin_token_loads_from_profile_lab_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text(f"{ADMIN_TOKEN_ENV}=secret-admin-token\n", encoding="utf-8")
    monkeypatch.setenv(ENV_FILE_ENV, str(env_file))
    monkeypatch.delenv(SKIP_ENV_FILE_ENV, raising=False)
    monkeypatch.delenv(ADMIN_TOKEN_ENV, raising=False)
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post("/api/customers/evytra/runs/run-1/approve", headers=admin_headers(), json={"actor": "admin", "note": "ok"})

    assert response.status_code == 200
    assert response.json()["state"] == "approved"


def test_publish_requires_admin_approval(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    create_profile(lab_root, markers=["EVYTRA GmbH"])
    client = TestClient(create_app(lab_root=lab_root, production_dir=tmp_path / "profiles"))

    blocked = client.post("/api/customers/evytra/runs/run-1/publish", headers=admin_headers())
    client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})
    client.post("/api/customers/evytra/runs/run-1/approve", headers=admin_headers(), json={"actor": "admin", "note": "ok"})
    published = client.post("/api/customers/evytra/runs/run-1/publish", headers=admin_headers())

    assert blocked.status_code == 409
    assert published.status_code == 200
    assert published.json()["state"] == "published"
    assert (tmp_path / "profiles" / "evytra.json").exists()


def test_profile_endpoint_returns_lab_and_production_status(tmp_path):
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    create_profile(lab_root, markers=["EVYTRA GmbH"])
    production_dir = tmp_path / "profiles"
    write_json(
        production_dir / "evytra.json",
        {
            "profile_name": "evytra",
            "status": "production",
            "markers": ["EVYTRA GmbH"],
            "published_at": "2026-05-20T12:00:00+08:00",
        },
    )
    client = TestClient(create_app(lab_root=lab_root, production_dir=production_dir))

    response = client.get("/api/customers/evytra/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"] == "evytra"
    assert payload["markers"] == ["EVYTRA GmbH"]
    assert payload["lab_status"] == "draft"
    assert payload["production_status"] == "production"
    assert payload["runtime_ready"] is True
    assert payload["production_exists"] is True


def test_update_profile_markers_requires_admin_token_and_syncs_production(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    create_profile(lab_root)
    production_dir = tmp_path / "profiles"
    write_json(production_dir / "evytra.json", {"profile_name": "evytra", "status": "production", "markers": []})
    client = TestClient(create_app(lab_root=lab_root, production_dir=production_dir))

    missing = client.put("/api/customers/evytra/profile/markers", json={"markers": ["EVYTRA GmbH"]})
    updated = client.put(
        "/api/customers/evytra/profile/markers",
        headers=admin_headers(),
        json={"markers": ["EVYTRA GmbH", "EVYTRA GmbH", "  "]},
    )

    assert missing.status_code == 403
    assert updated.status_code == 200
    assert updated.json()["markers"] == ["EVYTRA GmbH"]
    assert json.loads((lab_root / "customers" / "evytra" / "profile.json").read_text(encoding="utf-8"))["markers"] == ["EVYTRA GmbH"]
    assert json.loads((production_dir / "evytra.json").read_text(encoding="utf-8"))["markers"] == ["EVYTRA GmbH"]


def test_publish_requires_profile_markers(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    create_profile(lab_root)
    client = TestClient(create_app(lab_root=lab_root, production_dir=tmp_path / "profiles"))
    client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})
    client.post("/api/customers/evytra/runs/run-1/approve", headers=admin_headers(), json={"actor": "admin", "note": "ok"})

    response = client.post("/api/customers/evytra/runs/run-1/publish", headers=admin_headers())

    assert response.status_code == 409
    assert "profile.markers" in response.json()["detail"]


def test_confirm_expected_saves_merged_draft_and_reruns_evaluation(tmp_path):
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    expected_path = lab_root / "customers" / "evytra" / "expected" / "sample.json"
    if expected_path.exists():
        expected_path.unlink()
    write_json(
        run_dir / "adjudication" / "sample.merged_draft.json",
        {
            "header": {"customer_name": "EVYTRA GmbH", "po_number": "PO-1", "po_date": "2026-05-14"},
            "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
        },
    )
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post("/api/customers/evytra/runs/run-1/samples/sample/confirm-expected")

    assert response.status_code == 200
    assert expected_path.is_file()
    payload = response.json()
    assert payload["evaluation"]["sample_count"] == 1
    assert payload["samples"][0]["report"]["expected_missing"] is False
    assert payload["samples"][0]["report"]["publishable"] is True


def test_save_sample_corrections_updates_expected_and_records_notes(tmp_path):
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    write_json(
        run_dir / "adjudication" / "sample.merged_draft.json",
        {
            "header": {
                "customer_name": "EVYTRA GmbH",
                "po_number": "PO-1",
                "po_date": "2026-05-14",
                "payment_terms": "30 days net",
            },
            "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
        },
    )
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post(
        "/api/customers/evytra/runs/run-1/samples/sample/corrections",
        json={
            "actor": "business",
            "corrections": [
                {
                    "field": "header.payment_terms",
                    "correct_value": "90 days net",
                    "note": "Payment terms are printed in the PO footer.",
                },
                {
                    "field": "items[0].qty",
                    "correct_value": 3,
                    "note": "Quantity was corrected during visual review.",
                }
            ],
        },
    )

    assert response.status_code == 200
    expected = json.loads((lab_root / "customers" / "evytra" / "expected" / "sample.json").read_text(encoding="utf-8"))
    corrections = json.loads((run_dir / "corrections" / "sample.corrections.json").read_text(encoding="utf-8"))
    payload = response.json()
    assert expected["header"]["payment_terms"] == "90 days net"
    assert corrections["corrections"][0]["wrong_value"] == "30 days net"
    assert corrections["corrections"][0]["correct_value"] == "90 days net"
    assert corrections["corrections"][0]["note"] == "Payment terms are printed in the PO footer."
    assert expected["items"][0]["qty"] == 3
    assert corrections["corrections"][1]["field"] == "items[0].qty"
    assert corrections["corrections"][1]["correct_value"] == 3
    assert payload["samples"][0]["corrections"]["corrections"][0]["field"] == "header.payment_terms"
    assert payload["samples"][0]["report"]["publishable"] is False
    assert any(error["field"] == "header.payment_terms" for error in payload["samples"][0]["report"]["quality_errors"])


def test_sample_pdf_endpoint_serves_input_pdf(tmp_path):
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs" / "sample.pdf").write_bytes(b"%PDF-1.4\nsample")
    client = TestClient(create_app(lab_root=lab_root))

    response = client.get("/api/customers/evytra/runs/run-1/samples/sample/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.content.startswith(b"%PDF-1.4")


def test_sample_pdf_endpoint_uses_manifest_source_filename(tmp_path):
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    write_json(run_dir / "manifest.json", {"run_id": "run-1", "customer": "evytra", "samples": ["复杂 文件.pdf"], "created_at": "2026-05-14T18:30:00+08:00"})
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs" / "复杂 文件.pdf").write_bytes(b"%PDF-1.4\ncomplex")
    client = TestClient(create_app(lab_root=lab_root))

    response = client.get("/api/customers/evytra/runs/run-1/samples/复杂 文件/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-1.4")


def test_sample_page_image_endpoint_renders_png(tmp_path):
    fitz = pytest.importorskip("fitz")
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    pdf_path = run_dir / "inputs" / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PO sample")
    document.save(pdf_path)
    document.close()
    client = TestClient(create_app(lab_root=lab_root))

    response = client.get("/api/customers/evytra/runs/run-1/samples/sample/page-image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_delete_run_requires_admin_token_and_removes_directory(tmp_path, monkeypatch):
    monkeypatch.setenv(ADMIN_TOKEN_ENV, "secret-admin-token")
    lab_root = tmp_path / "profile-lab"
    run_dir = create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    missing = client.delete("/api/customers/evytra/runs/run-1")
    deleted = client.delete("/api/customers/evytra/runs/run-1", headers=admin_headers())

    assert missing.status_code == 403
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert not run_dir.exists()


def test_submit_without_webhook_records_skipped_notification(tmp_path, monkeypatch):
    monkeypatch.delenv("PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL", raising=False)
    lab_root = tmp_path / "profile-lab"
    create_run(lab_root)
    client = TestClient(create_app(lab_root=lab_root))

    response = client.post("/api/customers/evytra/runs/run-1/submit", json={"actor": "business", "note": "ready"})

    assert response.status_code == 200
    assert response.json()["notification_status"] == "skipped"
    assert response.json()["notification_error"]


def test_build_approval_payload_uses_po_profile_lab_event_and_boolean_publishable():
    payload = build_approval_payload(
        customer="evytra",
        run_id="run-1",
        summary={"overall_score": 0.98, "publishable": "true"},
        review_url="/profile-lab/customers/evytra/runs/run-1",
    )

    assert payload == {
        "event": "po_profile_lab.approval_requested",
        "customer": "evytra",
        "run_id": "run-1",
        "overall_score": 0.98,
        "publishable": False,
        "review_url": "/profile-lab/customers/evytra/runs/run-1",
    }
