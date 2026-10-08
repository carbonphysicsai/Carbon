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
4. Seams are NOT_RUN and say why: pool selection is not in the registered
   variant (P1-P4), no in-surface recipe diverged (M2, N2), and the cost
   calculator refuses development recipes (M1's finding).
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

from carbon.agent_campaign.attack import adapters, engine
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


def test_seams_say_why_they_are_not_run(level):
    seams = {s.name: s for s in LEVELS[level].ADAPTER.level_families()}
    assert {s.state for s in seams.values()} == {b.NOT_RUN}
    assert "parameter.unknown" in seams[f"l{level}_compute_accounting"].reason
    if level == 2:
        reason = seams["l2_pool_selection"].reason
        assert all(row in reason for row in ("P1", "P2", "P3", "P4"))
        assert "battery-l2-spectral-v1" in reason
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
