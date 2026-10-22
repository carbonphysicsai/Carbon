"""A selected recipe's practice gate verdict is said in the journal, and 'not reported' is never a pass (G2)."""

from scripts.dev.miner_launchpad import campaign_view


def decision(**body):
    own = {"decisions": [{"sequence": 1, **body}]}
    return campaign_view.feed(own, [])["entries"][0]


def test_passed_and_failed_are_said():
    passed = decision(gate_verdict="PASSED")
    assert passed["text"] == "Practice gates passed."
    failed = decision(gate_verdict="FAILED", reason="selected recipe failed a gate")
    assert failed["text"] == "selected recipe failed a gate"
    assert "failed, so nothing is submitted" in failed["detail"]


def test_not_reported_is_never_shown_as_a_pass():
    entry = decision(
        gate_verdict="NOT_REPORTED", note="This practice reports no gate verdict."
    )
    assert "not reported" in entry["text"] and "not a pass" in entry["text"]
    assert "passed" not in entry["text"].lower()
    assert "This practice reports no gate verdict." in entry["detail"]


def test_a_decision_without_a_verdict_reads_as_before():
    entry = decision(reason="Chose a wider model", evidence="run 3")
    assert entry["text"] == "Chose a wider model" and entry["detail"] == "run 3"
