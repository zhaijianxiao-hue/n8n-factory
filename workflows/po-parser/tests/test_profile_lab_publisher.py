import json

import pytest

from profile_lab.customer_assets import init_customer
from profile_lab.json_io import write_json
from profile_lab.publisher import PublishGateError, publish_profile


def publishable_summary(**overrides):
    summary = {
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
    }
    summary.update(overrides)
    return summary


def write_admin_approval(customer_dir, run_id):
    write_json(
        customer_dir / "runs" / run_id / "approval.json",
        {
            "state": "approved",
            "admin_decision": "approved",
            "admin_by": "admin",
        },
    )


def test_publish_profile_copies_profile_when_gate_passes(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        publishable_summary(),
    )
    write_admin_approval(customer_dir, "run-1")

    output_path = publish_profile(
        root=root,
        customer_key="acme",
        run_id="run-1",
        production_dir=production_dir,
    )

    assert output_path == production_dir / "acme.json"
    published = json.loads(output_path.read_text(encoding="utf-8"))
    assert published["profile_name"] == "acme"
    assert published["status"] == "production"
    assert published["last_run_id"] == "run-1"


def test_publish_profile_blocks_missing_admin_approval(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        publishable_summary(),
    )

    with pytest.raises(PublishGateError, match="admin approval is required"):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )


def test_publish_profile_blocks_failed_gate(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        {"publishable": False, "sample_count": 1},
    )
    write_admin_approval(customer_dir, "run-1")

    with pytest.raises(PublishGateError):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )


def test_publish_profile_blocks_empty_forged_summary(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        publishable_summary(sample_count=0, reports=[]),
    )
    write_admin_approval(customer_dir, "run-1")

    with pytest.raises(PublishGateError, match="sample_count must be greater than 0"):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )


def test_publish_profile_blocks_report_with_blocking_errors(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    summary = publishable_summary()
    summary["reports"][0]["blocking_errors"] = [{"field": "header.po_number"}]
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        summary,
    )
    write_admin_approval(customer_dir, "run-1")

    with pytest.raises(PublishGateError, match="blocking_errors"):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )


def test_publish_profile_blocks_low_p1_score(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    summary = publishable_summary()
    summary["reports"][0]["scores"]["p1"] = 0.94
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        summary,
    )
    write_admin_approval(customer_dir, "run-1")

    with pytest.raises(PublishGateError, match="scores.p1"):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )
