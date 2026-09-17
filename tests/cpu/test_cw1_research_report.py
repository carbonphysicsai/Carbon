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
