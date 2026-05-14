import importlib
import json
from pathlib import Path

from profile_lab.customer_assets import create_run, init_customer
from profile_lab.pdf_pages import sample_key_from_pdf


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


def test_sample_key_from_pdf_removes_extension():
    assert sample_key_from_pdf(Path("PO-001.pdf")) == "PO-001"
