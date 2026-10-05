"""The attack family report and Graphite's phase 3 and phase 4 records carry
the conditional tag (GRAPHITE-CONDITIONAL-EXPLORATION-01, policy
`conditional-evidence.v1`).

A family report, a phase 3 session result and a phase 4 coverage report and
iteration-log entry are results; each records the findings open on the
controller when it is recorded (for a session, its own included) and the
policy identity. Dropping the tag turns the family report's test red. Scripted
model, scripted pods and synthetic adapters only: no inference, pod or spend.
"""

from __future__ import annotations

import pytest

# The attack report and the Graphite sessions need numpy; the contract lane
# has none, so this module is skipped there rather than failing to collect.
pytest.importorskip("numpy")

import graphite_phase3_fixtures as p3f
import test_attack_report as tar
import test_graphite_phase4 as t4
from graphite_phase3_fixtures import ScriptedPods, text

from carbon.agent_campaign.attack import report
from carbon.agent_campaign.graphite import phase3
from carbon.challenge_readiness import conditional_evidence as ce

FINDING = {"id": "f-synthetic", "digest": "sha256:" + "9" * 64}


def test_an_attack_family_report_carries_the_tag():
    runs = report.attacker_runs(tar.VERDICTS, families=tar.FAMILIES)
    family = report.family_report(
        runs, controls_held_out=tar.HELD_OUT, open_findings=[FINDING]
    )
    assert family["conditional_on"] == [FINDING]
    assert family["conditional_policy"] == ce.identity()
    assert tar.full_report()["conditional_on"] == []
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional(family, site="test")


def test_dropping_the_family_reports_tag_fails_its_test(monkeypatch):
    original = ce.tag
    test_an_attack_family_report_carries_the_tag()  # passes with the tag
    monkeypatch.setattr(ce, "tag", lambda found, policy=ce.POLICY: original([], policy))
    with pytest.raises(AssertionError):
        test_an_attack_family_report_carries_the_tag()


def test_a_phase3_session_result_is_tagged_with_the_open_findings(tmp_path):
    graphite = p3f.provider(tmp_path, [text("done")], ScriptedPods())
    control = p3f.controller(tmp_path, graphite)
    try:
        control.record_finding("earlier-defect", "FAILING_TRIGGER", b"unrepaired")
        result = phase3.run_session(control, graphite, p3f.brief(graphite), 1)
        open_now = control.open_findings()
        terminal = [e for e in control.ledger() if e["kind"] == "terminal"]
    finally:
        control.close()
    assert [r["id"] for r in result["conditional_on"]] == ["earlier-defect"]
    assert result["conditional_on"] == open_now
    assert result["conditional_policy"] == ce.identity()
    assert terminal and all(e["conditional_on"] == open_now for e in terminal)
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional(result, site="test")


def test_a_phase3_session_with_no_open_finding_is_unconditional(tmp_path):
    result, _graphite, _control = p3f.session(tmp_path, [text("done")], ScriptedPods())
    assert result["conditional_on"] == []
    assert result["conditional_policy"] == ce.identity()
    ce.require_unconditional(result, site="test")


@t4.needs_engine
def test_phase4_coverage_and_log_entry_carry_the_sessions_findings(tmp_path):
    adapter = t4._synthetic_adapter(weak=True)
    miner = t4.RecordingMiner({"status": "OK", "accepted": True})
    control, _kstore, entry, coverage, _brief = t4._attack(
        tmp_path, adapter, t4._validate_script(t4.ATTACK), miner
    )
    try:
        open_now = control.open_findings()
    finally:
        control.close()
    assert entry["findings"]
    assert set(entry["findings"]) <= {r["id"] for r in open_now}
    assert coverage["conditional_on"] == entry["conditional_on"] == open_now
    assert coverage["conditional_policy"] == ce.identity()
    log = (tmp_path / "attacker" / "iteration-log.jsonl").read_bytes()
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional_bytes(log, site="test")


@t4.needs_engine
def test_a_held_boundary_session_is_unconditional(tmp_path):
    adapter = t4._synthetic_adapter(weak=False)
    miner = t4.RecordingMiner({"status": "REFUSED", "accepted": False})
    control, _kstore, entry, coverage, _brief = t4._attack(
        tmp_path, adapter, t4._validate_script(t4.ATTACK), miner
    )
    control.close()
    assert entry["findings"] == []
    assert coverage["conditional_on"] == entry["conditional_on"] == []
    assert coverage["families"]["conditional_on"] == []
    ce.require_unconditional(coverage, site="test")
