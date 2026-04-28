"""
TDD tests for /check-email endpoint - Exchange mailbox integration
"""
import importlib.util
from pathlib import Path

import pytest

SERVICE_PATH = (
    Path(__file__).resolve().parents[1] / "service" / "po_parser_service.py"
)


def load_service_module():
    spec = importlib.util.spec_from_file_location("po_parser_service", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_email_request_model():
    module = load_service_module()
    req = module.CheckEmailRequest(
        incoming_dir="/mnt/smb/po_pdfs/incoming",
        exchange_email="test@example.com",
        exchange_password="pass",
        exchange_server="mail.example.com",
    )
    assert req.incoming_dir == "/mnt/smb/po_pdfs/incoming"
    assert req.exchange_email == "test@example.com"
    assert req.exchange_password == "pass"
    assert req.exchange_server == "mail.example.com"
    assert req.max_emails == 10
    assert req.unread_only is True


@pytest.mark.asyncio
async def test_check_email_missing_config():
    module = load_service_module()
    import os
    # Temporarily unset env vars
    old_email = os.environ.pop("EXCHANGE_EMAIL", None)
    old_pass = os.environ.pop("EXCHANGE_PASSWORD", None)
    old_server = os.environ.pop("EXCHANGE_SERVER", None)
    old_incoming = os.environ.pop("EXCHANGE_INCOMING_DIR", None)
    try:
        from fastapi import HTTPException
        from fastapi.testclient import TestClient
        client = TestClient(module.app)
        resp = client.post("/check-email", json={})
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]
    finally:
        for key, val in [
            ("EXCHANGE_EMAIL", old_email),
            ("EXCHANGE_PASSWORD", old_pass),
            ("EXCHANGE_SERVER", old_server),
            ("EXCHANGE_INCOMING_DIR", old_incoming),
        ]:
            if val is not None:
                os.environ[key] = val
