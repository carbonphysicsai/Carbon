"""CONSTRUCTION-CONTRACT-01 S1: one construction contract over the whole 0-4 plan.

The owner, 2026-10-13: "a construction contract that can rebuild anything at all
on our 0-4 plan." Claims tested:

1. A single-level recipe compiles under the composition exactly as under its own
   level's variant (the same reconstruction and record), so nothing that builds
   today changes. A Level 0 recipe stays Level 0.
2. Combinations are accepted and rebuilt: across levels (L1+L2, L1+L3, L2+L3),
   inside a level (L2's SpecMuon and pool selection), and all of Levels 1-3 in
   one recipe. The record is composed and the level is derived and described
   in plain words, never used as a gate.
3. Each field keeps its own containment inside a combination: Level 3 stays a
   menu, Level 2's SpecMuon still needs Muon, and a field's own bounds still
   refuse.
4. The rebuild is the gate: a combination Carbon cannot rebuild yet (a Level 4
   graph beside another field, until S2) is refused with
   `construction_rebuild_unavailable`, naming the fields.
5. A combination is costed, not refused as uncostable.
6. The staged worker program and the in-process rebuild train the same
   combination to the same parameters, and a rebuild repeats.
7. The composition document is pinned by digest; v1-v3 are untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.battery import composed_worker, development_rebuild, pools
from carbon.battery.worker import (
    RECONSTRUCT_PROGRAM,
    DirectBackend,
    reconstruct_files,
)
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_variants as dv

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
BASE = {
    "width": 16,
    "depth": 1,
    "steps": 48,
    "polish_steps": 6,
    "optimizer_family": "muon",
}
(POOL_V1,) = pools.registered()
FIELDS = {
    "l1": {atk.FIELD: atk.VALID["valid_robust_l2"]},
    "spectral": {"muon_spectral": True},
    "pool": {
        "pool_selection": {
            "pool_version": POOL_V1,
            "strata": {"train": 1.0},
            "box": {"t_amb_c": [10.0, 35.0]},
            "cases": 120,
        }
    },
    "l3": {"quasi_newton_family": "bfgs", "line_search": "backtracking"},
}
LEVEL_OF = {"l1": 1, "spectral": 2, "pool": 2, "l3": 3}


def strategy(*names, **parameters):
    made = dict(BASE)
    for name in names:
        made.update(FIELDS[name])
    made.update(parameters)
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": made,
    }


@pytest.fixture(scope="module")
def backend():
    return DirectBackend(REPOSITORY)


def test_the_composition_is_registered_pinned_and_names_each_level():
    composition = dc.load(BATTERY)
    assert composition.version == "battery-construction-v1"
    assert [v.level for v in composition.variants] == [1, 2, 3, 4]
    for variant in composition.variants:
        assert variant == dv.variant(BATTERY, variant.level)
    document = REPOSITORY / "carbon/reconstruction/development_compositions"
    body = json.loads((document / "battery-construction-v1.json").read_text())
    assert dv.digest_of(body) == composition.digest


def test_a_changed_composition_document_is_refused(tmp_path):
    source = REPOSITORY / "carbon/reconstruction/development_compositions"
    for name in ("registry.json", "battery-construction-v1.json"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    body = json.loads((tmp_path / "battery-construction-v1.json").read_text())
    body["authority"] += " (edited)"
    (tmp_path / "battery-construction-v1.json").write_text(json.dumps(body))
    with pytest.raises(dv.VariantRefused) as refused:
        dc.load(BATTERY, directory=tmp_path)
    assert refused.value.code == dc.UNREGISTERED


@pytest.mark.parametrize("name", ["l1", "spectral", "pool", "l3"])
def test_a_single_level_recipe_compiles_exactly_as_under_its_own_variant(name):
    level = LEVEL_OF[name]
    own = dv.compile_development(strategy(name), dv.variant(BATTERY, level))
    composed = dc.compile(strategy(name))
    assert composed.reconstruction == own.reconstruction
    assert composed.construction.recipe_digest == own.construction.recipe_digest
    assert composed.record == development_rebuild.record(own.reconstruction)
    assert not composed_worker.is_composed(composed.record)
    assert composed.level == level


def test_one_levels_own_combination_keeps_that_levels_route():
    """SpecMuon and a pool selection are both Level 2's: the Level 2 variant
    already rebuilds them together, so the composition leaves them on it."""
    own = dv.compile_development(strategy("spectral", "pool"), dv.variant(BATTERY, 2))
    composed = dc.compile(strategy("spectral", "pool"))
    assert composed.record == development_rebuild.record(own.reconstruction)
    assert not composed_worker.is_composed(composed.record)
    assert composed.level == 2


def test_a_level0_recipe_stays_level0():
    composed = dc.compile(strategy())
    assert composed.reconstruction == {} and composed.record is None
    assert composed.derived["level"] == 0 and composed.derived["changes"] == []


@pytest.mark.parametrize(
    "names",
    [
        ("l1", "spectral"),
        ("l1", "l3"),
        ("spectral", "l3"),
        ("pool", "l3"),
        ("l1", "spectral", "pool", "l3"),
    ],
)
def test_a_combination_is_accepted_composed_and_described(names):
    composed = dc.compile(strategy(*names))
    record = composed.record
    assert composed_worker.is_composed(record)
    assert (record["expression"] is not None) == ("l1" in names)
    assert (record["spectral"] is not None) == ("spectral" in names)
    assert (record["pool"] is not None) == ("pool" in names)
    assert (record["numerics"] is not None) == ("l3" in names)
    assert composed.level == max(LEVEL_OF[n] for n in names)
    summary = composed.derived["summary"]
    assert summary.startswith(f"Level {composed.level} (") and "changes" in summary
    binding = composed.development
    assert binding["composition_digest"] == dc.load(BATTERY).digest
    assert set(binding["variants"]) == {str(LEVEL_OF[n]) for n in names}


@pytest.mark.parametrize(
    ("names", "parameters", "code"),
    [
        (("l1",), {"quasi_newton_family": "newton"}, "development.out_of_bounds"),
        (("l1", "l3"), {"line_search": "anything"}, "development.out_of_bounds"),
        (("l1", "spectral"), {"optimizer_family": "adam"}, "development.needs_muon"),
    ],
)
def test_each_field_keeps_its_own_containment_inside_a_combination(
    names, parameters, code
):
    with pytest.raises(dv.VariantRefused) as refused:
        dc.compile(strategy(*names, **parameters))
    assert code in {issue[0] for issue in refused.value.issues}, refused.value.issues


def test_a_combination_carbon_cannot_rebuild_yet_is_refused_naming_its_fields():
    graph = {"composition_graphs": "sha256:" + "0" * 64}
    with pytest.raises(dv.VariantRefused) as refused:
        dc.compile(strategy("spectral", **graph))
    assert refused.value.code == dc.UNAVAILABLE
    assert set(refused.value.issues) == {
        (dc.UNAVAILABLE, "/parameters/composition_graphs"),
        (dc.UNAVAILABLE, "/parameters/muon_spectral"),
    }


def test_a_combination_is_costed_not_refused():
    from carbon.training_budget import cost

    report = cost.cost(BATTERY, strategy("spectral", "pool", "l3"), level=dc.COMPOSED)
    (program,) = report["programs"]
    assert program["cases_per_update"] == 120  # the drawn pool, not TRAIN
    # Level 3's polish is priced at its line search's worst case, so the
    # combination's FLOPs are a number; without Level 3 they wait on a study.
    assert type(report["F4_flops"]) is float and report["F4_flops"] > 0
    single = cost.cost(BATTERY, strategy("spectral"), level=2)
    assert program["step_flops"] != single["programs"][0]["step_flops"]


def test_the_staged_program_and_the_in_process_rebuild_agree(tmp_path, backend):
    composed = dc.compile(strategy("l1", "spectral", "pool", "l3"))
    record = composed.record
    first = backend.reconstruct(None, composed.construction, 7, record)
    second = backend.reconstruct(None, composed.construction, 7, record)
    assert first[0] == second[0] and first[1]["trainer"] == development_rebuild.COMPOSED
    program, files, trainer = development_rebuild.stage(
        record,
        RECONSTRUCT_PROGRAM,
        reconstruct_files(REPOSITORY, composed.construction, 7),
        level1_program=lambda: 1 / 0,
    )
    assert trainer == development_rebuild.COMPOSED
    work, out = tmp_path / "work", tmp_path / "output"
    work.mkdir()
    out.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(program)
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={
            "PYTHONPATH": str(REPOSITORY),
            "JAX_PLATFORMS": "cpu",
            "PATH": "/usr/bin:/bin",
        },
        check=True,
        timeout=900,
    )
    staged = json.loads((out / "fit.json").read_text())
    assert staged["params_sha256"] == first[1]["params_sha256"]


def test_registered_variants_and_their_pins_are_untouched():
    registry = json.loads(
        (
            REPOSITORY
            / "carbon/reconstruction/development_variant_policies/registry.json"
        ).read_text()
    )
    assert "battery-construction-v1" not in registry["versions"]
    for level in (1, 2, 3, 4):
        assert dv.variant(BATTERY, level).version in registry["versions"]


def test_the_answer_says_accepted_or_names_the_refused_fields(tmp_path):
    accepted = dc.answer(strategy("spectral", "l3"), check_budget=False)
    assert accepted["status"] == "ACCEPTED" and accepted["rebuild"] == "composed"
    assert accepted["derived"]["level"] == 3
    graph = {"composition_graphs": "sha256:" + "0" * 64}
    refused = dc.answer(strategy("l3", **graph), check_budget=False)
    assert refused["status"] == "REFUSED" and refused["code"] == dc.UNAVAILABLE
    assert [dc.UNAVAILABLE, "/parameters/composition_graphs"] in refused["issues"]
    path = tmp_path / "strategy.json"
    path.write_text(json.dumps(strategy("l1", "pool")))
    assert dc.main([str(path), "--no-budget"]) == 0
