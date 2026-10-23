"""Battery 2.2 (the Validator, 2026-10-22): Battery 2.1 plus the backbone
catalog binding, by its own adapter beside the pinned Battery modules
(`carbon.battery.catalog_version`), on the shared direct campaign
(`carbon.direct_campaign`, `spec.BATTERY_CATALOG`).

Registered like F08 1.4 / F02 2.3; its catalog lists nothing until each entry
has its pair-identity receipt, and its campaign refuses to start until then; a
catalog recipe practises through the shared bundle worker (stubbed here, as
the F08/F02 tests stub it; its custody is the worker's own tests') and is
scored with Battery's own practice measurement. Battery 1.0, 2.0 and 2.1 keep
every byte of their identity, and no pinned Battery module is edited."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from direct_catalog_stand_in import STAND_IN, empty, inject
from test_lp_prod_research_tools import ledger

from carbon.backbone_catalog import listing, pipeline, served
from carbon.battery import catalog_campaign, catalog_version, implementation_versions
from carbon.battery import construction_bundle_material as cbm
from carbon.challenge_kit import physical_material
from carbon.challenge_kit import served_versions as sv
from carbon.challenge_registry import campaigns, describe, registry
from carbon.challenge_registry.campaigns import campaign_for, implemented_campaigns
from carbon.challenge_registry.direct import catalog_recipe, graph_recipe
from carbon.development_session import bundle_construction_worker as bundle_worker
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.direct_campaign import contracts as direct_contracts
from carbon.direct_campaign import research as direct_research
from carbon.direct_campaign.spec import BATTERY_CATALOG, HUMAN_INPUT, SPECS
from carbon.reconstruction.served_recipe_contract import registered

BATTERY = "battery-fastcharge-ageing-development-v1"
CHALLENGE = {"id": BATTERY, "version": "2.2"}
REPOSITORY = Path(__file__).resolve().parents[2]
#: Battery's served kits and served recipe contracts before 2.2 (the base
#: branch's values): unchanged by it.
KITS = {
    "1.0": "sha256:fa0ecc04db3c1094db510db218fd7fda934abe98657360619a633210c0fe79a4",
    "2.0": "sha256:8539c67e3685422625aa951b425b3bbd337682a926ebb9ca424b44dc5378f748",
    "2.1": "sha256:8202e99b53ef09ff3b30bd68f352e7bde2b995a70e3808878a74a63cadc5c177",
}
CONTRACTS = {
    "1.0": "sha256:2ef46d42a07e3485a8ccd4ce90bf1e60b3fccb8f2fbef223ddb3160681271312",
    "2.0": "sha256:67a32e3231b65dcc9014bac317a2ec41a90b07339a61798c677d05d1d25cfec8",
    "2.1": "sha256:04e85ef22cc99ad77c9f574a10082c429f0fa70d664cb143f3e625dd111c9134",
}
TRAIN = "sha256:3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
INTERFACE = "sha256:6719a714c8c51b1dc14836cb813f78e9eef6a518f53f84e3263f86c0888e0e19"
#: sha256 of the pinned Battery modules (`implementation_versions.MODULES`)
#: and the staged graph module on the base branch: 2.2 edits none of them.
PINNED = {
    "domain.py": "4268c9a222ab9082a15bf9d34202b4db0a6d7eb943c91840543f3317491e9da4",
    "recipes.py": "115209fc1ab4cd3a62f50ad6d1c2d12eb8e77e71553ad29aef5ff9b450d7da5e",
    "training.py": "421b8f36a1e90156240ff3a1ede07acac316f821c554be9a400a25de15f70338",
    "torch_training.py": (
        "9fdb83f8b2f117f047f7f383a5acd52a18fc94391f7a2b0df8490bc953d786fe"
    ),
    "torch_families.py": (
        "558c33b30028bbc4026feb166afcea2b43802d15af3161af8bc103ada2cab591"
    ),
    "direct_graph.py": "59599c63800f39bfa00f8c1858c56781a41e77d4fa8954ae39ae84dceeeaa8e8",
}


# --- registration ------------------------------------------------------------


def test_battery_2_2_is_a_catalog_version_serving_v7():
    assert (BATTERY, "2.2") in sv.CATALOG and (BATTERY, "2.2") in sv.V7
    assert sv.serves_catalog(BATTERY, "2.2") and sv.serves_v7(BATTERY, "2.2")
    assert not sv.step_caps(BATTERY, "2.2")
    # 2.1 binds no catalog, as before.
    assert not sv.serves_catalog(BATTERY, "2.1")
    assert "2.2" in cbm.VERSIONS and catalog_version.BASES == {"2.2": "2.1"}
    assert physical_material.is_registered(BATTERY, "2.2")
    assert not physical_material.is_registered(BATTERY, "2.1")


def test_the_registry_lists_battery_2_2_with_the_shared_catalog_gpu_profile():
    (entry,) = [
        e for e in registry.entries() if (e.challenge_id, e.version) == (BATTERY, "2.2")
    ]
    assert entry.status == registry.IMPLEMENTED
    motor = next(
        e
        for e in registry.entries()
        if (e.challenge_id, e.version) == ("electric-motor-magnetics", "1.3")
    )
    assert entry.profiles[1] == motor.profiles[1]
    # Battery's id resolves to 1.0 as before; 2.2 resolves to its own campaign.
    assert campaigns.challenge_ref(BATTERY) == {"id": BATTERY, "version": "1.0"}
    assert campaign_for({"id": BATTERY, "version": "1.0"}).key.version == "1.0"
    campaign = campaign_for(CHALLENGE)
    assert (campaign.key.challenge_id, campaign.key.version) == (BATTERY, "2.2")
    assert campaign.practice_provenance == "BATTERY_PUBLIC_PRACTICE"
    assert campaign.feedback_schema == "carbon.battery_catalog.permitted-feedback.v1"
    assert campaign.construction_kit() == catalog_version.construction_kit(
        BATTERY, "2.2"
    )
    assert campaign.construction_bundle_material()["challenge_key"] == campaign.key
    assert (BATTERY, "2.2") in {
        (e.challenge_id, e.version) for e, _ in implemented_campaigns()
    }
    assert SPECS[BATTERY] is BATTERY_CATALOG
    assert catalog_campaign.SPEC.versions == ("2.2",)


def test_there_is_no_default_version():
    for other in (None, "1.0", "2.1", "9.9"):
        with pytest.raises(ValueError, match="direct campaign version"):
            catalog_campaign.key_for(other)
    with pytest.raises(ValueError, match="no default version"):
        catalog_campaign.research_key()
    with pytest.raises(ValueError, match="direct campaign version"):
        campaigns._battery_catalog_direct("2.1")


def test_the_receiver_contract_and_worker_policy_accept_2_2():
    material = cbm.versioned_material("2.2")
    kit = material["construction_kit"]
    assert registered(BATTERY, "2.2").digest not in CONTRACTS.values()
    digest = bundle_worker.verify_direct_resource_policy(
        {
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        },
        material["construction_limits_document"],
    )
    assert digest == kit["construction_limits_digest"]


# --- the catalog binding, and 2.1 unchanged ----------------------------------


def test_2_2_is_2_1_plus_the_catalog_and_graph_adapter_and_nothing_else_moves():
    new = cbm.versioned_material("2.2")
    old = cbm.versioned_material("2.1")
    for version, limits in KITS.items():
        assert (
            cbm.versioned_material(version)["construction_kit"][
                "construction_limits_digest"
            ]
            == limits
        )
        assert registered(BATTERY, version).digest == CONTRACTS[version]
    assert new["construction_kit"]["train_digest"] == TRAIN
    assert new["construction_kit"]["interface_digest"] == INTERFACE
    assert old["construction_kit"]["interface_digest"] == INTERFACE
    assert new["construction_kit"]["construction_limits_digest"] not in KITS.values()
    # The limits differ only by version, the exact catalog served and
    # Battery's graph adapter (the Validator's ruling (a)).
    from carbon.development_session import battery_graph_adapter

    limits = dict(new["construction_limits_document"])
    assert limits.pop("graph_training_adapter") == (
        battery_graph_adapter.adapter_block(BATTERY, "2.2")
    )
    assert limits.pop("backbone_catalog") == {
        "schema": served.SCHEMA,
        "digest": served.digest(BATTERY, "2.2"),
    }
    assert limits.pop("challenge") == CHALLENGE
    base = dict(old["construction_limits_document"])
    base.pop("challenge")
    assert limits == base
    # Exam bank, TRAIN, physics and allowlist are 2.1's.
    assert np.array_equal(new["practice_inputs"], old["practice_inputs"])
    assert np.array_equal(
        new["practice_reference"], old["practice_reference"], equal_nan=True
    )
    # The receiver's canonical case names, by position; the bank's own ids,
    # in order, beside them (Test Lead's B22 fault: "ev4:..." ids).
    assert new["practice_case_sources"] == old["practice_case_ids"]
    assert new["practice_case_ids"] == tuple(
        f"bank-{index:04d}" for index in range(len(old["practice_case_ids"]))
    )
    assert new["train"] == old["train"]
    assert new["physics_digest"] == old["physics_digest"]
    assert new["allowlist_digest"] == old["allowlist_digest"]
    # The catalog's tested-digest check reads 2.1's TRAIN and interface.
    assert pipeline._served_kit_digests(BATTERY, "2.2") == {
        "train_digest": TRAIN,
        "interface_digest": INTERFACE,
    }
    with pytest.raises(ValueError, match="served material"):
        cbm.construction_limits_document_for("2.2", rows=1)


def test_no_pinned_battery_module_is_edited():
    assert "catalog_version.py" not in implementation_versions.MODULES
    assert "catalog_campaign.py" not in implementation_versions.MODULES
    for name in (*implementation_versions.MODULES, "direct_graph.py"):
        path = REPOSITORY / "carbon" / "battery" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == PINNED[name], name


# --- the catalog lists nothing until receipts --------------------------------


def test_the_catalog_and_toolbox_list_nothing_until_receipts(monkeypatch):
    from scripts.dev.miner_launchpad import toolbox

    empty(monkeypatch, BATTERY, "2.2")
    assert listing.entries(BATTERY, "2.2") == []
    assert served.document(BATTERY, "2.2")["entries"] == {}
    toolbox._catalog_recipes.cache_clear()
    assert toolbox._catalog_recipes(BATTERY, "2.2") == "[]"
    toolbox._catalog_recipes.cache_clear()
    document = describe(BATTERY, "2.2")
    assert document["models"]["rebuildable"] == []
    assert document["models"]["graph_training_adapter"]["base_version"] == "2.1"
    assert document["models"]["note"].startswith("No backbone is installable yet")
    assert document["models"]["note"] == document["examples_note"]
    assert document["examples"] == []
    assert document["task"] == HUMAN_INPUT
    template = catalog_recipe(BATTERY_CATALOG, version="2.2")
    assert template["source"]["catalog_id"] is None
    assert template["challenge"] == catalog_version.construction_kit(BATTERY, "2.2")


def test_an_empty_catalog_campaign_starts_on_the_graph_route_and_says_why(
    tmp_path, monkeypatch
):
    # Round 8b: while the catalog waits on its checks, 2.2 can practise the
    # miner's own graph; the toolbox says why it offers no ready recipe.
    from scripts.dev.miner_launchpad import toolbox

    empty(monkeypatch, BATTERY, "2.2")
    campaign = campaign_for(CHALLENGE)
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    granted = SimpleNamespace(root=tmp_path, admission="a-grant")
    with pytest.raises(ValueError, match="never consumes a development grant"):
        asyncio.run(campaign.prepare(args, ledger=granted, campaign=campaign))
    assert catalog_campaign.CATALOG_EMPTY == "battery_catalog_catalog_empty"
    note = describe(BATTERY, "2.2")["examples_note"]
    assert note.startswith("No backbone is installable yet")
    assert "practise your own graph" in note
    toolbox._sources.cache_clear()
    toolbox._catalog_recipes.cache_clear()
    try:
        document = toolbox.build(CHALLENGE, direct=True)
    finally:
        toolbox._sources.cache_clear()
        toolbox._catalog_recipes.cache_clear()
    assert document["examples"] == [] and document["catalog"] == []
    assert document["examples_note"] == note


def test_with_an_offered_entry_the_refusal_is_not_the_catalogs(tmp_path, monkeypatch):
    inject(monkeypatch, BATTERY, "2.2")
    campaign = campaign_for(CHALLENGE)
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    granted = SimpleNamespace(root=tmp_path, admission="a-grant")
    with pytest.raises(ValueError, match="never consumes a development grant"):
        asyncio.run(campaign.prepare(args, ledger=granted, campaign=campaign))


# --- research parts ----------------------------------------------------------


def test_the_research_parts_take_battery_s_interface_and_the_catalog_only():
    parts = direct_research.challenge_parts(BATTERY_CATALOG, "2.2")
    assert parts.key == campaign_for(CHALLENGE).key
    assert parts.contracts.key == parts.key
    assert parts.scaffold_strategy["source"]["kind"] == "catalog"
    with direct_contracts.keyed(
        BATTERY_CATALOG, direct_contracts.key_for(BATTERY_CATALOG, "2.2")
    ):
        physical, _candidate, _training = direct_contracts.authored_contracts(
            BATTERY_CATALOG
        )
        sources = direct_contracts.direct_sources(BATTERY_CATALOG)
        view = catalog_campaign.research_view()
    assert [f.field_id for f in physical.causal_inputs] == [
        "c1",
        "c2",
        "t_amb_c",
        "soc0",
    ]
    outputs = {f.field_id: f for f in physical.required_physical_quantities}
    assert list(outputs) == [
        "voltage_v",
        "temperature_c",
        "plating_margin_v",
        "capacity_ah",
    ]
    assert [a.extent.fixed_extent for a in outputs["voltage_v"].shape_contract] == [121]
    assert outputs["plating_margin_v"].shape_contract == ()
    # Both routes: Battery's graph adapter and the catalog.
    assert [selector for selector, *_ in sources] == [
        "direct_adapter",
        "direct_catalog",
    ]
    assert [o.kind for o in view.outputs] == [
        "time_series",
        "time_series",
        "scalar",
        "checkpoint_vector",
    ]
    assert [c for c, _ in view.components] == [
        "voltage",
        "temperature",
        "plating",
        "capacity",
    ]


# --- practice ----------------------------------------------------------------


def _rows(material):
    """The bank's references where present, else the first practice row:
    finite float64 rows of the interface's width."""
    reference = np.array(material["practice_reference"], dtype=np.float64)
    first = reference[material["public_practice_rows"][0]]
    missing = ~np.isfinite(reference).all(axis=1)
    reference[missing] = first
    return reference.tolist()


def _practice(tmp_path):
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    resolved = []
    item = catalog_campaign.BatteryCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        version="2.2",
        resolver=lambda ref: resolved.append(ref) or SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )
    return item, resolved


def test_a_catalog_recipe_runs_through_the_shared_bundle_worker(tmp_path, monkeypatch):
    inject(monkeypatch, BATTERY, "2.2")
    material = physical_material.bundle_material(BATTERY, "2.2")
    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=_rows(material)),
        )

    monkeypatch.setattr(bundle_worker, "reconstruct_and_infer_public", fake)
    item, resolved = _practice(tmp_path)
    recipe = catalog_recipe(BATTERY_CATALOG, STAND_IN, version="2.2")
    result = item("battery-catalog-0001", recipe)
    (call,) = calls
    assert call["seed"] == 0
    assert call["recipe"].to_dict()["source"]["kind"] == "bundle"
    assert resolved[0].bundle_digest == (
        call["recipe"].to_dict()["source"]["bundle_ref"]["bundle_digest"]
    )
    kit = material["construction_kit"]
    assert call["challenge_binding"] == {
        "challenge_id": BATTERY,
        "challenge_version": "2.2",
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }
    assert call["limits_document"] == material["construction_limits_document"]
    assert np.array_equal(call["inputs"], material["practice_inputs"])
    assert call["inputs"].dtype == np.float64
    assert call["expected_output_dtype"] == "float64"
    assert call["expected_output_shape"] == material["expected_output_shape"]
    assert result["schema"] == "carbon.battery_catalog.direct-practice-feedback.v1"
    assert result["provenance"] == "BATTERY_PUBLIC_PRACTICE"
    assert result["challenge"] == CHALLENGE
    assert result["source_kind"] == "catalog" and result["catalog_id"] == STAND_IN
    assert result["official_eligible"] is False and result["final_exam"] is False
    summary = result["summary"]
    # Battery's own practice measurement on its 200 public PRACTICE rows; the
    # references themselves score as a perfect model.
    assert summary["n_cases"] == 200 and summary["n_scored"] == 200
    assert summary["eligible"] is True and summary["gate_failures"] == {}
    assert summary["score"] == pytest.approx(0.0, abs=1e-9)
    assert set(summary["components"]) == {
        "voltage",
        "temperature",
        "plating",
        "capacity",
    }
    assert summary["cases"] == len(material["practice_case_ids"])
    assert summary["error_scale"]["record"] == catalog_version.PRACTICE_RECORD


def test_a_graph_recipe_runs_through_battery_s_graph_adapter(tmp_path, monkeypatch):
    # The Validator's ruling (a): graphs through Battery's adapter, on 2.1's
    # graph route (its custody and parity: test_battery_graph_adapter.py).
    from carbon.development_session import battery_graph_adapter
    from carbon.development_session import construction_recipe as construction
    from carbon.development_session import direct_graph_construction_worker as graph

    material = physical_material.bundle_material(BATTERY, "2.2")
    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=_rows(material)),
        )

    monkeypatch.setattr(graph, "reconstruct_and_infer_graph_public", fake)
    monkeypatch.setattr(
        construction, "graph_envelope_from_workspace", lambda *a, **k: b"{}"
    )
    monkeypatch.setattr(
        bundle_worker,
        "reconstruct_and_infer_public",
        lambda *a, **k: pytest.fail("no bundle runs"),
    )
    item, _ = _practice(tmp_path)
    recipe = graph_recipe(
        BATTERY_CATALOG, "sha256:" + "a" * 64, version="2.2", training={"steps": 16}
    )
    result = item("battery-graph-0001", recipe)
    (call,) = calls
    assert (
        call["adapter_id"] == battery_graph_adapter.SPECS[(BATTERY, "2.2")].adapter_id
    )
    assert call["train"] == material["train"]
    assert np.array_equal(call["inputs"], material["practice_inputs"])
    assert call["limits_document"] == material["construction_limits_document"]
    assert call["seed"] == 0
    assert result["source_kind"] == "graph"
    assert result["summary"]["n_scored"] == 200
    # A setting the base version's route refuses is refused before anything runs.
    bad = graph_recipe(
        BATTERY_CATALOG, "sha256:" + "a" * 64, version="2.2", training={"steps": 1}
    )
    with pytest.raises(RecipeRefused, match="battery_graph_training_value_invalid"):
        item("battery-graph-0002", bad)
    assert len(calls) == 1


def test_outputs_must_be_finite_rows_of_the_interface(tmp_path, monkeypatch):
    inject(monkeypatch, BATTERY, "2.2")
    material = physical_material.bundle_material(BATTERY, "2.2")
    rows = _rows(material)
    rows[0][0] = float("nan")
    state = "sha256:" + "5" * 64
    monkeypatch.setattr(
        bundle_worker,
        "reconstruct_and_infer_public",
        lambda ledger_, **kwargs: SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=rows),
        ),
    )
    item, _ = _practice(tmp_path)
    recipe = catalog_recipe(BATTERY_CATALOG, STAND_IN, version="2.2")
    with pytest.raises(ValueError, match="battery_catalog_practice_output_invalid"):
        item("battery-catalog-0002", recipe)


# --- the launch version: offered, with a runnable example ---------------------


def test_the_launch_offers_2_2_as_battery_s_newest_version():
    from scripts.dev.miner_launchpad import capabilities

    listed = [
        entry
        for entry in capabilities.control_center(None)["challenges"]
        if entry["challenge_id"] == BATTERY and entry["implemented"]
    ]
    versions = [tuple(int(p) for p in e["version"].split(".")) for e in listed]
    # Latest-version-only: the page offers each Challenge's newest version.
    assert max(versions) == (2, 2)
    assert {e["version"] for e in listed} == {"1.0", "2.2"}


def test_describe_offers_a_catalog_example_practice_accepts(monkeypatch):
    from carbon.development_session.research_service import (
        construction_recipe_issues,
    )
    from scripts.dev.miner_launchpad import toolbox

    inject(monkeypatch, BATTERY, "2.2")
    document = describe(BATTERY, "2.2")
    (example,) = document["examples"]
    recipe = example["recipe"]
    assert recipe["source"]["catalog_id"] == STAND_IN
    key = campaign_for(CHALLENGE).key
    assert construction_recipe_issues(recipe, key) == ()
    toolbox._catalog_recipes.cache_clear()
    try:
        offered = json.loads(toolbox._catalog_recipes(BATTERY, "2.2"))
    finally:
        toolbox._catalog_recipes.cache_clear()
    assert [item["catalog_id"] for item in offered] == [STAND_IN]
    assert construction_recipe_issues(offered[0]["recipe"], key) == ()
    # The first landed entry is the toolbox's example by itself (as Cooling
    # 1.3's entries gave it one): no release beyond the entry, and the empty
    # catalog's note is gone.
    assert "examples_note" not in document
    toolbox._sources.cache_clear()
    toolbox._catalog_recipes.cache_clear()
    try:
        built = toolbox.build(CHALLENGE, direct=True)
    finally:
        toolbox._sources.cache_clear()
        toolbox._catalog_recipes.cache_clear()
    assert built["examples"] == [recipe]
    assert "examples_note" not in built
    assert [item["catalog_id"] for item in built["catalog"]] == [STAND_IN]
    # The older versions offer no catalog.
    for version in ("1.0", "2.0", "2.1"):
        assert listing.entries(BATTERY, version) == []


def test_the_description_serves_both_routes_and_no_coming_line(monkeypatch):
    # The Validator's ruling (a) built: catalog backbones and your own graphs.
    from carbon.challenge_registry.known_limitations import known_limitations
    from carbon.development_session import battery_graph_adapter

    assert not any(
        "graphs coming" in line for line in known_limitations(BATTERY, "2.2")
    )
    inject(monkeypatch, BATTERY, "2.2")
    document = describe(BATTERY, "2.2")
    assert document["models"]["graph_training_adapter"] == (
        battery_graph_adapter.adapter_block(BATTERY, "2.2")
    )
    assert "stage a graph" in document["models"]["note"]
    assert document["execution"]["recipe"].endswith("source kind catalog or graph")
    template = graph_recipe(BATTERY_CATALOG, version="2.2")
    assert template["source"] == {"kind": "graph", "submission_digest": None}
    assert template["procedure"]["train_use"] == {
        "dataset": "battery-pinned-train-v1",
        "train_fraction": 1.0,
        "curriculum": "none",
    }
    assert template["output"]["format"] == "carbon.battery.raw-numeric.v1"


def test_the_receiver_serves_2_2_with_canonical_case_ids():
    # Test Lead's B22 pair batch (2026-10-22): the receiver refused 2.2 at
    # normal_retention_preflight, practice_case_ids not canonical.
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.registry.model import validate_canonical_identifier

    material = cbm.versioned_material("2.2")
    for case in (*material["practice_case_ids"], *material["train_case_ids"]):
        validate_canonical_identifier(case, "case")
    assert any(":" in case for case in material["practice_case_sources"])
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    assert discovery.info.challenge_key.version == "2.2"
    assert tuple(discovery.info.practice_case_ids) == material["practice_case_ids"]
