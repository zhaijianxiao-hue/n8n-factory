import json
from pathlib import Path


WORKFLOW_PATH = Path(__file__).parents[1] / "workflow.json"


def load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def get_node(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def test_workflow_uses_last_calendar_day_for_month_end_rows():
    workflow = load_workflow()
    code = get_node(workflow, "生成本次汇率计划")["parameters"]["jsCode"]

    assert "new Date(Date.UTC(year, month, 0)).getUTCDate()" in code
    assert "day === lastDay" in code
    assert code.count("frequency: 'MONTH_END'") == 4


def test_workflow_sends_plain_date_for_nexcore_to_convert():
    workflow = load_workflow()
    code = get_node(workflow, "构建 SAP 批量请求")["parameters"]["jsCode"]

    assert "99999999 - Number(plan.valid_from)" not in code
    assert "gdatu: plan.valid_from" in code


def test_workflow_targets_prd_environment():
    workflow = load_workflow()
    code = get_node(workflow, "构建 SAP 批量请求")["parameters"]["jsCode"]

    assert workflow["name"] == "SAP 汇率同步 - CFETS → OB08 (PRD)"
    assert "environment: 'prd'" in code


def test_sap_write_node_has_no_automatic_retry():
    workflow = load_workflow()
    sap_node = get_node(workflow, "写入 SAP PRD 汇率")

    assert sap_node.get("retryOnFail") is not True
