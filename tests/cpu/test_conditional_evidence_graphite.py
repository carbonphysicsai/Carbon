"""The attack family report and Graphite's phase 3 and phase 4 records carry
the conditional tag (GRAPHITE-CONDITIONAL-EXPLORATION-01, policy
`conditional-evidence.v2` since its 2026-10-05 amendment).

A family report, a phase 3 session result and a phase 4 coverage report and
iteration-log entry are results; each records the findings open on the
controller when it is recorded (for a session, its own included) and the
policy identity. Dropping the tag turns the family report's test red.

The amendment's ordering (Test Lead item 3): a phase 3 finding is recorded on
the controller when it is found, so a next-level proposal written after it
carries it, and the session's findings are recorded before its events and
artifacts are ingested; phase 4 re-tags its family report once every finding
of Carbon's side is recorded. Each has a mutation shown to fail its test.
Scripted model, scripted pods and synthetic adapters only: no inference, pod
or spend.
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
from test_graphite_phase4 import (  # the stand-in's material: an autouse fixture
    _stand_in_material,  # noqa: F401
)

from carbon.agent_campaign.attack import report
from carbon.agent_campaign.graphite import next_level, phase3, phase4
from carbon.agent_campaign.graphite.model import tool
from carbon.agent_campaign.graphite.roles import NEXT_LEVEL
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
    monkeypatch.setattr(
        ce, "tag", lambda found, policy=ce.POLICY, **kw: original([], policy)
    )
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


# --- ordering: no result written untagged while a finding is open -----------------------

#: A next-level proposal the phase-3 fixture literature supports.
PROPOSAL = {
    "capability": "a PDE-residual loss term weighted against the data loss",
    "source_card_ids": ["fixture-operator-0001"],
    "contract_dimension": "objective",
    "contract_capability_id": "objective.pde_weight",
    "outside_contract_because": (
        "the recorded battery contract lists objective.pde_weight as "
        "research_only: Carbon cannot rebuild it"
    ),
    "reconstruction_needs": (
        "a registered residual operator for the battery model and its rebuild "
        "test in the construction contract"
    ),
}


def test_a_phase3_finding_is_recorded_before_the_results_after_it(tmp_path):
    """An unrebuildable proposal is a finding; the next-level proposal the
    session writes after it, and every event and artifact the controller
    ingests from the session, carry it."""
    script = [p3f.propose(p3f.UNREBUILDABLE), tool(NEXT_LEVEL, PROPOSAL), text("done")]
    graphite = p3f.provider(tmp_path, script, ScriptedPods(steps=p3f.steps(1.0)))
    control = p3f.controller(tmp_path, graphite)
    try:
        result = phase3.run_session(control, graphite, p3f.brief(graphite), 1)
        open_now = control.open_findings()
        results = [
            e
            for e in control.ledger()
            if e["kind"] in ("event", "artifact", "terminal")
        ]
    finally:
        control.close()
    [finding] = result["findings"]
    assert [r["id"] for r in open_now] == [finding]
    [stored] = next_level.ProposalStore(graphite._dir(p3f.run_id())).proposals()
    assert stored["schema"] == next_level.SCHEMA_V2
    assert stored["conditional_on"] == open_now
    assert stored["conditional_policy"] == ce.identity()
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional(stored, site="a transcribed level proposal")
    assert [e for e in results if e["kind"] == "event"]
    assert all(e["conditional_on"] == open_now for e in results)


def test_a_session_run_elsewhere_has_its_findings_synced_before_ingest(tmp_path):
    """A session whose findings were not recorded as they were found (its run
    ran in another process, which had no controller bound): `run_session`
    records them before ingesting its events and artifacts, so those carry
    them."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(phase3.Phase3Provider, "_record_finding", lambda s, f: None)
        script = [p3f.propose(p3f.UNREBUILDABLE), text("done")]
        graphite = p3f.provider(tmp_path, script, ScriptedPods(steps=p3f.steps(1.0)))
        control = p3f.controller(tmp_path, graphite)
        try:
            result = phase3.run_session(control, graphite, p3f.brief(graphite), 1)
            open_now = control.open_findings()
            results = [
                e
                for e in control.ledger()
                if e["kind"] in ("event", "artifact", "terminal")
            ]
        finally:
            control.close()
    assert [r["id"] for r in open_now] == result["findings"] != []
    assert [e for e in results if e["kind"] == "event"]
    assert all(e["conditional_on"] == open_now for e in results)


def test_a_next_level_proposal_without_a_finding_is_v2_and_unconditional(tmp_path):
    script = [tool(NEXT_LEVEL, PROPOSAL), text("done")]
    result, graphite, _ = p3f.session(tmp_path, script, ScriptedPods())
    [stored] = next_level.ProposalStore(graphite._dir(p3f.run_id())).proposals()
    assert stored["schema"] == next_level.SCHEMA_V2
    assert stored["conditional_on"] == [] and result["conditional_on"] == []
    ce.require_unconditional(stored, site="test")


@t4.needs_engine
def test_phase4_family_report_carries_the_findings_recorded_after_it(tmp_path):
    adapter = t4._synthetic_adapter(weak=True)
    miner = t4.RecordingMiner({"status": "OK", "accepted": True})
    control, _kstore, _entry, coverage, _brief = t4._attack(
        tmp_path, adapter, t4._validate_script(t4.ATTACK), miner
    )
    try:
        open_now = control.open_findings()
    finally:
        control.close()
    # The deterministic baseline's finding is recorded after the family report
    # is built; the re-tag puts it on the report.
    [baseline] = coverage["findings_by_source"]["deterministic_baseline"]
    assert baseline in {r["id"] for r in coverage["families"]["conditional_on"]}
    assert coverage["families"]["conditional_on"] == coverage["conditional_on"]
    assert coverage["conditional_on"] == open_now


def _ingest_first(monkeypatch):
    """The order before the amendment: a session's findings recorded only
    after its events and artifacts were ingested."""
    original = phase3.sync_findings

    def sync_after_ingest(control, provider, run_id):
        control.poll(phase3.session_key(1))
        return original(control, provider, run_id)

    monkeypatch.setattr(phase3, "sync_findings", sync_after_ingest)


ORDERING_MUTATIONS = {
    "phase3_finding_recorded_when_found": (
        lambda m: m.setattr(
            phase3.Phase3Provider, "_record_finding", lambda s, f: None
        ),
        test_a_phase3_finding_is_recorded_before_the_results_after_it,
    ),
    "phase3_findings_synced_before_ingest": (
        _ingest_first,
        test_a_session_run_elsewhere_has_its_findings_synced_before_ingest,
    ),
    "phase4_family_report_retagged": (
        lambda m: m.setattr(phase4, "retag", lambda result, control: result),
        test_phase4_family_report_carries_the_findings_recorded_after_it,
    ),
}


@pytest.mark.parametrize("name", sorted(ORDERING_MUTATIONS))
def test_disabling_an_ordering_guard_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = ORDERING_MUTATIONS[name]
    if name.startswith("phase4") and t4.needs_engine.args[0]:
        pytest.skip(t4.needs_engine.kwargs.get("reason", "no attack engine"))
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact)  # passes with the guard in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(mutated)
