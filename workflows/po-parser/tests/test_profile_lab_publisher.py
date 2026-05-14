import json

import pytest

from profile_lab.customer_assets import init_customer
from profile_lab.json_io import write_json
from profile_lab.publisher import PublishGateError, publish_profile


def test_publish_profile_copies_profile_when_gate_passes(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        {"publishable": True, "sample_count": 1},
    )

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


def test_publish_profile_blocks_failed_gate(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        {"publishable": False, "sample_count": 1},
    )

    with pytest.raises(PublishGateError):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )
