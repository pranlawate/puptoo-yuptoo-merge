import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from puptoo.handlers import get_handler
from puptoo.handlers.advisor import AdvisorHandler
from puptoo.handlers.compliance import ComplianceHandler
from puptoo.handlers.qpc import QPCHandler


def test_get_handler_advisor():
    assert isinstance(get_handler("advisor"), AdvisorHandler)


def test_get_handler_compliance():
    assert isinstance(get_handler("compliance"), ComplianceHandler)


def test_get_handler_malware_detection():
    assert isinstance(get_handler("malware-detection"), ComplianceHandler)


def test_get_handler_qpc():
    assert isinstance(get_handler("qpc"), QPCHandler)


def test_get_handler_unknown():
    assert get_handler("unknown") is None


def test_advisor_handler_process():
    msg = {
        "insights_id": "id-1",
        "account_id": "acc-1",
        "org_id": "org-1",
        "hostname": "host.example.com",
        "facts": {"foo": "bar"},
    }
    result = AdvisorHandler().process(msg, {})
    assert result["insights_id"] == "id-1"
    assert result["account_id"] == "acc-1"
    assert result["org_id"] == "org-1"
    assert result["hostname"] == "host.example.com"
    assert result["facts"] == {"foo": "bar"}


def test_compliance_handler_process_forwards_metadata():
    metadata = {"policy_id": "p-1", "compliant": True}
    result = ComplianceHandler().process({"metadata": metadata, "other": "x"}, {})
    assert result == metadata


def test_qpc_handler_process_runs_modifiers():
    long_value = "x" * 300
    msg = {
        "host": {"insights_id": "h-1"},
        "tags": [{"name": "flag", "value": "true"}, {"name": "note", "value": long_value}],
    }
    result = QPCHandler().process(msg, {"reporter": "qpc-test"})
    assert result["insights_id"] == "h-1"
    assert result["tags"][0]["value"] is True
    assert len(result["tags"][1]["value"]) == 250
    assert "stale_timestamp" in result
    assert result["reporter"] == "qpc-test"
    assert "stale_warning_timestamp" in result
