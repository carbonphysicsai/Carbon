"""Battery's Level 2 and Level 3 attack adapters: the Test Lead's L2/L3 design.

Claims tested:

1. Each adapter is registered at (battery, level), passes the core's
   validation (all eight Track A checks supplied, trained and held-out
   controls) and attacks its registered variant (`contract_digest` is that
   variant's digest). Level 0 declares no Level 2 or 3 seam any more.
2. Every family's attacks are HELD at Carbon's real boundary, every specimen
   FIRES and every control PASSES.
3. The refusals are the variant's own typed codes: SpecMuon off the Muon
   family, on the plateau curve or on PyTorch; a dense inverse Hessian above
   the worker's memory bound; a numerics choice with no polish stage.
4. Pool selection (battery-l2-v2): P1 and P2 are refused by their own
   `pool.*` codes; P3 and P4 are seams. Seams are NOT_RUN and say why:
   pool selection's budget charge and distribution chasing, no in-surface
   recipe diverged (M2, N2), and the cost calculator refuses development
   recipes (M1's finding).
5. Rebuild compiles a strategy under the level's variant, labelled
   "CPU-verified only"; a recipe outside the variant is unrebuildable.
6. M2 and N2's classification (Test Lead, 2026-10-08): a NaN or Inf injected
   into the trainer's network output, test-only and outside the miner
   surface, ends as the candidate's own failure: a candidate `WorkerFailure`,
   or non-finite predictions the frozen rule makes ineligible with no case
   FAILED_INFRA. Never Carbon's.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.agent_campaign.attack import adapters, engine, identity, verify
from carbon.agent_campaign.attack.adapter import TRACK_A_CHECKS, validate
from carbon.agent_campaign.attack.adapters import battery as b
from carbon.agent_campaign.attack.adapters import battery_declarative as d
from carbon.agent_campaign.attack.adapters import battery_level2 as l2
from carbon.agent_campaign.attack.adapters import battery_level3 as l3

LEVELS = {2: l2, 3: l3}


@pytest.fixture(scope="module", params=sorted(LEVELS))
def level(request):
    return request.param


def test_registered_valid_and_bound_to_its_variant(level):
    adapter = adapters.load(b.CHALLENGE_ID, level)
    assert adapter is LEVELS[level].ADAPTER
    assert (b.CHALLENGE_ID, level) in adapters.registered()
    validate(adapter)
    assert adapter.level == level
    assert adapter.contract_digest == d.variant(level).digest
    checks = {f.check for f in adapter.families()} | {
        s.check for s in adapter.level_families()
    }
    assert checks == set(TRACK_A_CHECKS)
    assert not any(s.level in (2, 3) for s in b.ADAPTER.level_families())


def test_level_2_compact_rebuild_record_mints_a_replayable_specimen(tmp_path):
    construction = l2._strategy(muon_spectral=True)
    rebuilt = l2.ADAPTER.rebuild(construction)
    record = verify.record_of(rebuilt)
    assert "recipe_digest" not in record  # the historical mint failure
    artifact = identity.artifact_of(l2.ADAPTER, rebuilt, record)
    folder = tmp_path / verify.specimen_name("l2_pool_sources_and_weights", artifact)
    verify.bundle_attack_specimen(
        l2.ADAPTER,
        construction,
        record,
        folder,
        label="epoch-1-tool-007",
        artifact=artifact,
    )
    assert verify.clean_attack_specimen(folder, l2.ADAPTER)["status"] == "REBUILT"


def test_every_attack_held_every_specimen_fired(level):
    for definition in LEVELS[level].ADAPTER.families():
        run = engine.run_family(definition.family)
        attacks = [r for r in run.records if r["role"] == "attack"]
        verdicts = {(r["role"], r["verdict"]) for r in run.records}
        assert attacks and {r["verdict"] for r in attacks} == {"HELD"}, definition.name
        assert ("specimen", "SILENT") not in verdicts, definition.name
        assert ("control", "PASSED") in verdicts, definition.name


def _codes(gate, attacks):
    return {name: gate(value) for name, value in attacks}


def test_level_2_refusals_are_the_variants_typed_codes():
    found = _codes(d.variant_gate(2), l2._off_family_attacks())
    for family in ("adam", "lion", "sgd_momentum", "sam"):
        assert "development.needs_muon" in found[f"muon_spectral_on_{family}"]["issues"]
    assert "development.not_with_plateau_curve" in (
        found["muon_spectral_with_plateau_curve"]["issues"]
    )
    assert (
        "development.backend_not_served" in found["muon_spectral_on_pytorch"]["issues"]
    )
    for result in _codes(d.miner_contract_gate, l2._ablation_attacks()).values():
        assert result == {"status": "REFUSED", "code": "SubmissionRefused"}


def test_level_3_refusals_are_the_variants_typed_codes():
    found = _codes(d.variant_gate(3), l3._unbounded_attacks())
    for family in ("bfgs", "ssbfgs", "ssbroyden"):
        assert "development.inverse_hessian_too_large" in (
            found[f"dense_{family}_at_largest_mlp"]["issues"]
        )
    assert found["polish_beyond_the_contract"]["status"] == "REFUSED"
    lane = _codes(d.variant_gate(3), l3._off_lane_attacks())
    assert "development.backend_not_served" in lane["bfgs_on_pytorch"]["issues"]
    assert "development.no_polish_stage" in lane["bfgs_without_polish"]["issues"]
    # The largest MLP with limited-memory BFGS stays admitted.
    assert d.accepted(d.variant_gate(3)(l3._families()["l3_unbounded_work"].held_out))


def test_level_2_pool_attacks_are_refused_by_their_pool_codes():
    found = _codes(d.variant_gate(2), l2._pool_attacks())
    expected = {
        "pool_practice_stratum": "pool.practice_refused",
        "pool_practice_beside_train": "pool.practice_refused",
        "pool_unregistered_version": "pool.version_unregistered",
        "pool_part_not_in_version": "pool.part_not_in_version",
        "pool_names_its_cases": "pool.selection_malformed",
        "pool_weight_above_two": "pool.weight_out_of_bounds",
        "pool_weight_negative": "pool.weight_out_of_bounds",
        "pool_weight_not_a_number": "pool.weight_out_of_bounds",
        "pool_weight_boolean": "pool.weight_out_of_bounds",
        "pool_weights_all_zero": "pool.weights_all_zero",
        "pool_no_strata": "pool.strata_malformed",
        "pool_no_cases": "pool.cases_out_of_bounds",
        "pool_more_cases_than_the_pool": "pool.cases_out_of_bounds",
        "pool_box_reversed": "pool.box_malformed",
        "pool_box_unknown_input": "pool.box_unknown_input",
    }
    assert set(found) == set(expected)
    for name, code in expected.items():
        assert found[name]["status"] == "REFUSED", name
        assert code in found[name]["issues"], (name, found[name])
    honest = l2._families()["l2_pool_sources_and_weights"]
    assert d.accepted(d.variant_gate(2)(honest.trained))
    assert d.accepted(d.variant_gate(2)(honest.held_out))


def test_seams_say_why_they_are_not_run(level):
    seams = {s.name: s for s in LEVELS[level].ADAPTER.level_families()}
    assert {s.state for s in seams.values()} == {b.NOT_RUN}
    assert "parameter.unknown" in seams[f"l{level}_compute_accounting"].reason
    if level == 2:
        assert "l2_pool_selection" not in seams  # P1 and P2 run (battery-l2-v2)
        assert "P3" in seams["l2_pool_budget_evasion"].reason
        assert "P4" in seams["l2_pool_distribution_chasing"].reason
        assert "M2" in seams["l2_divergence"].reason
    else:
        assert "N2" in seams["l3_instability"].reason


@pytest.mark.parametrize("fault", ["nan", "inf"])
def test_injected_nonfinite_is_the_candidates_own(level, fault, monkeypatch):
    import jax

    from carbon.agent_campaign.graphite import experiment
    from carbon.battery import development_rebuild, level2_training, level3_training
    from carbon.battery.practice import PracticeSet
    from carbon.battery.worker import WorkerFailure

    trainer = {2: level2_training, 3: level3_training}[level]
    original = trainer.train
    scale = float(fault)

    def faulty(*, apply, **rest):
        def injected(*args, **kwargs):
            out = apply(*args, **kwargs)
            return jax.tree_util.tree_map(lambda o: o * scale, out)

        return original(apply=injected, **rest)

    monkeypatch.setattr(trainer, "train", faulty)
    honest = next(iter(LEVELS[level]._families().values())).trained
    found = d._dv().compile_development(honest, d.variant(level))
    record = development_rebuild.record(found.reconstruction)
    backend = d._backend()
    practice = PracticeSet.load(experiment.REPOSITORY)
    inputs = {c: r["inputs"] for c, r in zip(practice.case_ids, practice.records)}
    try:
        state, _stats = backend.reconstruct(None, found.construction, d.SEED, record)
        predictions = backend.infer(None, state, inputs)
    except WorkerFailure as failure:
        assert failure.candidate is True, failure.code
        return
    rows, summary = b._frozen_rule().score(predictions)
    assert not summary["eligible"]
    assert all(row["state"] != "FAILED_INFRA" for row in rows)


def test_rebuild_and_surface(level):
    adapter = LEVELS[level].ADAPTER
    honest = next(iter(LEVELS[level]._families().values())).trained
    made = adapter.rebuild(honest)
    assert isinstance(made, b.Rebuilt)
    assert made.detail["rebuild"] == "rebuild: CPU-verified only"
    outside = d.strategy({"width": 16, "depth": 1, "steps": 48}, composition_graphs="x")
    assert isinstance(adapter.rebuild(outside), b.Unrebuildable)
    assert adapter.admission_refusals(outside)
    assert adapter.permission_inventory()["profile"] == f"level-{level}"
    assert adapter.surface()["variant_version"] == d.variant(level).version


FAMILY_CASES = [(2, "l2_pool_sources_and_weights"), (3, "l3_cross_level_fields")]


def _session_attempt(identity, strategy_json, design):
    import json as _json

    from carbon.agent_campaign.attack import analysis
    from carbon.agent_campaign.attack.identity import digest

    return analysis.Attempt(
        identity=identity,
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=analysis.PREFIX + "start_research_task",
        arguments={
            "action": "check_design",
            "arguments_json": _json.dumps({"design": design}),
            "kind": "workspace",
            "strategy_json": strategy_json,
        },
        result={"status": "MINER_PATH_REFUSED"},
        withheld=None,
        intent_digest=digest(identity.encode()),
        result_digest=digest(b"refused"),
    )


@pytest.mark.parametrize("level,family", FAMILY_CASES)
def test_a_session_attempt_is_judged_never_an_oracle_crash(level, family):
    """Stage-A L2-L4 (2026-10-12): verify hands these adapters a view without
    a `value` (they inherit Level 0's `attempt_input`), and the generic oracle
    crashed (`oracle_crashed:TypeError`, INFRA). The value is now the
    attempt's strategy, unwrapped as the rebuild unwraps it."""
    import json as _json

    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import verify

    adapter = core.ADAPTERS[("battery-fastcharge-ageing-development-v1", level)]
    design = {"strategy": {"schema_version": "1.0",
              "challenge_id": "battery-fastcharge-ageing-development-v1",
              "backbone": "mlp", "parameters": {}}}  # fmt: skip
    for attempt in (
        _session_attempt("epoch-1-tool-003", _json.dumps(design), design),
        _session_attempt("epoch-1-tool-004", None, design),
    ):
        verdict = verify.verify(attempt, adapter, family=family)
        assert not str(verdict.reason).startswith("oracle_crashed"), verdict
        assert verdict.outcome != verify.INFRA, verdict


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_the_attacker_declares_the_family_per_attempt(level):
    """Levels 1-4 take the family an attempt declares (`[family: <name>]` in
    its hypothesis) when the level lists it as reachable by a session
    attempt; anything else maps to the level's surface, as before."""
    import json as _json

    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import analysis

    adapter = core.ADAPTERS[("battery-fastcharge-ageing-development-v1", level)]
    names = [f.name for f in adapter.families()]
    design = {"strategy": {"schema_version": "1.0",
              "challenge_id": "battery-fastcharge-ageing-development-v1",
              "backbone": "mlp", "parameters": {}}}  # fmt: skip

    def mapped(hypothesis):
        attempt = _session_attempt("epoch-1-tool-001", _json.dumps(design), design)
        attempt = attempt.__class__(
            **{
                **attempt.__dict__,
                "arguments": {**attempt.arguments, "hypothesis": hypothesis},
            }
        )
        return analysis.family_of(attempt, adapter)

    surface = mapped("no declaration")
    assert surface in names
    reachable = [n for n in names if mapped(f"probe [family: {n}] here") == n]
    expected = {1: 4, 2: 5, 3: 5, 4: 7}[level]
    assert len(reachable) == expected, reachable
    assert mapped("[family: no_such_family]") == surface
    # Two different declarations are no declaration.
    assert mapped(f"[family: {names[0]}] [family: {names[-1]}]") == surface
    # Off the construction door, nothing is declared into a family.
    off = _session_attempt("epoch-1-tool-002", None, design)
    off = off.__class__(**{**off.__dict__, "tool": analysis.PREFIX + "get_challenge_info",
                           "arguments": {"hypothesis": f"[family: {names[0]}]"}})  # fmt: skip
    assert analysis.family_of(off, adapter) == analysis.UNASSIGNED


@pytest.mark.parametrize(
    "level,family",
    [
        (2, "l2_off_family"),
        (2, "l2_slot_ablation"),
        (3, "l3_off_lane"),
        (3, "l3_slot_ablation"),
    ],
)
def test_a_declared_family_judges_the_attempt_never_crashes(level, family):
    import json as _json

    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import verify

    adapter = core.ADAPTERS[("battery-fastcharge-ageing-development-v1", level)]
    design = {"strategy": {"schema_version": "1.0",
              "challenge_id": "battery-fastcharge-ageing-development-v1",
              "backbone": "mlp", "parameters": {}}}  # fmt: skip
    attempt = _session_attempt("epoch-1-tool-003", _json.dumps(design), design)
    verdict = verify.verify(attempt, adapter, family=family)
    assert verdict.outcome != verify.INFRA, verdict
