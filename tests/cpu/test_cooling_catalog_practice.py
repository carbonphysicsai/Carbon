"""Cooling catalog practice (OWNER-BACKBONE-CATALOG-01): the recipe is expanded to
its Carbon bundle and rebuilt by the receiver's own call with the receiver's
build inputs; the 100 public PRACTICE rows are queried, mapped back to Cooling's
outputs by the interface's target slices and scored with Cooling's scorer. The
C-03 build is injected here; its custody is the bundle worker's own tests'. The
catalog entry is a stand-in (`cooling_catalog_stand_in`): no Cooling entry is
tested yet."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
from cooling_catalog_stand_in import STAND_IN, empty, inject
from test_lp_prod_research_tools import ledger

from carbon.challenge_registry.cold_plate import catalog_recipe
from carbon.cold_plate import catalog_practice, domain
from carbon.cold_plate.challenge import PublicMaterial
from carbon.cold_plate.practice import PROVENANCE, PracticeSet, score_practice
from carbon.development_session import bundle_construction_worker as worker

ROOT = "."


def _native_rows():
    """Each public PRACTICE reference laid out as the numeric interface does:
    peak_c, the 30-segment profile_c, pressure_drop_pa."""
    rows = []
    for record in PracticeSet.load(ROOT).records:
        outputs = record["outputs"]
        rows.append(
            [outputs["peak_c"], *outputs["profile_c"], outputs["pressure_drop_pa"]]
        )
    return rows


@pytest.fixture
def practice(tmp_path, monkeypatch):
    inject(monkeypatch)
    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=_native_rows()),
        )

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    meter = ledger(tmp_path / "ledger")
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    resolved = []
    item = catalog_practice.CoolingCatalogPractice(
        ledger=meter,
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        version="1.2",
        root=ROOT,
        resolver=lambda ref: resolved.append(ref) or SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )
    return item, calls, resolved, meter


def test_a_catalog_recipe_runs_as_its_bundle_on_the_public_practice_inputs(practice):
    item, calls, resolved, _ = practice
    recipe = catalog_recipe(STAND_IN, version="1.2")
    result = item("cooling-catalog-0001", recipe)
    (call,) = calls
    assert call["seed"] == 0 and call["recipe"].to_dict()["source"]["kind"] == "bundle"
    assert (
        call["inference_image"] is item.parent
        and call["construction_parent"] is item.parent
    )
    assert (
        resolved[0].bundle_digest
        == call["recipe"].to_dict()["source"]["bundle_ref"]["bundle_digest"]
    )
    # The 100 public PRACTICE inputs, in the interface's input order, are both
    # the probe and the query; 32 predicted columns per case.
    records = PracticeSet.load(ROOT).records
    expected = np.asarray(
        [[record["inputs"][name] for name in domain.INPUTS] for record in records],
        dtype="<f8",
    )
    assert np.array_equal(call["inputs"], expected)
    assert call["example"] is call["inputs"]
    assert call["expected_output_shape"] == (100, 2 + domain.PROFILE_SEGMENTS)
    assert call["expected_output_dtype"] == "<f8"
    assert result["provenance"] == PROVENANCE == "COLD_PLATE_PUBLIC_PRACTICE"
    assert result["catalog_id"] == STAND_IN
    assert result["recipe"] == recipe
    assert result["official_eligible"] is False and result["final_exam"] is False
    # PRACTICE-SAFETY-01's safety block (Validator, 2026-10-21), read through
    # the provider; the feedback schema is versioned for it.
    assert result["schema"] == catalog_practice.FEEDBACK_SCHEMA
    assert result["schema"].endswith(".v2")
    assert result["safety"]["schema"] == "carbon.practice-safety-feedback.v1"


def _optimistic_rows():
    """Each reference run 5 C cool at half the pressure drop: a model the
    safety block flags (PRACTICE-SAFETY-01's own optimist)."""
    return [
        [row[0] - 5.0, *(t - 5.0 for t in row[1:-1]), row[-1] * 0.5]
        for row in _native_rows()
    ]


@pytest.mark.parametrize("kind", ["reference", "optimistic"])
def test_the_safety_block_is_level_0_practices_for_the_same_predictions(
    practice, monkeypatch, tmp_path, kind
):
    from test_practice_safety_feedback import _recipe, _runner, _Workspace

    from carbon.cold_plate import research
    from carbon.development_session import research_workspace

    item, _, _, _ = practice
    rows = _native_rows() if kind == "reference" else _optimistic_rows()
    if kind == "optimistic":
        monkeypatch.setattr(
            worker,
            "reconstruct_and_infer_public",
            lambda ledger_, **kwargs: SimpleNamespace(
                build=SimpleNamespace(state_digest="sha256:" + "5" * 64),
                inference=SimpleNamespace(
                    state_digest="sha256:" + "5" * 64, predictions=rows
                ),
            ),
        )
    result = item("cooling-catalog-0006", catalog_recipe(STAND_IN, version="1.2"))
    # Level 0 practice (`ColdPlatePractice`) on the same predictions.
    records = PracticeSet.load(ROOT).records
    slices = item._material()["interface_document"]["target_slices"]
    predictions = {
        record["case_id"]: catalog_practice._outputs(row, slices)
        for record, row in zip(records, rows, strict=True)
    }
    monkeypatch.setattr(research_workspace, "ResearchWorkspace", _Workspace)
    level0 = research.ColdPlatePractice(
        ledger=SimpleNamespace(root=tmp_path / "level0"),
        owner="o",
        image=SimpleNamespace(image_id="sha256:" + "1" * 64),
        root=ROOT,
        runner=_runner(predictions, research.digest),
    )
    level0.compile = lambda strategy: (None, _recipe({"id": "cooling"}))
    expected = level0("task-1", {"strategy": "fixture"})["safety"]
    assert result["safety"] == expected
    metrics = expected["metrics"]
    if kind == "optimistic":
        assert metrics["C1"]["false_feasible"] > 0
    else:
        assert metrics["C1"]["rate"] == 0.0 and metrics["C2"]["rate"] == 0.0
    # No public PRACTICE case id leaves in the safety block.
    text = json.dumps(result["safety"])
    assert not [r["case_id"] for r in records if r["case_id"] in text]


def test_the_columns_map_back_to_coolings_outputs_in_the_interfaces_order(practice):
    # Predicting each reference exactly scores exactly as the references do
    # through Cooling's own scorer: a column swap would not.
    item, _, _, _ = practice
    result = item("cooling-catalog-0002", catalog_recipe(STAND_IN, version="1.2"))
    records = PracticeSet.load(ROOT).records
    direct = {record["case_id"]: dict(record["outputs"]) for record in records}
    _rows, summary = score_practice(
        direct, PracticeSet.load(ROOT), PublicMaterial.load(ROOT)
    )
    assert result["summary"] == summary
    assert summary["n_gate_failed"] == 0 and summary["score"] == pytest.approx(0.0)


def test_a_catalog_practice_record_supports_a_freeze(practice):
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_campaign import trial_supports_selection
    from carbon.development_session.research_tasks import PublicResearchExecutor

    item, _, _, meter = practice
    recipe = catalog_recipe(STAND_IN, version="1.2")
    result = item("cooling-catalog-0003", recipe)
    PublicResearchExecutor(
        ledger=meter, owner="alice", image=None, public_material=None, practice=None
    )
    assert not trial_supports_selection(meter, "alice", recipe)
    body = canonical(result)
    with meter.db() as db:
        db.execute(
            "INSERT OR REPLACE INTO research_results VALUES(?,?,?,?)",
            ("alice", "cooling-catalog-0003", body, digest(body)),
        )
    assert trial_supports_selection(meter, "alice", recipe)
    assert not trial_supports_selection(meter, "other", recipe)


def test_an_uninstalled_entry_is_not_served_here_before_anything_runs(
    tmp_path, monkeypatch
):
    inject(monkeypatch)

    def missing(ref):
        raise FileNotFoundError("verified child missing")

    item = catalog_practice.CoolingCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=SimpleNamespace(image_id="sha256:" + "7" * 64),
        cache_root=tmp_path / "cache",
        version="1.2",
        resolver=missing,
        parents=SimpleNamespace(for_bundle=lambda _ref: None),
    )
    assert item.backend_refusal(catalog_recipe(STAND_IN, version="1.2")) == ()


def test_a_level0_strategy_is_not_a_catalog_recipe(practice):
    item, calls, _, _ = practice
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "chip-cold-plate",
        "backbone": "kernel_ridge",
        "parameters": {},
    }
    with pytest.raises(ValueError):
        item("cooling-catalog-0004", strategy)
    assert calls == []


def test_with_an_empty_catalog_nothing_runs(tmp_path, monkeypatch):
    # No entry offered: the unfilled template names none and is refused
    # before anything is built.
    empty(monkeypatch)
    calls = []
    monkeypatch.setattr(
        worker, "reconstruct_and_infer_public", lambda *a, **k: calls.append(k)
    )
    item = catalog_practice.CoolingCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=SimpleNamespace(image_id="sha256:" + "7" * 64),
        cache_root=tmp_path / "cache",
        version="1.2",
        resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: None),
    )
    template = catalog_recipe(version="1.2")
    assert template["source"]["catalog_id"] is None
    with pytest.raises(ValueError):
        item("cooling-catalog-0005", template)
    assert item.installed() == ()
    assert calls == []


def test_only_a_catalog_version_has_catalog_practice(tmp_path):
    for version in ("1.0", "1.1", None):
        with pytest.raises(ValueError, match="cooling catalog version"):
            catalog_practice.CoolingCatalogPractice(
                ledger=None,
                owner="alice",
                parent=None,
                cache_root=tmp_path,
                version=version,
            )


# --- two CPU parents: each entry builds on its own runtime's parent -----------


@pytest.mark.parametrize("eligible", [True, False])
def test_the_cpu_parent_is_served_only_when_docker_finds_it(
    tmp_path, monkeypatch, eligible
):
    from test_direct_parents import torch_image

    from carbon.reconstruction.worker import docker_runtime

    seen = []

    def doctor(*, image_id, image_identity):
        seen.append(image_id)
        return SimpleNamespace(eligible=eligible)

    monkeypatch.setattr(docker_runtime, "doctor", doctor)
    item = catalog_practice.CoolingCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=torch_image(),
        cache_root=tmp_path / "cache",
        version="1.2",
        resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
    )
    assert item.parents().runtimes() == (
        ("python-cpu-py311", "torch-cpu-py311") if eligible else ("torch-cpu-py311",)
    )
    assert seen == [torch_image().base_image_digest]
