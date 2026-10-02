"""Battery Track A at Level 0 (CI-BATTERY-L0-01): the registered harness.

The claims tested:
- every registered attack is held by the real boundary;
- the same attacks breach a deliberately vulnerable specimen, so each detector
  can fire;
- every valid control passes, so a held attack is not a boundary that refuses
  everything;
- findings are emitted, never suppressed, and no family state is ever an
  acceptance.

The coverage map names every Track A check, and every reused test it cites
exists.
"""

import ast
import json
from pathlib import Path

import pytest

from carbon.battery import track_a
from carbon.challenge_readiness.admission import CHECKS

REPO = Path(__file__).resolve().parents[2]
FAMILIES = {f.family_id: f for f in track_a.FAMILIES}


@pytest.fixture(scope="module")
def records():
    return {f.family_id: track_a.run_family(f) for f in track_a.FAMILIES}


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_attack_is_held_and_every_specimen_fires(records, family):
    rows = records[family]
    attacks = [r for r in rows if r["role"] == "attack"]
    specimens = [r for r in rows if r["role"] == "specimen"]
    assert attacks and len(attacks) == len(specimens)
    assert {r["verdict"] for r in attacks} == {track_a.HELD}, [
        r["attempt"] for r in attacks if r["verdict"] != track_a.HELD
    ]
    assert {r["verdict"] for r in specimens} == {track_a.FIRED}, [
        r["attempt"] for r in specimens if r["verdict"] != track_a.FIRED
    ]


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_valid_control_passes(records, family):
    (control,) = [r for r in records[family] if r["role"] == "control"]
    assert control["verdict"] == track_a.PASSED
    assert track_a.family_state(records[family], family) == "IN_PROGRESS"
    assert track_a.findings(records[family]) == []


def test_recipe_attacks_are_refused_by_typed_compiler_issues():
    """Refused for a named reason, not by an incidental crash."""
    for name, strategy in track_a.RECIPE_ATTACKS:
        result = track_a.compile_boundary(strategy)
        assert not result["accepted"], name
        codes = {code for code, _ in result["codes"]}
        assert all("." in code for code in codes), (name, codes)


def test_one_inadmissible_case_disqualifies_an_otherwise_perfect_model():
    """The specimen shows the attack is worth making: averaged away, the
    damaged predictions would score as well as the references themselves."""
    control = track_a.scoring_boundary(track_a.mandatory_control())
    assert control["eligible"] and control["score"] == 0.0
    for name, predictions in track_a.mandatory_inputs():
        real = track_a.scoring_boundary(predictions)
        weak = track_a.averaging_scorer(predictions)
        assert not real["eligible"] and real["n_gate_failed"] == 1, name
        assert weak["eligible"] and weak["score"] == 0.0, name


def _rows(*verdicts):
    return [
        {
            "family": "f",
            "role": role,
            "attempt": f"a{i}",
            "verdict": verdict,
            "result_digest": "sha256:0",
        }
        for i, (role, verdict) in enumerate(verdicts)
    ]


def test_a_breach_or_a_wrong_refusal_is_a_finding_and_never_suppressed():
    breach = _rows(("attack", track_a.BREACHED), ("specimen", track_a.FIRED))
    assert track_a.family_state(breach, "f") == "FINDING"
    assert [f["condition"] for f in track_a.findings(breach)] == ["FAILING_TRIGGER"]
    refused = _rows(("control", track_a.REFUSED))
    assert track_a.family_state(refused, "f") == "FINDING"
    assert track_a.findings(refused)[0]["role"] == "control"


def test_a_silent_specimen_makes_the_family_inconclusive_not_a_pass():
    rows = _rows(
        ("attack", track_a.HELD),
        ("specimen", track_a.SILENT),
        ("control", track_a.PASSED),
    )
    assert track_a.family_state(rows, "f") == "INCONCLUSIVE"


def test_no_family_state_is_an_acceptance():
    states = {
        track_a.family_state(_rows(*v), "f")
        for v in (
            (("attack", track_a.HELD), ("specimen", track_a.FIRED)),
            (("attack", track_a.BREACHED),),
            (("specimen", track_a.SILENT),),
        )
    }
    assert "ACCEPTED" not in states


def test_divergence_on_retained_ev_results_is_emitted():
    """The known findings fire on both EV2 and EV4 (§3.4), and the oracle
    control, which decides best, is never the member at fault."""
    out = track_a.divergence_findings(REPO)
    for name in ("ev2-2026-10-01", "ev4-2026-10-01"):
        conditions = out[name]["conditions"]
        assert any(
            c["condition"] == "SCORE_VALUE_DIVERGENCE"
            and c.get("member") == "control-boundary_optimist"
            for c in conditions
        ), name
        assert not any(c.get("member") == "control-oracle" for c in conditions), name


def test_the_coverage_map_names_exactly_the_track_a_checks():
    assert set(track_a.COVERAGE) == CHECKS["construction_integrity"]
    for check, entry in track_a.COVERAGE.items():
        assert entry["here"] or entry["reused"] or entry["untested"], check
    here = {f.family_id for f in track_a.FAMILIES}
    for f in track_a.FAMILIES:
        assert f.check in CHECKS["construction_integrity"]
        assert f.family_id in track_a.COVERAGE[f.check]["here"]
    assert here


def _test_names(path):
    tree = ast.parse(path.read_text())
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_every_reused_test_it_cites_exists():
    """Reused evidence is named exactly; a renamed or deleted test fails here
    instead of leaving the coverage map claiming it."""
    for check, entry in track_a.COVERAGE.items():
        for citation in entry["reused"]:
            path, _, name = citation.partition("::")
            path = path.split(" ")[0]
            assert (REPO / path).is_file(), (check, path)
            if name:
                assert name in _test_names(REPO / path), (check, citation)


def test_the_command_writes_the_ledger_and_exits_one_when_anything_fires(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(REPO)
    assert track_a.main(["run", "--out", str(tmp_path)]) == 1
    attempts = [
        json.loads(line)
        for line in (tmp_path / "attempts.jsonl").read_text().splitlines()
    ]
    assert {r["schema"] for r in attempts} == {track_a.ATTEMPT_SCHEMA}
    report = json.loads((tmp_path / "coverage.json").read_text())
    assert report["claims"] == {"security_acceptance": False, "qualification": False}
    assert set(report["reserved"].values()) == {"HUMAN_INPUT"}
    assert report["findings"] == []
    assert report["divergence"]["ev4-2026-10-01"]["conditions"] > 0
    assert json.loads((tmp_path / "conditions.json").read_text())
