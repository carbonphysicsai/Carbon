"""The attack engine extracted from battery's Track A harness
(OWNER-GRAPHITE-ATTACKER-01, slice AT-A).

The claims tested:
- battery's harness runs through the engine and its records, conditions and
  coverage report are byte-identical to the pre-extraction harness;
- a family is IN_PROGRESS only when every attack held, every specimen fired
  and every control passed; a silent specimen, a missing control, no attempt
  or a boundary that did not answer is INCONCLUSIVE, never a pass;
- a breach or a wrongly refused control is a finding, in the CONDITIONS
  vocabulary only, and none is suppressed;
- the budget counts attacks attempted; the engine never reads held-out
  controls.

Mutation-style tests name the mutation each would turn red on.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from carbon.agent_campaign.attack import engine
from carbon.battery import track_a
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK

REPO = Path(__file__).resolve().parents[2]

#: The harness's output on 2363950db, before the extraction. A change here is
#: a change to battery's Track A evidence and needs its own review.
PINNED = {
    "coverage.json": "0dbac5d88207afe6306f17bc27e237e2461620c9b2f687feb3f2c7a37cec2d6b",
    "attempts.jsonl": "5cd7ccb6a01af2708f01e037917c04e8573aa227e425701adc2a2b2382b6f2c5",
    "conditions.json": "ba50297abaf775783d0ae62158432d6a17f2fc2e7eeeb0d05ebf3c44359f5bf3",
}


def test_battery_track_a_output_is_byte_identical_after_the_extraction(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(REPO)
    assert track_a.main(["run", "--out", str(tmp_path)]) == 1
    capsys.readouterr()
    for name, pinned in PINNED.items():
        got = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        assert got == pinned, name


def test_battery_consumes_the_engine():
    assert track_a.Family is engine.Family
    assert all(type(f) is engine.Family for f in track_a.FAMILIES)
    # The names battery's EV5 panel reads (`value.panel.harness_constructions`).
    for family in track_a.FAMILIES:
        assert family.family_id == family.name
        assert family.protocol_family == family.description
        assert family.attacks()


# -- a toy family, named for no Challenge ------------------------------------


def _boundary(value):
    return {"accepted": value == "ok"}


def _open(value):
    return {"accepted": True}


def _breached(result):
    return result["accepted"]


def toy(**changes):
    fields = {
        "name": "toy_surface",
        "check": "artifact_and_dependency_attacks",
        "boundary": _boundary,
        "attacks": lambda: (("bad_a", "bad-a"), ("bad_b", "bad-b"), ("bad_c", "c")),
        "specimen": _open,
        "breached": _breached,
        "control": engine.control_from(_boundary, lambda: "ok", _breached),
    }
    return engine.Family(**{**fields, **changes})


def _verdicts(run, role):
    return [r["verdict"] for r in run.records if r["role"] == role]


def test_a_clean_family_is_in_progress_and_never_an_acceptance():
    run = engine.run_family(toy())
    assert _verdicts(run, "attack") == [engine.HELD] * 3
    assert _verdicts(run, "specimen") == [engine.FIRED] * 3
    assert _verdicts(run, "control") == [engine.PASSED]
    assert engine.family_state(run) == "IN_PROGRESS"
    assert engine.findings([run]) == []
    assert "ACCEPTED" not in engine.FAMILY_STATES
    assert "HELD" not in engine.FAMILY_STATES  # HELD is an attack's verdict
    assert {r["schema"] for r in run.records} == {engine.ATTEMPT_SCHEMA}
    assert (run.available, run.attempted, run.exhausted) == (3, 3, False)


def test_a_breach_is_a_failing_trigger_finding():
    """Mutation: a boundary that accepts an attack."""
    run = engine.run_family(toy(boundary=_open))
    assert engine.family_state(run) == "FINDING"
    found = engine.findings([run])
    assert [f.condition for f in found] == ["FAILING_TRIGGER"] * 3
    assert {f.role for f in found} == {"attack"}
    assert all(f.condition in CONDITIONS for f in found)
    assert found[0].as_dict() == {
        "condition": "FAILING_TRIGGER",
        "family": "toy_surface",
        "attempt": "bad_a",
        "role": "attack",
        "evidence_digest": run.records[0]["result_digest"],
    }


def test_a_wrongly_refused_control_is_a_finding():
    """Mutation: a boundary that refuses everything, the valid control too."""
    shut = lambda value: {"accepted": False}
    run = engine.run_family(
        toy(boundary=shut, control=engine.control_from(shut, lambda: "ok", _breached))
    )
    assert _verdicts(run, "control") == [engine.REFUSED]
    assert engine.family_state(run) == "FINDING"
    assert [f.role for f in engine.findings([run])] == ["control"]


def test_mutation_silent_specimen_is_never_counted_as_a_pass():
    """Mutation: the specimen is the real boundary, so the detector cannot
    fire. The family is INCONCLUSIVE, not IN_PROGRESS."""
    run = engine.run_family(toy(specimen=_boundary))
    assert set(_verdicts(run, "specimen")) == {engine.SILENT}
    assert engine.family_state(run) == "INCONCLUSIVE"
    # One silent specimen among fired ones is enough.
    partial = engine.run_family(toy(specimen=lambda v: {"accepted": v != "c"}))
    assert _verdicts(partial, "specimen") == [engine.FIRED, engine.FIRED, engine.SILENT]
    assert engine.family_state(partial) == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "error, verdict",
    [
        (engine.InfrastructureFailure("pod lost"), engine.FAILED_INFRA),
        (TimeoutError("wall clock"), engine.TIMEOUT),
        (RuntimeError("boom"), engine.CRASHED),
    ],
)
def test_a_boundary_that_does_not_answer_is_never_a_pass_nor_a_finding(error, verdict):
    """Mutation: count FAILED_INFRA (or a timeout) as a pass."""

    def raises(_value):
        raise error

    run = engine.run_family(toy(boundary=raises))
    assert _verdicts(run, "attack") == [verdict] * 3
    assert engine.family_state(run) == "INCONCLUSIVE"
    assert engine.findings([run]) == []
    specimen = engine.run_family(toy(specimen=raises))
    assert set(_verdicts(specimen, "specimen")) == {verdict}
    assert engine.family_state(specimen) == "INCONCLUSIVE"

    def control():
        raise error

    silent_control = engine.run_family(toy(control=control))
    assert _verdicts(silent_control, "control") == [verdict]
    assert engine.family_state(silent_control) == "INCONCLUSIVE"
    assert engine.findings([silent_control]) == []


def test_the_budget_counts_attacks_attempted():
    run = engine.run_family(toy(), budget=2)
    assert [r["attempt"] for r in run.records if r["role"] == "attack"] == [
        "bad_a",
        "bad_b",
    ]
    assert (run.available, run.attempted, run.exhausted, run.not_attempted) == (
        3,
        2,
        True,
        1,
    )
    assert engine.family_state(run) == "IN_PROGRESS"
    assert engine.run_family(toy(), budget=99).attempted == 3
    # Zero attempts is no evidence.
    empty = engine.run_family(toy(), budget=0)
    assert engine.family_state(empty) == "INCONCLUSIVE"
    for bad in (-1, 1.5, True, "2"):
        with pytest.raises(ValueError, match="budget"):
            engine.run_family(toy(), budget=bad)


def test_missing_evidence_is_inconclusive():
    rows = list(engine.run_family(toy()).records)
    no_control = [r for r in rows if r["role"] != "control"]
    no_specimen = [
        r for r in rows if not (r["role"] == "specimen" and r["attempt"] == "bad_b")
    ]
    only_control = [r for r in rows if r["role"] == "control"]
    for records in (no_control, no_specimen, only_control, []):
        assert engine.family_state(records, "toy_surface") == "INCONCLUSIVE"
    assert engine.family_state(rows, "toy_surface") == "IN_PROGRESS"


def test_attack_names_are_unique_and_families_are_well_formed():
    with pytest.raises(ValueError, match="attack_names_are_unique"):
        engine.run_family(toy(attacks=lambda: (("a", 1), ("a", 2))))
    with pytest.raises(ValueError, match="family_check_is_a_track_a_check"):
        toy(check="not_a_check")
    with pytest.raises(ValueError, match="family_name"):
        toy(name="Not-A-Token")
    with pytest.raises(TypeError, match="callable"):
        toy(boundary=None)
    with pytest.raises(TypeError):
        engine.run_family(object())
    assert engine.TRACK_A_CHECKS == CHECKS[LEDGER_TRACK]


def test_mutation_a_finding_outside_conditions_is_refused():
    """Mutation: emit a finding whose condition is not in CONDITIONS."""
    with pytest.raises(ValueError, match="finding_condition_outside_conditions"):
        engine.Finding("EXPLOIT", "toy_surface", "bad_a", "attack", "sha256:0")
    assert engine.FINDING_CONDITION in CONDITIONS


class _Control:
    def __init__(self, name, split, value=None, check=None):
        self.name, self.split, self.value, self.check = name, split, value, check


def test_trained_controls_are_each_recorded_by_name():
    run = engine.run_family(
        toy(),
        controls=(
            _Control("ok_value", "trained", "ok"),
            _Control("own_check", "trained", check=lambda: True),
        ),
    )
    assert [
        (r["attempt"], r["verdict"]) for r in run.records if r["role"] == "control"
    ] == [
        ("ok_value", engine.PASSED),
        ("own_check", engine.PASSED),
    ]
    refused = engine.run_family(toy(), controls=(_Control("bad", "trained", "nope"),))
    assert engine.family_state(refused) == "FINDING"


def test_mutation_the_engine_never_reads_a_held_out_control():
    """Mutation: the engine runs held-out controls."""
    for split in ("held_out", None, "both"):
        with pytest.raises(engine.HeldOutControlRefused):
            engine.run_family(toy(), controls=(_Control("hidden", split, "ok"),))


def test_a_control_whose_boundary_does_not_say_accepted_answers_nothing():
    """A boundary that only reports breaches cannot show a wrongful refusal."""
    silent = lambda value: {"breach": False}
    run = engine.run_family(
        toy(boundary=silent, breached=lambda r: r.get("breach", False)),
        controls=(_Control("value_only", "trained", "ok"),),
    )
    assert _verdicts(run, "control") == [engine.CRASHED]
    assert engine.family_state(run) == "INCONCLUSIVE"


def test_records_carry_the_run_context():
    context = engine.RunContext(challenge="some-challenge-v1", profile="level-2")
    run = engine.run_family(toy(), context=context)
    assert {(r["challenge"], r["profile"]) for r in run.records} == {
        ("some-challenge-v1", "level-2")
    }
    assert {r["check"] for r in run.records} == {"artifact_and_dependency_attacks"}
