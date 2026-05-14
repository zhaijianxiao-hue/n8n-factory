import importlib
import json
from pathlib import Path

import pytest

from profile_lab.commands import main
from profile_lab.customer_assets import create_run, init_customer
from profile_lab.llm_client import extract_json_object
from profile_lab.pdf_pages import sample_key_from_pdf
from profile_lab.text_candidate import generate_text_candidate_with_model
from profile_lab.vision_candidate import generate_vision_candidate_with_model


class FakeJsonClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create_json(self, messages, model):
        self.calls.append({"messages": messages, "model": model})
        return self.payload


def test_profile_lab_package_imports():
    module = importlib.import_module("profile_lab")
    assert module.__all__ == ["__version__"]


def test_commands_module_exposes_main():
    commands = importlib.import_module("profile_lab.commands")
    assert callable(commands.main)


def test_init_customer_creates_expected_asset_tree(tmp_path):
    root = tmp_path / "profile-lab"

    result = init_customer(
        root=root,
        customer_key="acme",
        display_name="ACME Corp",
    )

    assert result.customer_dir == root / "customers" / "acme"
    assert (result.customer_dir / "samples").is_dir()
    assert (result.customer_dir / "expected").is_dir()
    assert (result.customer_dir / "runs").is_dir()
    assert (result.customer_dir / "customer.json").is_file()
    assert (result.customer_dir / "profile.json").is_file()
    assert (result.customer_dir / "prompt.md").is_file()
    assert (result.customer_dir / "field_priority.json").is_file()

    customer = json.loads((result.customer_dir / "customer.json").read_text(encoding="utf-8"))
    assert customer["customer_key"] == "acme"
    assert customer["display_name"] == "ACME Corp"

    profile = json.loads((result.customer_dir / "profile.json").read_text(encoding="utf-8"))
    assert profile["profile_name"] == "acme"
    assert profile["status"] == "draft"
    assert profile["version"] == "0.1.0"


def test_init_customer_is_idempotent_for_existing_assets(tmp_path):
    root = tmp_path / "profile-lab"
    first = init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    prompt_path = first.customer_dir / "prompt.md"
    prompt_path.write_text("custom prompt\n", encoding="utf-8")

    second = init_customer(root=root, customer_key="acme", display_name="Changed Name")

    assert second.customer_dir == first.customer_dir
    assert prompt_path.read_text(encoding="utf-8") == "custom prompt\n"


def test_create_run_copies_samples_and_writes_manifest(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    run = create_run(root=root, customer_key="acme", run_id="2026-05-14-153000")

    assert run.run_dir == root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run.run_dir / "inputs" / "po-001.pdf").is_file()
    manifest = json.loads((run.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["customer"] == "acme"
    assert manifest["samples"] == ["po-001.pdf"]


def test_create_run_raises_when_no_pdf_samples_exist(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")

    with pytest.raises(ValueError, match="no PDF samples found for customer: acme"):
        create_run(root=root, customer_key="acme", run_id="2026-05-14-153000")


def test_create_run_raises_when_run_id_already_exists(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")
    run_dir = root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    run_dir.mkdir()

    with pytest.raises(FileExistsError, match="run already exists: "):
        create_run(root=root, customer_key="acme", run_id="2026-05-14-153000")


def test_sample_key_from_pdf_removes_extension():
    assert sample_key_from_pdf(Path("PO-001.pdf")) == "PO-001"


def test_draft_command_creates_candidate_files(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    exit_code = main([
        "--lab-root",
        str(root),
        "draft",
        "--customer",
        "acme",
        "--run-id",
        "2026-05-14-153000",
        "--skip-render",
    ])

    assert exit_code == 0
    run_dir = root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run_dir / "candidates" / "text" / "po-001.json").is_file()
    assert (run_dir / "candidates" / "vision" / "po-001.json").is_file()


def test_draft_command_creates_adjudication_artifacts(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    exit_code = main([
        "--lab-root",
        str(root),
        "draft",
        "--customer",
        "acme",
        "--run-id",
        "2026-05-14-153000",
        "--skip-render",
    ])

    assert exit_code == 0
    run_dir = root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run_dir / "adjudication" / "po-001.merged_draft.json").is_file()
    assert (run_dir / "adjudication" / "po-001.conflict_report.md").is_file()
    assert (run_dir / "adjudication" / "po-001.field_evidence.json").is_file()
    assert (run_dir / "adjudication" / "po-001.profile_suggestions.md").is_file()

    merged_draft = json.loads(
        (run_dir / "adjudication" / "po-001.merged_draft.json").read_text(encoding="utf-8")
    )
    assert merged_draft["metadata"]["adjudication_status"] == "no_usable_candidate"

    conflict_report = (run_dir / "adjudication" / "po-001.conflict_report.md").read_text(
        encoding="utf-8"
    )
    assert "No usable candidate was produced" in conflict_report

    field_evidence = json.loads(
        (run_dir / "adjudication" / "po-001.field_evidence.json").read_text(encoding="utf-8")
    )
    assert field_evidence["_adjudication"]["human_review_required"] is True
    assert "header" not in field_evidence
    assert "header.po_number" in field_evidence


def test_extract_json_object_strips_markdown_fence():
    content = "```json\n{\"header\": {\"po_number\": \"PO-1\"}, \"items\": []}\n```"
    assert extract_json_object(content)["header"]["po_number"] == "PO-1"


def test_text_candidate_uses_model_client(tmp_path):
    pdf_path = tmp_path / "po-001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    client = FakeJsonClient(
        {
            "header": {"customer_name": "ACME", "po_number": "PO-1"},
            "items": [],
            "confidence": 0.8,
            "warnings": [],
        }
    )

    result = generate_text_candidate_with_model(
        pdf_path=pdf_path,
        extracted_text="Purchase Order PO-1",
        prompt="Return JSON",
        model="text-model",
        client=client,
    )

    assert result["source_file"] == "po-001.pdf"
    assert result["metadata"]["candidate_source"] == "text"
    assert result["header"]["po_number"] == "PO-1"
    assert client.calls[0]["model"] == "text-model"


def test_vision_candidate_uses_model_client(tmp_path):
    pdf_path = tmp_path / "po-001.pdf"
    page_path = tmp_path / "page-001.png"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    page_path.write_bytes(b"png")
    client = FakeJsonClient(
        {
            "header": {"customer_name": "ACME", "po_number": "PO-1"},
            "items": [],
            "confidence": 0.9,
            "warnings": [],
        }
    )

    result = generate_vision_candidate_with_model(
        pdf_path=pdf_path,
        page_paths=[page_path],
        prompt="Return JSON",
        model="vision-model",
        client=client,
    )

    assert result["source_file"] == "po-001.pdf"
    assert result["metadata"]["candidate_source"] == "vision"
    assert result["metadata"]["page_count"] == 1
    assert result["header"]["po_number"] == "PO-1"
    assert client.calls[0]["model"] == "vision-model"
