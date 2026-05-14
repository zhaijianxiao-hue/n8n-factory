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
from profile_lab_ui.models import (
    AdminDecisionRequest,
    ApprovalRecord,
    ApprovalRequest,
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
    assert approval.admin_decision is None
    assert approval.admin_by is None
    assert approval.admin_at is None
    assert approval.note == "ready"
    assert (run_dir / "approval.json").exists()
    assert load_approval(run_dir).state == "submitted"


def test_approval_record_has_planned_metadata_fields():
    approval = ApprovalRecord()

    if hasattr(approval, "model_dump"):
        data = approval.model_dump()
    else:
        data = approval.dict()

    assert list(data.keys()) == [
        "state",
        "submitted_by",
        "submitted_at",
        "admin_decision",
        "admin_by",
        "admin_at",
        "note",
        "notification_status",
        "notification_error",
    ]


def test_request_models_default_to_business_and_admin_actors():
    assert ApprovalRequest().actor == "business"
    assert ApprovalRequest(note="ready").note == "ready"
    assert AdminDecisionRequest().actor == "admin"
    assert AdminDecisionRequest(note="ok").note == "ok"


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
    assert approved.admin_decision == "approved"
    assert approved.admin_by == "admin"
    assert approved.admin_at is not None
    assert publish_allowed(run_dir) is True

    rejected = reject_run(run_dir, admin_by="admin", note="change delivery date rule")

    assert rejected.state == "changes_requested"
    assert rejected.admin_decision == "rejected"
    assert rejected.admin_at is not None
    assert rejected.note == "change delivery date rule"
    assert publish_allowed(run_dir) is False


def test_submit_run_clears_previous_admin_decision(tmp_path):
    run_dir = tmp_path / "profile-lab" / "customers" / "evytra" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    write_summary(run_dir)
    submit_run(run_dir, submitted_by="business", note="ready")
    approve_run(run_dir, admin_by="admin", note="ok")

    approval = submit_run(run_dir, submitted_by="business", note="ready again")

    assert approval.state == "submitted"
    assert approval.admin_decision is None
    assert approval.admin_by is None
    assert approval.admin_at is None
