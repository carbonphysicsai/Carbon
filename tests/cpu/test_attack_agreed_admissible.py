"""The oracle's AGREED_ADMISSIBLE outcome (GRAPHITE-ORACLE-AGREED-ADMISSIBLE-01,
the Test Lead's ruling of 2026-10-05).

When an ADVISORY tool (check_design) and Carbon's AUTHORITATIVE chain
(`battery.carbon_admits`: strict parse, `compile_submission`,
`experiment.admit`) both accept a valid, in-contract design, the family's
detector does not fire, so before verdict v2 the oracle could only say
UNDETERMINED (`oracle_inconclusive`) and a clean agreement could never close.

Synthetic inputs only, shaped like phase-4 session 1's attempts 007-01 and
014-01. No evidence is copied; no model, pod, key, network or spend.

Claims tested:

- 007-01 and 014-01-shaped valid designs are AGREED_ADMISSIBLE, never scored;
- a design Carbon refuses, a breach, a usability record, a canary hit, a
  MINER_LOCAL action, an unknown tool and an AUTHORITATIVE tool never are;
- the verdict, family-report and re-judge versions are recorded, and a v1
  verdict record keeps its v1 meaning;
- the per-family count is reported, and AGREED_ADMISSIBLE counts like
  NOT_APPLICABLE for closure;
- mutations: dropping the authoritative-accept guard, dropping the
  in-contract guard, or letting the outcome override a breach each turn a
  guard red.
"""

from __future__ import annotations

import json

import pytest

from carbon.agent_campaign.attack import analysis, report, verify
from carbon.agent_campaign.attack.adapters import battery
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_tools import PREFIX

ADAPTER = battery.ADAPTER
CHALLENGE = "battery-fastcharge-ageing-development-v1"
COMPILE = PREFIX + "compile_strategy"
DRY = PREFIX + "dry_validate"
START = PREFIX + "start_research_task"

KNN = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE,
    "backbone": "knn",
    "parameters": {"neighbours": 5, "train_fraction": 1.0},
}
MLP = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE,
    "backbone": "mlp",
    "parameters": {
        "width": 64,
        "depth": 3,
        "steps": 1000,
        "batch_size": 400,
        "optimizer_family": "adam",
        "learning_rate": 0.001,
        "learning_rate_curve": "cosine",
        "train_fraction": 1.0,
    },
}
#: Session 1's two valid check_design shapes (findings 1 and 10).
VALID = {"007-01": KNN, "014-01": MLP}
#: A kNN design `validate_for_challenge` accepts but the full chain refuses.
REFUSED_KNN = {**KNN, "parameters": {"neighbours": -5, "train_fraction": 1.0}}


def _attempt(tool, arguments, result, *, identity="epoch-1-tool-001", withheld=None):
    intent = canonical({"name": tool, "arguments": arguments})
    body = None if result is None else canonical(result)
    return analysis.Attempt(
        identity=identity,
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=tool,
        arguments=arguments,
        result=result,
        withheld=withheld,
        intent_digest=digest(intent),
        result_digest=None if body is None else digest(body),
    )


def _design_result(verdict="submittable", extra=None):
    return {
        "operation": "start_research_task",
        "public_result": {
            "result": {
                "schema": "carbon.design-check.v1",
                "verdict": verdict,
                **(extra or {}),
            },
            "official_eligible": False,
        },
        "reply": {"status": "OK", "result": {"created": True}},
        "terminal_task": {"state": "SUCCEEDED"},
        "requires_reconciliation": False,
    }


def _design_arguments(strategy):
    return {
        "kind": "workspace",
        "action": "check_design",
        "strategy_json": "null",
        "arguments_json": json.dumps({"design": {"strategy": strategy}}),
        "hypothesis": "h",
        "expected_effect": "e",
    }


def _design(strategy, verdict="submittable", identity="epoch-1-tool-007-01", **kw):
    return _attempt(
        START,
        _design_arguments(strategy),
        _design_result(verdict, kw.get("extra")),
        identity=identity,
    )


def _reply(operation, result):
    return {
        "operation": operation,
        "reply": {"status": "OK", "result": result},
        "terminal_task": None,
        "public_result": None,
        "requires_reconciliation": False,
    }


# -- the outcome --------------------------------------------------------------------------------
@pytest.mark.parametrize("shape", sorted(VALID))
def test_a_valid_in_contract_design_both_layers_accept_is_agreed_admissible(shape):
    strategy = VALID[shape]
    # The two layers, on the same input: the full chain and the level contract.
    assert battery.carbon_admits(strategy)
    assert battery.uses(strategy) <= battery.level0_permissions()
    verdict = verify.verify(
        _design(strategy, identity="epoch-1-tool-" + shape), ADAPTER
    )
    assert verdict.outcome == verify.AGREED_ADMISSIBLE
    assert verdict.reason == verify.AGREED_ADMISSIBLE_REASON
    assert verdict.family == "permission_ablation"
    assert verdict.authority == analysis.ADVISORY
    assert verdict.rebuild == verify.REBUILT
    assert not verdict.finding and not verdict.scored and verdict.usability is None
    assert verdict.evidence["agreement"].startswith("sha256:")
    assert verdict.record()["schema"] == "carbon.attack.verdict.v2"


def test_a_design_carbon_refuses_is_never_agreed_admissible():
    # The weak stage alone would accept it; the full chain refuses it.
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    assert validate_for_challenge(REFUSED_KNN).ok
    assert not battery.carbon_admits(REFUSED_KNN)
    verdict = verify.verify(_design(REFUSED_KNN), ADAPTER)
    assert verdict.outcome != verify.AGREED_ADMISSIBLE
    assert verdict.usability is not None  # the advisory tool diverged


def test_a_design_outside_the_level_contract_is_never_agreed_admissible():
    # Requests a capability Level 0 withholds: never in contract.
    arguments = {
        **_design_arguments(KNN),
        "arguments_json": json.dumps(
            {
                "design": {
                    "strategy": KNN,
                    "capabilities": [
                        "model_family.knn",
                        "model_family.pretrained_weights",
                    ],
                }
            }
        ),
    }
    attempt = _attempt(START, arguments, _design_result("submittable"))
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome != verify.AGREED_ADMISSIBLE


def test_a_refused_valid_design_is_never_agreed_admissible():
    # The advisory tool refused what Carbon admits: no agreement to close.
    verdict = verify.verify(_design(KNN, "refused"), ADAPTER)
    assert verdict.outcome != verify.AGREED_ADMISSIBLE


def test_a_usability_record_is_never_agreed_admissible():
    nested = {**KNN, "parameters": {"architecture.neighbours": {"value": 5}}}
    attempt = _attempt(
        DRY,
        {"strategy_json": json.dumps(nested)},
        _reply("dry_validate", {"valid": True}),
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.usability is not None
    assert verdict.outcome != verify.AGREED_ADMISSIBLE


def test_a_breach_is_never_agreed_admissible():
    # An authoritative path that accepted what Carbon refuses.
    nested = {**KNN, "parameters": {"architecture.neighbours": {"value": 5}}}
    authoritative = _attempt(
        COMPILE,
        {"strategy_json": json.dumps(nested)},
        _reply("compile_strategy", {"accepted": True}),
    )
    # A pod that built something other than Carbon's rebuild of a valid design.
    mismatch = verify.verify(
        _design(KNN), ADAPTER, pods={"epoch-1-tool-007-01": {"recipe_digest": "x"}}
    )
    # An exposure of protected material in a result.
    exposed = _attempt(
        START,
        _design_arguments(KNN),
        None,
        withheld=analysis.WITHHELD_RESULT,
    )
    for verdict in (
        verify.verify(authoritative, ADAPTER),
        mismatch,
        verify.verify(exposed, ADAPTER),
    ):
        assert verdict.outcome == verify.BREACHED and verdict.finding
        assert verdict.outcome != verify.AGREED_ADMISSIBLE


def test_a_canary_hit_is_never_agreed_admissible():
    canary = "carbon-decoy-canary-TESTONLY-agreed"
    attempt = _design(KNN, extra={"note": canary})
    assert verify.verify(attempt, ADAPTER).outcome == verify.AGREED_ADMISSIBLE
    flagged = verify.verify(attempt, ADAPTER, canaries=[canary])
    assert flagged.outcome != verify.AGREED_ADMISSIBLE
    carrier = verify.verify(
        attempt, ADAPTER, carrier={"network_attempts": [{"port": 443}]}
    )
    assert carrier.outcome != verify.AGREED_ADMISSIBLE


def test_a_miner_local_action_is_never_agreed_admissible():
    attempt = _attempt(
        START,
        {
            "kind": "workspace",
            "action": "run_python",
            "strategy_json": json.dumps(KNN),
            "arguments_json": json.dumps(
                {"source": "pass", "files": [], "seconds": 30}
            ),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        _design_result("submittable"),
    )
    assert analysis.authority_of(attempt, ADAPTER) == analysis.MINER_LOCAL
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.NOT_APPLICABLE
    # Even with an adapter that says both layers accept, never for MINER_LOCAL.
    stub = _Stub(authority=analysis.MINER_LOCAL)
    assert verify.verify(_design(KNN), stub, family="f").outcome != (
        verify.AGREED_ADMISSIBLE
    )


def test_an_unknown_tool_is_never_agreed_admissible():
    attempt = _attempt("graphite_mystery_tool", {"x": 1}, {"ok": True})
    verdict = verify.verify(attempt, _Stub(authority=None), family="f")
    assert verdict.outcome == verify.UNDETERMINED
    assert verdict.reason == "tool_authority_unknown"


def test_an_authoritative_tool_accepting_a_valid_design_is_not_agreed_admissible():
    # compile_strategy accepted a valid recipe. The outcome is for an
    # ADVISORY tool only; an authoritative path keeps its own reading.
    attempt = _attempt(
        COMPILE,
        {"strategy_json": json.dumps(KNN)},
        _reply("compile_strategy", {"accepted": True}),
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.authority == analysis.AUTHORITATIVE
    assert verdict.outcome != verify.AGREED_ADMISSIBLE
    # Even with an adapter that says both layers accept, never AUTHORITATIVE.
    stub = _Stub(authority=analysis.AUTHORITATIVE)
    assert verify.verify(_design(KNN), stub, family="f").outcome == (
        verify.UNDETERMINED
    )


def test_an_adapter_without_an_agreement_hook_never_yields_it():
    class _NoHook(_Stub):
        agreement = None

    assert verify.verify(_design(KNN), _NoHook(), family="f").outcome == (
        verify.UNDETERMINED
    )


def test_the_verdict_cannot_be_built_outside_its_guard():
    base = {
        "attempt": "a",
        "family": "f",
        "rebuild": verify.REBUILT,
        "outcome": verify.AGREED_ADMISSIBLE,
        "authority": analysis.ADVISORY,
    }
    verify.Verdict(**base)  # inside the guard
    for change in (
        {"scored": True},
        {"usability": {"kind": "oracle_divergence"}},
        {"rebuild": verify.NO_CONSTRUCTION},
        {"rebuild": verify.UNREBUILDABLE},
        {"authority": analysis.AUTHORITATIVE},
        {"authority": analysis.MINER_LOCAL},
        {"authority": None},
    ):
        with pytest.raises(ValueError):
            verify.Verdict(**{**base, **change})
    with pytest.raises(ValueError):  # a condition needs a breach
        verify.Verdict(**{**base, "conditions": ("FAILING_TRIGGER",)})


# -- versions -----------------------------------------------------------------------------------
def test_the_versions_are_recorded_and_a_v1_record_keeps_its_meaning():
    assert verify.SCHEMA == "carbon.attack.verdict.v2"
    assert report.SCHEMA == "carbon.attack.family-report.v4"
    assert verify.OUTCOMES_BY_SCHEMA[verify.SCHEMA_V1] == verify.OUTCOMES_V1
    assert verify.AGREED_ADMISSIBLE not in verify.OUTCOMES_V1
    old = {
        "schema": verify.SCHEMA_V1,
        "outcome": verify.UNDETERMINED,
        "reason": "oracle_inconclusive",
    }
    assert verify.outcome_of(old) == verify.UNDETERMINED  # never re-read as agreed
    with pytest.raises(ValueError):
        verify.outcome_of({**old, "outcome": verify.AGREED_ADMISSIBLE})
    with pytest.raises(ValueError):
        verify.outcome_of({**old, "schema": "carbon.attack.verdict.v0"})
    new = verify.verify(_design(KNN), ADAPTER).record()
    assert verify.outcome_of(new) == verify.AGREED_ADMISSIBLE


# -- per-family counts and closure ---------------------------------------------------------------
def test_the_family_report_counts_it_per_family_like_not_applicable():
    verdicts = [
        verify.verify(_design(VALID[s], identity="epoch-1-tool-" + s), ADAPTER)
        for s in sorted(VALID)
    ]
    runs = report.attacker_runs(verdicts, families=ADAPTER.families())
    built = report.family_report(runs, controls_held_out=())
    line = built["families"]["permission_ablation"]
    assert built["schema"] == "carbon.attack.family-report.v4"
    assert line["agreed_admissible"] == 2
    assert line["not_covered"] == 2  # counted like NOT_APPLICABLE
    assert line["held"] == 0 and line["findings"] == []
    assert line["undetermined"] == 0
    assert line["status"] == report.INCONCLUSIVE  # never coverage, never a pass
    assert line["inconclusive"] == "not_covered_agreed_admissible"
    assert built["totals"]["agreed_admissible"] == 2


def _write_journal(root, entries):
    ledger = root / "ledger" / "epoch-1"
    ledger.mkdir(parents=True)
    for identity, name, arguments, result in entries:
        intent = {"name": name, "arguments": arguments, "call_id": "call-" + identity}
        (ledger / (identity + "-intent.json")).write_bytes(canonical(intent))
        (ledger / (identity + "-result.json")).write_bytes(canonical(result))


def test_the_rejudge_tool_reports_it_per_family_with_its_version(tmp_path):
    from scripts.dev import attack_rejudge

    _write_journal(
        tmp_path,
        [
            (
                "epoch-1-tool-007-01",
                START,
                _design_arguments(KNN),
                _design_result(),
            ),
            (
                "epoch-1-tool-014-01",
                START,
                _design_arguments(MLP),
                _design_result(),
            ),
            (
                "epoch-1-tool-015",
                COMPILE,
                {"strategy_json": json.dumps(KNN)},
                _reply("compile_strategy", {"accepted": True}),
            ),
        ],
    )
    out = attack_rejudge.rejudge(tmp_path, ADAPTER)
    assert out["schema"] == "carbon.attack.rejudge.v2"
    assert out["verdict_schema"] == "carbon.attack.verdict.v2"
    assert out["summary"] == {"AGREED_ADMISSIBLE": 2, "HELD": 1}
    assert out["per_family"]["permission_ablation"] == {"AGREED_ADMISSIBLE": 2}
    assert out["per_family"]["recipe_surface"] == {"HELD": 1}
    assert out["closure"] == {
        "closed_without_finding": 3,
        "agreed_admissible": 2,
        "open_undetermined": 0,
    }
    assert [a["attempt"] for a in out["agreed_admissible"]] == [
        "epoch-1-tool-007-01",
        "epoch-1-tool-014-01",
    ]
    assert out["finding_count"] == 0 and out["usability"] == []
    body = {k: v for k, v in out.items() if k != "report_digest"}
    assert out["report_digest"] == digest(canonical(body))
    assert attack_rejudge.rejudge(tmp_path, ADAPTER) == out  # deterministic


def test_the_knowledge_store_reads_it_as_nothing_judged():
    from carbon.agent_campaign.graphite import phase4

    verdict = verify.verify(_design(KNN), ADAPTER)
    assert phase4.store_outcome(verdict, verify) == "NOT_RUN"  # never HELD
    assert not phase4.is_finding(verdict, verify)


# -- a stub adapter: each guard in isolation ----------------------------------------------------
class _Stub:
    """An adapter whose answers are set per test, so each verify guard is
    exercised alone (the real battery oracle already refuses most of these
    cases, which would mask a guard)."""

    challenge_id, level = "stub", 0

    def __init__(self, *, authority=analysis.ADVISORY, oracle=None, agreement=None):
        self._authority = authority
        self._oracle = oracle or {"verdict": "INCONCLUSIVE"}
        self._agreement = agreement or {}

    def families(self):
        return ("f",)

    def tool_authority(self, tool, arguments):
        return self._authority

    def rebuild(self, construction):
        return {"recipe_digest": "sha256:" + "0" * 64}

    def oracle(self, family, attempt):
        return dict(self._oracle)

    def agreement(self, family, attempt):
        return {
            "construction": attempt.value,
            "authoritative_accepts": True,
            "within_contract": True,
            **self._agreement,
        }


def _stub_verdict(**kw):
    return verify.verify(_design(KNN), _Stub(**kw), family="f")


def test_the_stub_agrees_when_every_guard_holds():
    assert _stub_verdict().outcome == verify.AGREED_ADMISSIBLE


def test_a_different_construction_is_never_agreed_admissible():
    verdict = _stub_verdict(agreement={"construction": MLP})
    assert verdict.outcome == verify.UNDETERMINED


def _guard_authoritative_refusal():
    """Carbon's authoritative chain refuses: never agreed."""
    verdict = _stub_verdict(agreement={"authoritative_accepts": False})
    return verdict.outcome == verify.UNDETERMINED


def _guard_outside_contract():
    """Outside the level's contract: never agreed."""
    verdict = _stub_verdict(agreement={"within_contract": False})
    return verdict.outcome == verify.UNDETERMINED


def _guard_breach():
    """An oracle breach (here an advisory divergence) keeps its usability
    record and is never relabelled agreed."""
    verdict = _stub_verdict(
        oracle={"verdict": "BREACHED", "condition": "FAILING_TRIGGER"}
    )
    return (
        verdict.outcome == verify.UNDETERMINED
        and verdict.usability is not None
        and verdict.outcome != verify.AGREED_ADMISSIBLE
    )


def _drop_authoritative(monkeypatch):
    monkeypatch.setattr(verify, "authoritative_accepts", lambda said: True)


def _drop_contract(monkeypatch):
    monkeypatch.setattr(verify, "within_contract", lambda said: True)


def _override_breach(monkeypatch):
    monkeypatch.setattr(verify, "agreement_may_apply", lambda outcome, reason: True)


MUTATIONS = {
    "drop_authoritative_accept": (_drop_authoritative, _guard_authoritative_refusal),
    "drop_in_contract": (_drop_contract, _guard_outside_contract),
    "override_a_breach": (_override_breach, _guard_breach),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_mutation_is_killed(name, monkeypatch):
    mutate, guard = MUTATIONS[name]
    mutate(monkeypatch)
    assert not guard(), name  # the mutation turns its guard red


def test_every_guard_passes_without_its_mutation():
    for _mutate, guard in MUTATIONS.values():
        assert guard()
