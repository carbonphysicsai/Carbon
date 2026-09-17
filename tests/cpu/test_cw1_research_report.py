"""Reports never turn preparatory records into real execution."""

import json

import pytest

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


def test_terminal_elapsed_is_durable_and_never_hides_unsettled_work(tmp_path):
    from test_cw1_research_ledger import ledger as make_ledger

    now = [1000]
    meter = make_ledger(tmp_path, clock=lambda: now[0])
    meter.reserve(
        "uncertain",
        owner="alice",
        phase="research",
        request={},
        resources={"reference_invocations": 1},
    )
    marker = tmp_path / "campaign-complete.json"
    marker.write_text(json.dumps({"completed_unix": 1010}))
    now[0] = 1100
    first = report(meter, owner="alice")
    now[0] = 9000
    second = report(meter, owner="alice")
    assert first["elapsed_seconds"] == second["elapsed_seconds"] == 10
    assert second["elapsed_basis"] == "RECORDED_COMPLETION"
    assert second["status"] == "ACTIVE_OR_RECONCILIATION_REQUIRED"
    assert second["active_operations"] == ["uncertain"]
    marker.write_text("{}")
    legacy = report(meter, owner="alice")
    assert legacy["elapsed_seconds"] is None
    assert legacy["elapsed_basis"] == "LEGACY_COMPLETION_TIME_UNKNOWN"
    assert marker.read_text() == "{}"


@pytest.mark.parametrize("completed", [True, -1, 999999, "1010", float("nan")])
def test_invalid_completion_clock_is_rejected(tmp_path, completed):
    meter = CampaignLedger(tmp_path, clock=lambda: 1000)
    (tmp_path / "campaign-complete.json").write_text(
        json.dumps({"completed_unix": completed})
    )
    with pytest.raises(ValueError, match="completion timestamp"):
        report(meter, owner="alice")
