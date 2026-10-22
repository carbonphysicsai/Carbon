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
from carbon.challenge_registry.direct import catalog_recipe
from carbon.development_session import bundle_construction_worker as bundle_worker
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


def test_2_2_is_2_1_plus_the_catalog_and_nothing_else_moves():
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
    # The limits differ only by version and the exact catalog served.
    limits = dict(new["construction_limits_document"])
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
    assert new["practice_case_ids"] == old["practice_case_ids"]
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
    assert document["models"]["graph_training_adapter"] is None
    assert "needs its own pair-identity receipt" in document["models"]["note"]
    assert document["examples"] == []
    assert document["task"] == HUMAN_INPUT
    template = catalog_recipe(BATTERY_CATALOG, version="2.2")
    assert template["source"]["catalog_id"] is None
    assert template["challenge"] == catalog_version.construction_kit(BATTERY, "2.2")


def test_an_empty_catalog_campaign_is_refused_before_anything_starts(
    tmp_path, monkeypatch
):
    empty(monkeypatch, BATTERY, "2.2")
    campaign = campaign_for(CHALLENGE)
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    assert catalog_campaign.CATALOG_EMPTY == "battery_catalog_catalog_empty"
    with pytest.raises(ValueError, match="battery_catalog_catalog_empty"):
        asyncio.run(campaign.prepare(args, ledger=None, campaign=campaign))
    assert list(tmp_path.iterdir()) == []


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
    # Catalog only: no graph adapter source.
    assert [selector for selector, *_ in sources] == ["direct_catalog"]
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


def test_a_graph_recipe_is_refused_before_anything_runs(tmp_path, monkeypatch):
    inject(monkeypatch, BATTERY, "2.2")
    monkeypatch.setattr(
        bundle_worker,
        "reconstruct_and_infer_public",
        lambda *a, **k: pytest.fail("nothing runs"),
    )
    item, _ = _practice(tmp_path)
    kit = catalog_version.construction_kit(BATTERY, "2.2")
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": {}},
            "train_use": {"dataset": "train", "train_fraction": 1.0},
            "initial_state": None,
        },
        "output": {"format": "array", "interface_digest": kit["interface_digest"]},
    }
    with pytest.raises(ValueError, match="battery_catalog_graph_unserved"):
        item("battery-graph-0001", recipe)


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
