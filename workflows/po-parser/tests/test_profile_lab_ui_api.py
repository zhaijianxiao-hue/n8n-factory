import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from profile_lab_ui.api import create_app
from profile_lab_ui.artifacts import ArtifactNotFoundError
from profile_lab_ui.artifacts import run_dir


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
    newer_run = lab_root / "customers" / "evytra" / "runs" / "run-2"
    write_json(newer_run / "manifest.json", {"run_id": "run-2", "customer": "evytra", "samples": [], "created_at": "2026-05-15T18:30:00+08:00"})
    write_json(newer_run / "evaluation" / "summary.json", {"publishable": True, "sample_count": 0, "reports": []})
    client = TestClient(create_app(lab_root=lab_root))

    customers = client.get("/api/customers").json()
    runs = client.get("/api/customers/evytra/runs").json()

    assert customers == [{"customer_key": "evytra", "display_name": "EVYTRA GmbH", "run_count": 2}]
    assert [run["run_id"] for run in runs] == ["run-2", "run-1"]
    assert runs[1]["approval"]["state"] == "submitted"


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
    assert payload["samples"][0]["text_candidate"]["header"]["po_number"] == "PO-1"


def test_missing_run_returns_404(tmp_path):
    client = TestClient(create_app(lab_root=tmp_path / "profile-lab"))

    response = client.get("/api/customers/evytra/runs/missing")

    assert response.status_code == 404


def test_run_dir_raises_for_missing_path(tmp_path):
    lab_root = tmp_path / "profile-lab"

    with pytest.raises(ArtifactNotFoundError):
        run_dir(lab_root, "evytra", "missing")
