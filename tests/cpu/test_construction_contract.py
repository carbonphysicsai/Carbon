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
4. Graph combinations carry a prospective graph record and require a verified
   workspace for reconstruction. Detailed graph execution, objective conflict,
   staging and costing controls live in test_battery_composed_graph*.py.
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
from dataclasses import replace
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


def test_graph_combination_has_a_record_and_cannot_train_without_documents():
    found = dc.compile(
        strategy("spectral", composition_graphs="sha256:" + "0" * 64),
        check_budget=False,
    )
    assert found.record["schema"] == composed_worker.GRAPH_SCHEMA
    assert development_rebuild.uses_graph(found.record)
    with pytest.raises(ImportError, match="level4_submission_documents_not_staged"):
        development_rebuild.build_in_process(found.construction, found.record)


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


@pytest.mark.parametrize(
    "removed",
    [
        None,
        atk.FIELD,
        "muon_spectral",
        "pool_selection",
        "quasi_newton_family",
        "line_search",
    ],
)
def test_the_staged_program_and_the_in_process_rebuild_agree(
    tmp_path, backend, removed
):
    requested = strategy("l1", "spectral", "pool", "l3")
    if removed is not None:
        del requested["parameters"][removed]
    composed = dc.compile(requested)
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
    described = dc.answer(strategy("l3", **graph), check_budget=False)
    assert described["status"] == "ACCEPTED" and described["rebuild"] == "composed"
    # Structural/offline admission is not evidence of available graph documents
    # or budget acceptance; the missing-document control above remains binding.
    path = tmp_path / "strategy.json"
    path.write_text(json.dumps(strategy("l1", "pool")))
    assert dc.main([str(path), "--no-budget"]) == 0


# S1-R1: a claimed digest is not an authenticated descriptor.
@pytest.mark.parametrize(
    "tamper",
    [
        "digest",
        "variant_digest",
        "permission",
        "applicability",
        "bounds",
        "signed",
        "base_sequence",
    ],
)
def test_supplied_composition_must_match_every_registered_descriptor(tamper):
    registered = dc.load(BATTERY)
    l1, *others = registered.variants
    if tamper == "digest":
        changed = replace(registered, digest="sha256:" + "0" * 64)
    elif tamper == "base_sequence":
        # Python equality alone considers an integer equal to this float.
        changed = replace(
            registered, base_record_sequence=float(registered.base_record_sequence)
        )
    else:
        if tamper == "signed":
            changed_l1 = dv.variant(BATTERY, 1, "signed")
        elif tamper == "variant_digest":
            document = l1.document()
            document["authority"] += " fixture tamper"
            changed_l1 = replace(l1, canonical_document=dv._canonical(document))
        else:
            field = l1.fields()[atk.FIELD]
            changes = {
                "permission": {"capability_id": "objective.fixture_undeclared"},
                "applicability": {"applies_to": ("fixture_family",)},
                "bounds": {"bounds_json": "{}"},
            }[tamper]
            changed_field = replace(field, **changes)
            changed_l1 = replace(
                l1,
                widened=tuple(changed_field if w == field else w for w in l1.widened),
            )
        changed = replace(registered, variants=(changed_l1, *others))
    with pytest.raises(dv.VariantRefused) as refused:
        dc.compile(strategy("l1"), changed, check_budget=False)
    assert refused.value.code == dc.UNREGISTERED
    assert dc.answer(strategy("l1"), changed, check_budget=False)["status"] == "REFUSED"
    assert (
        dc.compile(strategy("l1"), registered, check_budget=False).composition_digest
        == registered.digest
    )


def test_supplied_composition_requires_exact_type():
    registered = dc.load(BATTERY)

    class Lookalike(dc.Composition):
        pass

    for supplied in ({"digest": registered.digest}, Lookalike(**registered.__dict__)):
        with pytest.raises(TypeError, match="a Composition is required"):
            dc.compile(strategy(), supplied, check_budget=False)


@pytest.fixture
def advanced_registries(tmp_path, monkeypatch):
    """Prospective registry cutover fixture; no committed document is edited."""
    policies = tmp_path / "variants"
    compositions = tmp_path / "compositions"
    policies.mkdir()
    compositions.mkdir()
    for source in Path(dv.SHIPPED_DIR).glob("*.json"):
        (policies / source.name).write_bytes(source.read_bytes())
    for source in dc.DIRECTORY.glob("*.json"):
        (compositions / source.name).write_bytes(source.read_bytes())
    old = dc.load(BATTERY)
    previous_graph = old.variants[-1]
    graph = previous_graph.document()
    graph["version"] = "battery-l4-graph-fixture-next"
    next_digest = dv.digest_of(graph)
    (policies / (graph["version"] + ".json")).write_text(
        json.dumps(graph), encoding="utf-8", newline="\n"
    )
    registry = json.loads((policies / "registry.json").read_text(encoding="utf-8"))
    registry["versions"][graph["version"]] = next_digest
    for entry in registry["current"]:
        if entry["challenge"] == BATTERY and entry["level"] == 4:
            entry["version"] = graph["version"]
    (policies / "registry.json").write_text(
        json.dumps(registry), encoding="utf-8", newline="\n"
    )
    document = json.loads(
        (compositions / (old.version + ".json")).read_text(encoding="utf-8")
    )
    document["version"] = "battery-construction-fixture-next"
    document["composes"][-1].update(version=graph["version"], digest=next_digest)
    (compositions / (document["version"] + ".json")).write_text(
        json.dumps(document), encoding="utf-8", newline="\n"
    )
    registry = json.loads((compositions / "registry.json").read_text(encoding="utf-8"))
    registry["versions"][document["version"]] = dv.digest_of(document)
    registry["current"][BATTERY] = document["version"]
    (compositions / "registry.json").write_text(
        json.dumps(registry), encoding="utf-8", newline="\n"
    )
    monkeypatch.setattr(dv._registry, "DEVELOPMENT_VARIANT_DIR", policies)
    monkeypatch.setattr(dc, "DIRECTORY", compositions)
    return old, dc.load(BATTERY), policies, compositions


def test_historical_composition_survives_current_variant_advance(advanced_registries):
    old, new, _, _ = advanced_registries
    assert dc.load(BATTERY, version=old.version) == old
    assert new.variants[-1].version != old.variants[-1].version
    assert (
        dc.compile(strategy("l1", "pool"), old, check_budget=False).composition_digest
        == old.digest
    )
    assert (
        dc.compile(strategy("l1", "pool"), new, check_budget=False).composition_digest
        == new.digest
    )
    # Ordinary admission is deliberately still current-only.
    with pytest.raises(dv.VariantRefused) as refused:
        dv.registered(old.variants[-1].digest, BATTERY)
    assert refused.value.code == dv.UNREGISTERED


@pytest.mark.parametrize(
    "tamper", ["document", "unregistered_digest", "sequence", "level"]
)
def test_historical_composition_pin_tampering_refuses(advanced_registries, tamper):
    old, _, policies, compositions = advanced_registries
    if tamper == "document":
        path = policies / (old.variants[-1].version + ".json")
        document = json.loads(path.read_text(encoding="utf-8"))
        document["authority"] += " fixture tamper"
        path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    else:
        path = compositions / (old.version + ".json")
        document = json.loads(path.read_text(encoding="utf-8"))
        if tamper == "unregistered_digest":
            document["composes"][-1]["digest"] = "sha256:" + "0" * 64
        elif tamper == "sequence":
            document["base_contract"]["record_sequence"] += 1
        else:
            document["composes"][-1]["level"] = 3
        path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
        registry_path = compositions / "registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["versions"][old.version] = dv.digest_of(document)
        registry_path.write_text(json.dumps(registry), encoding="utf-8", newline="\n")
    with pytest.raises(dv.VariantRefused):
        dc.load(BATTERY, version=old.version)


def test_budget_recompiles_the_selected_historical_composition(
    advanced_registries, monkeypatch
):
    from carbon.battery.training_budget import BatteryAdapter
    from carbon.reconstruction import challenge_contracts

    old, new, _, _ = advanced_registries
    seen = []
    original = dc.compile

    def compile_selected(recipe, composition=None, **kwargs):
        seen.append(None if composition is None else composition.digest)
        return original(recipe, composition, **kwargs)

    def budget(item, recipe, level=0):
        if level == 0:  # the unchanged base compile also checks its own budget
            return
        assert type(level) is dc.Composition and level.digest == old.digest
        BatteryAdapter(REPOSITORY)._development(recipe, level)

    monkeypatch.setattr(dc, "compile", compile_selected)
    monkeypatch.setattr(challenge_contracts, "check_compute_budget", budget)
    original(strategy("l1", "pool"), old)
    assert seen == [old.digest] and new.digest not in seen


# S1-R3: observe the compiler/record/rebuild route, not pre-made trainer flags.
ACTIVE_FIELDS = (
    atk.FIELD,
    "muon_spectral",
    "pool_selection",
    "quasi_newton_family",
    "line_search",
)


def _full_and_without(field=None):
    recipe = strategy("l1", "spectral", "pool", "l3")
    if field is not None:
        del recipe["parameters"][field]
    return dc.compile(recipe, check_budget=False)


def _compiled_fit(compiled, backend):
    return backend.reconstruct(None, compiled.construction, 7, compiled.record)[1][
        "params_sha256"
    ]


@pytest.fixture(scope="module")
def compiled_effects(backend):
    full = _full_and_without()
    expected = _compiled_fit(full, backend)
    assert _compiled_fit(full, backend) == expected
    removed = {
        field: _compiled_fit(_full_and_without(field), backend)
        for field in ACTIVE_FIELDS
    }
    return expected, removed


@pytest.mark.parametrize("field", ACTIVE_FIELDS)
def test_each_compiled_field_changes_the_composed_rebuild(compiled_effects, field):
    expected, removed = compiled_effects
    assert expected != removed[field], field


def _assert_requested_pool(compiled):
    import numpy as np

    from carbon.battery import level2_worker
    from carbon.battery.challenge import PublicMaterial

    train = PublicMaterial.load(REPOSITORY).train
    requested = level2_worker.level2_record(compiled.reconstruction)["pool"]
    expected = pools.subset(train, requested["case_ids"])
    actual = development_rebuild.training_data(compiled.record, train)
    assert tuple(actual.case_ids) == tuple(expected.case_ids), "requested pool identity"
    for field in ("q", "v"):
        np.testing.assert_array_equal(getattr(actual, field), getattr(expected, field))


def test_compiled_pool_selection_preserves_requested_identity_and_content():
    _assert_requested_pool(_full_and_without())


@pytest.mark.parametrize(
    "broken",
    ["expression", "routine", "line_search", "ignored_pool", "substituted_pool"],
)
def test_effect_controls_detect_broken_composed_record_routing(
    monkeypatch, backend, broken
):
    """Mutate only the new composed record route; normal per-level tests cannot catch this."""
    from carbon.battery.challenge import PublicMaterial

    original = composed_worker.composed_record

    def corrupted(reconstruction):
        record = original(reconstruction)
        if not composed_worker.is_composed(record):
            return record
        record = dict(record)
        if broken == "expression":
            record["expression"] = None
        elif broken == "routine":
            record["numerics"] = {**record["numerics"], "routine": "lbfgs"}
        elif broken == "line_search":
            record["numerics"] = {**record["numerics"], "line_search": "strong_wolfe"}
        elif broken == "ignored_pool":
            record["pool"] = None
        else:
            requested = set(record["pool"]["case_ids"])
            train = PublicMaterial.load(REPOSITORY).train
            others = [case for case in train.case_ids if case not in requested]
            count = len(record["pool"]["case_ids"])
            assert len(others) >= count
            record["pool"] = {**record["pool"], "case_ids": others[:count]}
        return record

    monkeypatch.setattr(composed_worker, "composed_record", corrupted)
    if broken in {"ignored_pool", "substituted_pool"}:
        with pytest.raises(AssertionError, match="requested pool identity"):
            _assert_requested_pool(_full_and_without())
    else:
        field = {
            "expression": atk.FIELD,
            "routine": "quasi_newton_family",
            "line_search": "line_search",
        }[broken]
        full = _compiled_fit(_full_and_without(), backend)
        without = _compiled_fit(_full_and_without(field), backend)
        with pytest.raises(AssertionError):
            assert full != without, field
