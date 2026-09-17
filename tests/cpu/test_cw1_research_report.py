"""Reports never turn preparatory records into real execution."""

from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_report import report


def test_empty_report_and_untrusted_text(tmp_path):
    ledger = CampaignLedger(tmp_path)
    ledger.note(
        owner="alice", kind="hypothesis", body={"text": "<script>alert(1)</script>"}
    )
    value = report(ledger, owner="alice")
    assert value["status"] == "NOT_DISPATCHED"
    assert value["used"]["provider_attempts"] == 0
    page = (tmp_path / "research-report.html").read_text()
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert value["campaign_digest"] is None


def test_report_separates_phases_and_preserves_machine_readable_alias(tmp_path):
    import json

    from test_cw1_research_ledger import ledger as make_ledger

    meter = make_ledger(tmp_path)
    meter.reserve(
        "reference",
        owner="alice",
        phase="research",
        request={},
        resources={"reference_invocations": 1},
    )
    value = report(meter, owner="alice")
    assert value["phase_accounting"]["research"]["reference_invocations"] == 1
    assert value["active_operations"] == ["reference"]
    assert json.loads((tmp_path / "agent-report.json").read_bytes()) == value
    assert value["epoch_outcomes"] == []
