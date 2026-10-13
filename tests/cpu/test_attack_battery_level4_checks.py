"""PKT-15: discriminating declared probes and unavailable session evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("jax")

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import INCONCLUSIVE, NOT_RUN, AttackInput
from carbon.agent_campaign.attack.adapters import battery_level4 as l4
from carbon.agent_campaign.attack.adapters import battery_level4_checks as checks


@pytest.mark.parametrize("name", sorted(checks.NAMES))
def test_fixed_probes_have_bad_attacks_fired_specimens_and_valid_controls(name):
    run = engine.run_family(checks.family(name))
    attacks = [r for r in run.records if r["role"] == "attack"]
    specimens = [r for r in run.records if r["role"] == "specimen"]
    controls = [r for r in run.records if r["role"] == "control"]
    assert attacks and {r["verdict"] for r in attacks} == {engine.HELD}
    assert specimens and {r["verdict"] for r in specimens} == {engine.FIRED}
    assert controls and {r["verdict"] for r in controls} == {engine.PASSED}
    for split in ("trained", "held_out"):
        control = next(
            c for c in checks.controls(split, "fixture-v1") if c.family == name
        )
        assert engine.evaluate_control(checks.family(name), control) is True


def test_compile_scope_bypass_is_caught_by_the_real_entry_point(monkeypatch):
    from carbon.level4 import compile as g5

    monkeypatch.setattr(g5, "SCOPES", (*g5.SCOPES, "mainnet"))
    result = checks.oracle(checks.COMPILE, AttackInput("mainnet", {"case": "mainnet"}))
    assert result.verdict == engine.BREACHED
    assert result.condition == engine.FINDING_CONDITION
    assert result.specimen == engine.FIRED


def test_g5_program_substitution_is_caught(monkeypatch):
    from carbon.level4 import compile as g5

    monkeypatch.setattr(g5, "PROGRAM", g5.PROGRAM + "\n# replaced program\n")
    result = checks.oracle(
        checks.COMPILE, AttackInput("valid", {"case": "development"})
    )
    assert result.verdict == engine.BREACHED


def test_no_compile_worker_is_executed(monkeypatch):
    import sys
    from types import ModuleType

    default_runner = ModuleType("carbon.development_session.research_carrier")
    reached = []

    def forbidden_runner(*args, **kwargs):
        reached.append((args, kwargs))
        raise AssertionError("the real worker must not run for a software probe")

    default_runner._run = forbidden_runner
    monkeypatch.setitem(sys.modules, default_runner.__name__, default_runner)
    for case in ("mainnet", "unset_deadline", "development", "testnet"):
        found = checks._compile({"case": case})
        assert found["dispatched"] == (case in ("development", "testnet"))
        assert not checks._compile_breached(found)
    assert reached == []


def test_r6_missing_setting_factor_is_caught(monkeypatch):
    from carbon.training_budget import analysis

    monkeypatch.setattr(analysis, "r6", lambda *_: {"settings_needing_a_factor": {}})
    result = checks.oracle(
        checks.COUNTING, AttackInput("slow", {"case": "slow_gather"})
    )
    assert result.verdict == engine.BREACHED


def test_r6_threshold_change_is_caught(monkeypatch):
    from carbon.training_budget import analysis

    monkeypatch.setattr(analysis, "R6_SLOW", 100.0)
    result = checks.oracle(
        checks.COUNTING, AttackInput("slow", {"case": "slow_gather"})
    )
    assert result.verdict == engine.BREACHED


def test_r7_missing_safety_limit_is_caught(monkeypatch):
    from carbon.training_budget import analysis

    monkeypatch.setattr(analysis, "r7", lambda *_: {"time_limit_s": None})
    result = checks.oracle(
        checks.COUNTING, AttackInput("limit", {"case": "missing_safety_limit"})
    )
    assert result.verdict == engine.BREACHED


def test_registered_threshold_boundary_and_positive_contrast():
    at = checks._counting({"case": "threshold"})
    slow = checks._counting({"case": "slow_gather"})
    assert at["expected_factor"] is None and at["factor"] is None
    assert slow["expected_factor"] == 3.0 and slow["factor"] == 3.0
    assert not checks._counting_breached(at)
    assert not checks._counting_breached(slow)


@pytest.mark.parametrize("wrong", [[], ["fixture-b"]])
def test_missing_or_wrong_case_nonfinite_detection_is_caught(monkeypatch, wrong):
    from carbon.level4 import grade

    monkeypatch.setattr(grade, "nonfinite_cases", lambda *_: wrong)
    result = checks.oracle(checks.FINITE, AttackInput("nan", {"case": "nan"}))
    assert result.verdict == engine.BREACHED


@pytest.mark.parametrize("case", ["nan", "positive_inf", "negative_inf"])
def test_g7_identifies_actual_graph_output_case(case, monkeypatch):
    from carbon.level4 import grade

    def forbidden_exam(*args, **kwargs):
        raise AssertionError("a finite-case probe must not execute an exam")

    monkeypatch.setattr(grade, "grade", forbidden_exam)
    result = checks._finite({"case": case})
    assert result["expected"] == result["found"] == ["fixture-a"]
    assert all(out.device.platform == "cpu" for out in checks._outputs(case))


def test_a_finite_contrast_is_inconclusive_as_an_attack_not_false_coverage():
    value = {"case": "finite"}
    result = checks.oracle(checks.FINITE, AttackInput("finite", value))
    assert result.verdict == INCONCLUSIVE
    assert result.specimen == engine.SILENT
    assert not checks._finite_breached(checks._finite(value))


@pytest.mark.parametrize("name", sorted(checks.NAMES))
def test_session_claims_cannot_become_declared_fixture_coverage(name):
    # An ordinary session view, including a claimed GPU execution and a
    # spoofed fixture case, is not an exact engine declaration.
    view = SimpleNamespace(
        name="session",
        value={"case": "mainnet", "gpu_executed": True},
        arguments={"case": "nan", "executed": True, "backend": "gpu"},
        rebuilt=True,
    )
    result = l4.ADAPTER.oracle(name, view)
    assert result.verdict == NOT_RUN
    assert result.specimen is None and result.condition is None
    assert result.reading == checks.UNAVAILABLE


@pytest.mark.parametrize("name", sorted(checks.NAMES))
def test_unknown_declared_probe_is_not_held_or_not_applicable(name):
    result = checks.oracle(name, AttackInput("unknown", {"case": "unknown"}))
    assert result.verdict == NOT_RUN
    assert result.reading == checks.UNAVAILABLE
    assert result.evidence_digest == engine.digest(
        {"not_run": checks.UNSUPPORTED, "family": name}
    )


def test_extra_fields_and_subclass_do_not_execute_a_probe():
    class Derived(AttackInput):
        pass

    for attempt in (
        AttackInput("extra", {"case": "nan", "document": "untrusted"}),
        Derived("subclass", {"case": "nan"}),
    ):
        assert checks.oracle(checks.FINITE, attempt).verdict == NOT_RUN


def test_all_thirteen_identities_remain_and_unknown_seams_stay_not_run():
    from carbon.agent_campaign.attack.adapter import validate

    validate(l4.ADAPTER)
    existing = set(l4._family_table())
    assert len(existing) == 7
    assert {f.name for f in l4.ADAPTER.families()} == existing | checks.NAMES
    seams = l4.ADAPTER.level_families()
    assert {s.name for s in seams} == {
        "l4_fresh_cases_rerun",
        "l4_procedural_tables",
        "l4_gpu_nondeterminism",
    }
    assert all(s.state == NOT_RUN for s in seams)
    assert len(l4.ADAPTER.families()) + len(seams) == 13


def test_software_only_probes_cannot_be_declared_as_session_reachable_families():
    from carbon.agent_campaign.attack import analysis

    tool = analysis.PREFIX + "compile_strategy"
    for name in checks.NAMES:
        arguments = {"hypothesis": f"probe [family: {name}] here"}
        assert l4.ADAPTER.family_for(tool, arguments) == l4.SURFACE
    for name in l4._family_table():
        arguments = {"hypothesis": f"probe [family: {name}] here"}
        assert l4.ADAPTER.family_for(tool, arguments) == name


@pytest.mark.parametrize(
    "name",
    sorted(checks.NAMES)
    + ["l4_fresh_cases_rerun", "l4_procedural_tables", "l4_gpu_nondeterminism"],
)
def test_real_session_unavailable_evidence_is_undetermined_and_never_agreement(name):
    import json

    from carbon.agent_campaign.attack import analysis, verify

    attempt = analysis.Attempt(
        identity="epoch-1-tool-001",
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=analysis.PREFIX + "compile_strategy",
        arguments={
            "strategy_json": json.dumps(l4._strategy()),
            "case": "finite",
            "gpu_executed": True,
        },
        result={"accepted": True},
        withheld=None,
        intent_digest=engine.digest("fixture-intent"),
        result_digest=engine.digest("fixture-result"),
    )
    view = verify.oracle_attempt(attempt, adapter=l4.ADAPTER, rebuilt=True)
    outcome, condition, _near, _evidence, reason = verify._oracle(
        l4.ADAPTER, name, view
    )
    assert outcome == verify.UNDETERMINED
    assert condition is None
    assert reason == verify.NO_ORACLE_EVIDENCE_REASON
    assert not verify.agreement_may_apply(outcome, reason)
    verdict = verify.verify(attempt, l4.ADAPTER, family=name)
    assert verdict.outcome == verify.UNDETERMINED
    assert verdict.reason == verify.NO_ORACLE_EVIDENCE_REASON
    assert verdict.scored is False


def test_existing_inconclusive_and_true_not_applicable_semantics_are_preserved():
    from carbon.agent_campaign.attack import verify
    from carbon.agent_campaign.attack.adapter import OracleResult

    view = SimpleNamespace(name="fixture")
    for verdict, specimen, expected in (
        (NOT_RUN, None, verify.NOT_APPLICABLE),
        (INCONCLUSIVE, engine.SILENT, verify.UNDETERMINED),
    ):
        adapter = SimpleNamespace(
            oracle=lambda *_args, verdict=verdict, specimen=specimen: OracleResult(
                family="fixture",
                attempt="fixture",
                verdict=verdict,
                specimen=specimen,
                evidence_digest=engine.digest("fixture"),
            )
        )
        outcome, _condition, _near, _evidence, reason = verify._oracle(
            adapter, "fixture", view
        )
        assert outcome == expected
        if verdict == INCONCLUSIVE:
            assert reason == verify.ORACLE_INCONCLUSIVE_REASON
