import importlib.util
import re
from datetime import datetime as real_datetime
from pathlib import Path
from unittest.mock import patch

SERVICE_PATH = (
    Path(__file__).resolve().parents[1] / "service" / "po_parser_service.py"
)


def load_service_module():
    spec = importlib.util.spec_from_file_location("po_parser_service", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_soap_xml_uses_local_server_time_for_rdate_rtime():
    module = load_service_module()

    class FakeDatetime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 5, 6, 18, 54, 24)

        @classmethod
        def utcnow(cls):
            return real_datetime(2026, 5, 6, 10, 54, 24)

    with patch.object(module, "datetime", FakeDatetime):
        xml = module._build_soap_xml({"GUID": "ABC123"})

    rdate = re.search(r"<RDATE>(\d+)</RDATE>", xml)
    rtime = re.search(r"<RTIME>(\d+)</RTIME>", xml)

    assert rdate is not None
    assert rtime is not None
    assert rdate.group(1) == "20260506"
    assert rtime.group(1) == "185424"
