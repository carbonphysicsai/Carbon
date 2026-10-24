"""Graph route v2 (owner: "No carbon limits please!"; Launchpad brief
LP_GRAPH_ROUTE_V2_BRIEF_20261023, sweep rows L9-L12; Validator ruling in
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022, no-limits binding).

Claims tested, each absence paired with the same check finding a presence:

- every existing version replays byte for byte: its construction kit (TRAIN,
  interface and limits digests, pinned at composite 40 5b1f2928f), its
  served catalog and v1's worker programs;
- each new version (F08 1.5, F02 2.4, Motor 1.4, Cooling 1.4) is its
  predecessor plus the graph adapter v2: the same TRAIN, interface, bank,
  development and sealed evaluation versions (guards that run, never skip);
- F08's TRAIN is chosen by an explicit table that refuses an unknown version;
- the v2 settings: ranges refused before are accepted, the keep list still
  refuses, per-output weights change the loss, a 3+ member ensemble on
  disjoint outputs trains and combines per output, more than four members are
  accepted, an output no member trains is refused;
- the receiver rebuilds and infers a v2 ensemble in its isolated programs,
  float32 (F08) and float64 (Motor), as the in-worker model predicts;
- every offered version passes each registration point and lists its routes;
- the Ladder keys on the evaluation version: a best carries from F08 1.4 to
  1.5 on the same exam, old rows are read through the map, never rewritten.
"""

from __future__ import annotations

import hashlib
import itertools
import os
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import physical_material, served_versions, version_registry
from carbon.development_session import (
    build_refusal_v2,
    direct_graph_construction_worker,
    graph_adapters,
)
from carbon.development_session import physical_graph_adapter_v2 as adapter
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module

posix = pytest.mark.skipif(os.name != "posix", reason="isolated build programs")
F08, F02 = "f08-ribbed-bracket", "f02"
MOTOR, COOLING = "electric-motor-magnetics", "chip-cold-plate"
NEW = sorted(version_registry.keys(graph_adapter="v2"))

#: Every existing version's construction limits digest, as served at
#: composite 40 (5b1f2928f), before graph route v2.
BASE_KITS = {
    (
        COOLING,
        "1.0",
    ): "04ae6257c44346d276b8496e436a2e99ab76b64f6f8b6c0df93a3d9992a28aff",
    (
        COOLING,
        "1.1",
    ): "a314b52829093a795b77f02e5fdf843907f210e08ff3df7736c5c895bef1ee38",
    (
        COOLING,
        "1.2",
    ): "3b322569494155fedaba59f4ad9a7da5ba2d407d302490f007c29c812d472e70",
    (
        COOLING,
        "1.3",
    ): "7df1a6ee7b70140972e11bda20d9e3935c1ce7798d6c2cf90c1b5e249606217c",
    (MOTOR, "1.0"): "bde507459e8665e0f213689675728dbebf33c38eed721492442f4757fdcbbe1d",
    (MOTOR, "1.1"): "5a8a872f2cf5ffd40cd0e07e7057c87cfcb9c98abb6529f2d4361c63b4f2a9b1",
    (MOTOR, "1.2"): "61347c1624700203b4091e5278de68a05a23d30eb24bdebe0538e2981c8db215",
    (MOTOR, "1.3"): "2dac7922486baf6a147705d0fe2a0524840479b2f5d6a43e5e8cfa98c5abe0fc",
    (F02, "2.0"): "df88cb39b0213803cf7c6ad0a7cdc60f9ee55a3418f054d17776e433391dae99",
    (F02, "2.1"): "00f7675fa6600a4c172b8e037b415bea9bcdb5ce5d77cc113d1fe6910b506eb3",
    (F02, "2.2"): "1d6894f7880550b0d06c1ebd9cb1e093fc5ec4af21925cd88cd2ca95106a9b91",
    (F02, "2.3"): "9881ad629acf9df9b839543d4968b938933c7ec03c348242f6278b023bd62e50",
    (F08, "1.0"): "88f56b8af03054a6002e92590784257df52580782b59c7a6bc019c17197725c3",
    (F08, "1.1"): "28a77a5beaf259a73acfa5b807fb5fd683353ee2c7de20ddb5ee155c94c7fb78",
    (F08, "1.2"): "039ec28de20975f0391707bf4cdf5153dacbed65f0bd247f07ab76321879c2ca",
    (F08, "1.3"): "58a1fceb1941bb249e6d32aa516de9e3890565830265e94c52b9e160e6b7dac7",
    (F08, "1.4"): "9e26eb1a372e8f007b031599b1ebab8fc7dd590a2fe1d801276f009aa14b99f8",
}
#: v1's worker programs at 942080f3a and composite 40 (5b1f2928f): graph
#: route v2 only adds beside them.
BASE_PROGRAMS = {
    "BUILD_PROGRAM": "7c97aabcbf7a00298455a4266931b2a49147e015d6616825ab86944cb2b3211e",
    "PHYSICAL_BUILD_PROGRAM": (
        "5f3018c3f1a77cdb77295f4de34233a4069863080a83c1472dd35c6084f99f17"
    ),
    "PHYSICAL_INFER_PROGRAM": (
        "dec3bf54fbaee202ed5f1621a7746e8c7f047d0fcdbc93cde32eacff2558d4de"
    ),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ---- Replay and lineage ---------------------------------------------------


#: The six existing versions whose served catalog digest the catalog freeze
#: moved (frozen catalog 0530c1d41; codex-queue/reports/
#: SERVED_DIGESTS_RC6_FINAL_20261023.json). Each: the cause, the catalog digest
#: it served at rc6 a454e75e5, and its construction limits digest now. The
#: limits document differs from the old one in `backbone_catalog.digest` only
#: (asserted below), and the digest of a catalog that did not move stays.
RELICENSE = "OWNER-CATALOG-LICENCES-01 relicense (08c1465a9)"
MOVED_KITS = {
    (COOLING, "1.2"): (
        RELICENSE,
        "sha256:d21fce9f7ab074e365f566ec7f3646e441f8241f328cddd521a6fea3000ffda5",
        "f6bf90a17128e687a05c66be9baec2b0cfffbb8a794c433d6cf8f90c45d626f6",
    ),
    (COOLING, "1.3"): (
        RELICENSE,
        "sha256:724e814daf2267aeed1038eeada65988b770c254f674c47c7873917144a78add",
        "ba4842de66f3745b6ad32545608d8bc86f78cb794fd4e2095b20b2101a8a9148",
    ),
    (MOTOR, "1.2"): (
        RELICENSE,
        "sha256:3d43a9bb19473f866a193404ab2f339e3ffeae66b7fbbac6ea6164ed9e3e5710",
        "4f92627d50ab071d29828e7172c63f00a2d25bd312587745b7f2dfdadd228653",
    ),
    (MOTOR, "1.3"): (
        RELICENSE,
        "sha256:6bacb58c995b636b152a7645918f10613c1f9ee402ba79dc4610996000519ece",
        "912b1bc71b830ddbfdb5368e7b8ddcc0de4bba0c6a8054f492b8efddaa349863",
    ),
    (F02, "2.3"): (
        RELICENSE,
        "sha256:2ff8b82da0f552f26e2797fa865cd023e638b329adb15f5ce5ac8bc1ba7171b0",
        "8f7c043dc8a69eff83e181868b3b60c3603da8f8c5b9ec3b9568dfb5c4cf8ebf",
    ),
    (F08, "1.4"): (
        RELICENSE,
        "sha256:b934bba02176ec06593e5cb77cea312298fbc83fd0e840153b9f7330bc0b38b3",
        "746a0666ee74c51d2fbfdb9667a090ca90bf8f3a86b16e8a5d823d146c91730f",
    ),
}


@pytest.mark.parametrize("key", sorted(BASE_KITS))
def test_every_existing_version_s_kit_is_byte_identical(key):
    """Every existing version keeps its kit bytes, except the six whose catalog
    digest moved: for those only `backbone_catalog.digest` differs, and putting
    the old catalog digest back reproduces the old limits digest exactly."""
    from carbon.backbone_catalog import listing
    from carbon.development_session.profile import canonical, digest

    kit = physical_material.construction_kit(*key)
    if key not in MOVED_KITS:
        # A version with no catalog entries cannot move with the catalog.
        assert listing.entries(*key) == []
        assert kit["construction_limits_digest"] == "sha256:" + BASE_KITS[key]
        return
    _cause, old_catalog, new_kit = MOVED_KITS[key]
    assert kit["construction_limits_digest"] == "sha256:" + new_kit
    assert new_kit != BASE_KITS[key]
    document = physical_material._public(key[0]).construction_limits_document(*key)
    assert document["backbone_catalog"]["digest"] != old_catalog
    restored = {
        **document,
        "backbone_catalog": {**document["backbone_catalog"], "digest": old_catalog},
    }
    assert digest(canonical(restored)) == "sha256:" + BASE_KITS[key]


def test_the_catalog_freeze_moved_exactly_the_versions_it_names():
    """Zero-entry versions are unmoved; the six existing versions with entries
    moved; the four graph route v2 versions are new (their pins are in
    test_v2_rebuild_wall)."""
    from carbon.backbone_catalog import listing

    with_entries = {key for key in BASE_KITS if listing.entries(*key)}
    assert with_entries == set(MOVED_KITS)


def test_v1_worker_programs_and_staged_modules_keep_their_bytes():
    for name, pinned in BASE_PROGRAMS.items():
        program = getattr(direct_graph_construction_worker, name)
        assert _sha(program.encode()) == pinned, name
    staged = direct_graph_construction_worker.PHYSICAL_STAGED_MODULES
    assert not any(name.endswith("_v2") for name in staged)


@pytest.mark.parametrize("key", NEW)
def test_a_new_version_is_its_predecessor_s_material(key):
    """Validator (a)(2): the new version's TRAIN and interface equal its
    predecessor's, and so do its bank and its evaluation versions."""
    from carbon.scoring import physical_adapters, sealed_versions

    cid, version = key
    previous = version_registry.entry(cid, version).predecessor
    new = physical_material.bundle_material(cid, version)
    old = physical_material.bundle_material(cid, previous)
    assert new["construction_kit"]["train_digest"] == (
        old["construction_kit"]["train_digest"]
    )
    assert new["train"] == old["train"]

    def interface(document):
        return {k: v for k, v in document.items() if k != "challenge"}

    assert interface(new["interface_document"]) == interface(old["interface_document"])
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import dev_grid

    grid = dev_grid.kind(cid, version) is not None
    if not grid:
        assert np.array_equal(new["practice_inputs"], old["practice_inputs"])
        assert np.array_equal(new["practice_reference"], old["practice_reference"])
    else:
        # New version, pre-publish, dev-pack v2 (Validator 2026-10-23): the
        # development bank is the predecessor's cells plus interleaved public probes.
        bank = physical_pack.development_bank(cid, version)
        cells = [
            row
            for row, cohort in zip(new["practice_inputs"], bank["cohorts"], strict=True)
            if cohort != "probe_response"
        ]
        new_cells = sorted(map(tuple, np.asarray(cells).tolist()))
        old_rows = sorted(map(tuple, np.asarray(old["practice_inputs"]).tolist()))
        if cid == MOTOR:
            # Motor (M2): the PRACTICE cohort and the 8 x 6 decision cells, all of them
            # rows of the predecessor's 90-row bank (the 12 pilot rows are not carried).
            assert set(new_cells) <= set(old_rows) and len(new_cells) == 78
        else:
            assert new_cells == old_rows
        assert len(new["practice_inputs"]) > len(old["practice_inputs"])
    assert new["physics_digest"] == old["physics_digest"]
    new_adapter = physical_adapters.adapter(cid, version)
    old_adapter = physical_adapters.adapter(cid, previous)
    assert new_adapter is not None and old_adapter is not None
    if grid:
        assert new_adapter.EVALUATION_VERSION == (
            f"{dev_grid.kind(cid, version)}-dual-development-grid-v2"
        )
    else:
        assert new_adapter.EVALUATION_VERSION == old_adapter.EVALUATION_VERSION
    assert sealed_versions.evaluation_version(cid, version) == (
        sealed_versions.evaluation_version(cid, previous)
    )
    # Only the construction limits differ: the graph adapter v2.
    limits = new["construction_limits_document"]
    assert limits["graph_training_adapter"]["schema"] == adapter.ADAPTER_SCHEMA
    assert limits["challenge"] == {"id": cid, "version": version}


def test_the_registry_declares_each_new_version_in_full():
    """Each graph route v2 version is written out, never read through its
    predecessor: every field but its identity, pack version, adapter, catalog
    entries, lineage and rebuild wall equals the predecessor's."""
    assert {key: version_registry.entry(*key).predecessor for key in NEW} == {
        (COOLING, "1.4"): "1.3",
        (F02, "2.4"): "2.3",
        (F08, "1.5"): "1.4",
        (MOTOR, "1.4"): "1.3",
    }
    own = {
        "version",
        "pack_version",
        "graph_adapter",
        "catalog_entries_from",
        "predecessor",
        # Its 30-minute rebuild wall (OWNER-SANDBOX-REBUILD-WALL-01).
        "rebuild_wall_seconds",
    }
    from carbon.scoring import dev_grid

    for cid, version in NEW:
        new = version_registry.entry(cid, version)
        old = version_registry.entry(cid, new.predecessor)
        # Dev-pack v2: a dev-grid version names its own development evaluation
        # (new version, pre-publish; Validator 2026-10-23).
        own_here = own | (
            {"development_evaluation"} if dev_grid.kind(cid, version) else set()
        )
        # F08 1.5 and F02 2.4 carry their own approved facts: their predecessor's with the exam-safety
        # edits (OWNER-PUBLISH-WHAT-IS-TESTED-01).
        if (cid, version) in ((F08, "1.5"), (F02, "2.4")):
            own_here = own_here | {"facts"}
        for field in new.__dataclass_fields__:
            if field not in own_here:
                assert getattr(new, field) == getattr(old, field), (cid, field)
        assert new.graph_adapter == "v2" and new.pack_version != old.pack_version
        assert served_versions.serves_catalog(cid, version)
        assert served_versions.serves_v7(cid, version)
        assert physical_material.is_registered(cid, version)
    with pytest.raises(version_registry.UnregisteredVersion):
        version_registry.entry(F08, "1.6")
    assert version_registry.find(F08, "1.6") is None


def _scorer_tables():
    from carbon.challenge_validator import cooling_hidden
    from carbon.scoring import (
        battery_dual_pack,
        battery_sealed_dual_pack,
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        f02_dual_pack,
        f02_sealed_dual_pack,
        f08_dual_pack,
        f08_sealed_dual_pack,
        motor_dual_pack,
        motor_sealed_dual_pack,
    )

    development, sealed = {}, {}
    for module in (f08_dual_pack, f02_dual_pack, motor_dual_pack, battery_dual_pack):
        for version, entry in module.VERSIONS.items():
            development[(module.CHALLENGE, version)] = tuple(entry)
    for module in (cooling_dual_pack, cooling_encoded_dual_pack):
        for version, entry in module.VERSIONS.items():
            development[(module.CHALLENGE, version)] = tuple(entry)
    # Dev-pack v2: a dev-grid version's development pack is graded by the sealed v2 grader
    # under its own development evaluation version (`scoring.dev_grid`).
    from carbon.scoring import dev_grid

    for key in dev_grid.GRID_KINDS:
        variant = dev_grid.adapter(*key)
        development[key] = (variant.EVALUATION_VERSION, variant.CASE_ID)
    # Scoring v2: F08, F02 and Motor are graded by their sealed grid graders.
    for module in (
        f08_sealed_dual_pack,
        f02_sealed_dual_pack,
        motor_sealed_dual_pack,
        battery_sealed_dual_pack,
    ):
        for version, entry in module.VERSIONS.items():
            sealed[(module.CHALLENGE, version)] = entry[0]
    sealed[(cooling_hidden.CHALLENGE_ID, cooling_hidden.CHALLENGE_VERSION)] = (
        cooling_hidden.EVALUATION_VERSION
    )
    for version, value in cooling_dual_pack.SEALED_VERSIONS.items():
        sealed[(cooling_dual_pack.CHALLENGE, version)] = value
    for version in cooling_encoded_dual_pack.VERSIONS:
        variant = cooling_encoded_dual_pack.sealed_adapter(version)
        if variant is not None:
            sealed[(cooling_dual_pack.CHALLENGE, version)] = variant.EVALUATION_VERSION
    return development, sealed


def test_every_served_version_resolves_through_the_registry():
    """The Lead (2026-10-23): one registry; every served version resolves
    through it, and the scorers' own tables (inside their producer identity)
    agree with what it declares."""
    from carbon.challenge_kit import physical_pack
    from carbon.challenge_kit.served_versions import _known
    from carbon.scoring import physical_adapters

    development, sealed = _scorer_tables()
    served = (
        served_versions.STEP2
        | served_versions.CATALOG
        | served_versions.V7
        | served_versions.EXISTING
    )
    assert served == set(version_registry.VERSIONS)
    for key, entry in version_registry.VERSIONS.items():
        assert _known(*key) == key
        assert development.get(key) == entry.development_evaluation, key
        assert sealed.get(key) == entry.sealed_evaluation, key
        assert physical_pack.PACK_VERSIONS[key] == entry.pack_version
        if key[0] != version_registry.BATTERY:
            adapter_ = physical_adapters.adapter(*key)
            assert (adapter_ is not None) == (entry.development_evaluation is not None)
            # The cooling encoded scorer exactly where rows are encoded.
            if key[0] == COOLING:
                from carbon.scoring import cooling_encoded_dual_pack

                assert (key[1] in cooling_encoded_dual_pack.VERSIONS) == (
                    entry.output_encoding is not None
                )
        assert graph_adapters.serves_graph(*key) == (entry.graph_adapter is not None)
    # Development and sealed tables name no version the registry does not.
    # Battery 2.2 stays in its pinned scorer and is not served
    # (OWNER-BATTERY-OUT-OF-LAUNCH-01).
    development.pop((version_registry.BATTERY, "2.2"), None)
    sealed.pop((version_registry.BATTERY, "2.2"), None)
    assert set(development) <= set(version_registry.VERSIONS)
    assert set(sealed) <= set(version_registry.VERSIONS)


def test_versions_naming_the_same_train_serve_the_same_bytes():
    seen = {}
    for (cid, version), entry in version_registry.VERSIONS.items():
        if cid == version_registry.BATTERY:
            continue
        digest = physical_material.construction_kit(cid, version)["train_digest"]
        seen.setdefault(entry.train, set()).add(digest)
    assert all(len(digests) == 1 for digests in seen.values()), seen
    assert len(seen) == 6


def test_f08_train_is_an_explicit_table_that_refuses_unknown_versions():
    from carbon.challenge_kit import f08_train

    assert set(f08_train.TRAIN_FOR_VERSION) == set(f08_train.CHALLENGE_VERSIONS)
    assert f08_train.CHALLENGE_VERSIONS == version_registry.versions(F08)
    for version, train in f08_train.TRAIN_FOR_VERSION.items():
        loaded = f08_train.load_public_train(version)
        expected = (
            f08_train.TRAIN_SHA256 if train == "v1" else (f08_train.TRAIN_V2_SHA256)
        )
        assert loaded["provenance"]["train_sha256"] == "sha256:" + expected, version
    with pytest.raises(ValueError):
        f08_train.load_public_train("1.6")


#: The catalog's entry counts per graph route v2 version, exact: moved only by
#: the catalog freeze's single re-pin (Validator 2026-10-23). `v2.*` ids exist
#: only on these versions.
CATALOG_COUNTS = {
    (MOTOR, "1.4"): (78, 46),
    (COOLING, "1.4"): (50, 45),
    (F08, "1.5"): (44, 44),
    (F02, "2.4"): (45, 45),
}


def test_graph_route_v2_versions_offer_their_predecessor_s_entries_and_their_own_v2_entries():
    """A catalog entry's receipt binds TRAIN and interface digests; Motor and
    Cooling 1.4's equal 1.3's, so 1.3's entries are offered on 1.4, plus the
    version's own `v2.*` entries. F08 1.5 and F02 2.4 name their version in the
    interface, so they offer only `v2.*` entries. No older version offers one."""
    from carbon.backbone_catalog import listing

    for cid in (MOTOR, COOLING):
        ids = {e["catalog_id"] for e in listing.entries(cid, "1.4")}
        inherited = {e["catalog_id"] for e in listing.entries(cid, "1.3")}
        assert {i for i in ids if not i.startswith("v2.")} == inherited
        assert inherited
        kit = physical_material.construction_kit(cid, "1.4")
        old = physical_material.construction_kit(cid, "1.3")
        assert kit["train_digest"] == old["train_digest"]
        assert kit["interface_digest"] == old["interface_digest"]
    for (cid, version), (total, v2) in CATALOG_COUNTS.items():
        ids = [e["catalog_id"] for e in listing.entries(cid, version)]
        assert (len(ids), sum(i.startswith("v2.") for i in ids)) == (total, v2)
    for cid, version in _offered():
        if (cid, version) not in CATALOG_COUNTS:
            assert not any(
                e["catalog_id"].startswith("v2.") for e in listing.entries(cid, version)
            ), (cid, version)


# ---- Settings ------------------------------------------------------------


def _recipe(key, configuration=None, *, fraction=1.0, digest=None, use=None):
    recipe = graph_adapters.graph_recipe(
        *key, digest or "sha256:" + "0" * 64, configuration=configuration
    )
    if use is not None:
        recipe["procedure"]["train_use"] = use
    else:
        recipe["procedure"]["train_use"]["train_fraction"] = fraction
    return ConstructionRecipe.from_dict(recipe)


def _refused(key, configuration=None, **kwargs):
    with pytest.raises(RecipeRefused) as raised:
        adapter.training_settings(_recipe(key, configuration, **kwargs))
    return raised.value.code


def test_the_default_recipe_is_one_member_on_every_output():
    for key in NEW:
        settings = adapter.training_settings(_recipe(key))
        spec = adapter.SPECS[key]
        assert settings["output_weights"] == [1.0] * spec.outputs
        (member,) = settings["ensemble"]
        assert member["outputs"] == list(range(spec.outputs))
        assert member["training"]["optimizer_family"] == "adamw"


#: Each value v1 refused (its DEVELOPMENT ranges, `physical_graph_adapter`),
#: now accepted: only structure bounds them.
OPENED = [
    ("batch_size", 128),
    ("learning_rate", 0.5),
    ("weight_decay", 0.5),
    ("adam_epsilon", 0.1),
    ("optimizer_family", "lion"),
    ("learning_rate_curve", "cosine"),
    ("loss", "huber"),
    ("clip_norm", 1.0),
    ("steps", 1),
]


@pytest.mark.parametrize("name, value", OPENED)
def test_a_range_v1_refused_is_accepted(name, value):
    from carbon.development_session import physical_graph_adapter as v1

    v1_recipe = graph_adapters.graph_recipe(F08, "1.4", "sha256:" + "0" * 64)
    v1_recipe["procedure"]["configuration"] = {"training": {name: value}}
    with pytest.raises(RecipeRefused):
        v1.training_settings(ConstructionRecipe.from_dict(v1_recipe))
    settings = adapter.training_settings(
        _recipe((F08, "1.5"), {"training": {name: value}})
    )
    assert settings["ensemble"][0]["training"][name] == value
    # A train fraction v1 refused (below 0.1) is accepted.
    assert adapter.training_settings(_recipe((F08, "1.5"), fraction=0.05))


KEEP = [
    ({"training": {"batch_size": 288}}, "graph_route_batch_exceeds_train"),
    ({"training": {"learning_rate": 0}}, "graph_route_training_value_invalid"),
    ({"training": {"beta1": 1.0}}, "graph_route_training_value_invalid"),
    ({"training": {"loss": "made_up"}}, "graph_route_training_value_invalid"),
    (
        {"training": {"learning_rate": float("inf")}},
        "construction_recipe_malformed",
    ),
    ({"training": {"unknown": 1}}, "graph_route_training_field_invalid"),
    ({"training": {"h1_weight": 1.0}}, "graph_route_surface_unserved"),
    ({"output_weights": [0.0] * 7}, "graph_route_output_weights_invalid"),
    ({"output_weights": [1.0] * 6}, "graph_route_output_weights_invalid"),
    ({"output_weights": [-1.0] + [1.0] * 6}, "graph_route_output_weights_invalid"),
    ({"ensemble": {"members": []}}, "graph_route_ensemble_invalid"),
    ({"ensemble": {"members": [{"outputs": [0, 1]}]}}, "graph_route_ensemble_invalid"),
    (
        {"ensemble": {"members": [{"outputs": [0, 0, 1, 2, 3, 4, 5, 6]}]}},
        "graph_route_ensemble_invalid",
    ),
    (
        {
            "ensemble": {
                "members": [
                    {"outputs": list(range(7))},
                    {"outputs": [0], "training": {"batch_size": 16}},
                ]
            }
        },
        "graph_route_ensemble_invalid",
    ),
    ({"other": {}}, "graph_route_procedure_invalid"),
]


@pytest.mark.parametrize("configuration, code", KEEP)
def test_the_keep_list_still_refuses(configuration, code):
    assert _refused((F08, "1.5"), configuration) == code


def test_train_fraction_zero_and_a_wrong_dataset_are_refused():
    assert _refused((F08, "1.5"), fraction=0) == "graph_route_training_value_invalid"
    assert (
        _refused((F08, "1.5"), use={"dataset": "other", "train_fraction": 1.0})
        == "graph_route_procedure_invalid"
    )


def test_an_unregistered_version_is_refused_by_the_v2_adapter():
    with pytest.raises(RecipeRefused) as raised:
        adapter.spec_for(F08, "1.4")
    assert raised.value.code == "graph_route_challenge_version_unregistered"


def test_more_than_four_members_are_accepted():
    members = [{"outputs": list(range(7))} for _ in range(9)]
    settings = adapter.training_settings(
        _recipe((F08, "1.5"), {"ensemble": {"members": members}})
    )
    assert len(settings["ensemble"]) == 9


def test_every_v2_code_is_registered_with_its_class():
    for suffix in adapter.REFUSED_SUFFIXES:
        assert (
            build_refusal_v2.outcome(adapter.CODE + suffix) == build_refusal_v2.REFUSED
        )
    for suffix in adapter.GAP_SUFFIXES:
        assert build_refusal_v2.outcome(adapter.CODE + suffix) == build_refusal_v2.GAP
    assert set(build_refusal_v2._REFUSED_SUFFIXES) == set(adapter.REFUSED_SUFFIXES)
    assert set(build_refusal_v2._GAP_SUFFIXES) == set(adapter.GAP_SUFFIXES)


def test_the_trainer_digest_is_pinned_and_in_each_v2_limits_document():
    raw = (adapter.TRAINER_PIN[0]).encode()
    del raw
    assert _sha(adapter.trainer_source()) == adapter.TRAINER_SHA256
    for key in NEW:
        block = physical_material.bundle_material(*key)["construction_limits_document"][
            "graph_training_adapter"
        ]
        assert block["trainer"]["sha256"] == "sha256:" + adapter.TRAINER_SHA256
        assert block == adapter.adapter_block(*key)


# ---- Training ------------------------------------------------------------


def _graph(key, batch, x64=False):
    """A small MLP graph of the version's interface at `batch` cases."""
    pytest.importorskip("jax")
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, intake, staging, submission
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[key]
    dtype = jnp.float64 if spec.dtype == "float64" else jnp.float32
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*key))
    width = 16

    def forward(w1, b1, w2, b2, x):
        return jnp.tanh(x @ w1 + b1) @ w2 + b2

    _, document, _ = through_bprime(
        forward,
        (
            jnp.zeros((spec.inputs, width), dtype),
            jnp.zeros((width,), dtype),
            jnp.zeros((width, spec.outputs), dtype),
            jnp.zeros((spec.outputs,), dtype),
            jnp.ones((batch, spec.inputs), dtype),
        ),
        role="forward",
        allowlist=allowed,
        input_names=[
            "params/0",
            "params/1",
            "params/2",
            "params/3",
            adapter.INPUT_NAME,
        ],
        max_bytes=intake.BOUNDS["document_bytes"],
    )

    def parameter(index, initializer, axes):
        return {
            "input": f"params/{index}",
            "initializer": initializer,
            "fan_in_axes": axes[0],
            "fan_out_axes": axes[1],
        }

    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            parameter(0, "glorot_normal", ([0], [1])),
            parameter(1, "zeros", ([], [])),
            parameter(2, "glorot_normal", ([0], [1])),
            parameter(3, "zeros", ([], [])),
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    return submission.canonical(manifest), files, submission.digest(manifest), staging


def _x64(key):
    import contextlib

    if adapter.SPECS[key].dtype != "float64":
        return contextlib.nullcontext()
    import jax

    return jax.enable_x64(True)


def _case(key, configuration):
    batch = (configuration.get("training") or {}).get("batch_size", 8)
    raw_manifest, files, submission_digest, staging = _graph(key, batch)
    recipe = _recipe(key, configuration, digest=submission_digest)
    return recipe, raw_manifest, files, staging


def _train(key):
    import io

    raw = physical_material.bundle_material(*key)["train"]
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        return raw, archive["inputs"].copy(), archive["targets"].copy()


def _fit(key, configuration):
    recipe, raw_manifest, files, _ = _case(key, configuration)
    _raw, inputs, targets = _train(key)
    model = adapter.build_validated_graph(
        recipe,
        raw_manifest,
        files,
        allowlist_bytes=adapter.served_allowlist_bytes(*key),
        train_cases=adapter.SPECS[key].rows,
    )
    return model, model.fit(inputs, targets, seed=0), inputs


def test_per_output_weights_change_the_trained_model():
    key = (F08, "1.5")
    _plain, plain_fit, _ = _fit(key, {"training": {"steps": 24}})
    _weighted, weighted_fit, _ = _fit(
        key,
        {"training": {"steps": 24}, "output_weights": [10.0, 0, 0, 0, 0, 0, 1.0]},
    )
    assert plain_fit["params_sha256"] != weighted_fit["params_sha256"]
    # Two seeded rebuilds of the same recipe are bit-identical.
    _again, again_fit, _ = _fit(
        key,
        {"training": {"steps": 24}, "output_weights": [10.0, 0, 0, 0, 0, 0, 1.0]},
    )
    assert again_fit["params_sha256"] == weighted_fit["params_sha256"]


def test_an_ensemble_on_disjoint_outputs_trains_and_combines_per_output():
    key = (F08, "1.5")
    members = [
        {"outputs": [0, 1, 2], "training": {"steps": 16}},
        {"outputs": [3, 4], "training": {"steps": 16, "learning_rate": 0.01}},
        {"outputs": [5, 6], "training": {"steps": 16, "optimizer_family": "adam"}},
    ]
    model, fit, inputs = _fit(key, {"ensemble": {"members": members}})
    assert fit["members"] == 3 and len(fit["member_losses"]) == 3
    # Each output is its own member's prediction alone.
    combine = model.combine
    assert combine.shape == (3, 7)
    np.testing.assert_array_equal(
        combine,
        np.array(
            [[1, 1, 1, 0, 0, 0, 0], [0, 0, 0, 1, 1, 0, 0], [0, 0, 0, 0, 0, 1, 1]],
            dtype=np.float32,
        ),
    )
    import jax.numpy as jnp

    query = inputs[:4]
    member_rows = [
        np.asarray(
            model.prepared.predict(
                [jnp.asarray(v) for v in params], jnp.asarray(query)
            )[0]
        )
        for params in model.members
    ]
    combined = model.predict(query)
    for output, owner in enumerate([0, 0, 0, 1, 1, 2, 2]):
        expected = member_rows[owner][:, output] * model.sd[output] + model.mu[output]
        np.testing.assert_allclose(combined[:, output], expected, rtol=1e-5, atol=1e-5)


def test_overlapping_members_average_their_shared_outputs_by_weight():
    from carbon.development_session import physical_graph_trainer_v2 as trainer

    combine = trainer.combination(
        [
            {"outputs": [0, 1], "weight": 1.0},
            {"outputs": [1, 2], "weight": 3.0},
        ],
        3,
    )
    np.testing.assert_allclose(combine, [[1, 0.25, 0], [0, 0.75, 1]])
    with pytest.raises(ValueError):
        trainer.combination([{"outputs": [0], "weight": 1.0}], 2)


# ---- The receiver --------------------------------------------------------


def _local_runner():
    count = itertools.count()

    def runner(ledger, *, source, files, output_validator, **_kwargs):
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        done = subprocess.run(
            [sys.executable, "-c", source],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + _sha(path.read_bytes())
                for path in snapshot.iterdir()
            },
        }

    return runner


def _image():
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8))


@posix
@pytest.mark.parametrize("key", [(F08, "1.5"), (MOTOR, "1.4")])
def test_the_receiver_rebuilds_and_infers_a_v2_ensemble(key, tmp_path):
    from carbon.development_session.profile import canonical

    spec = adapter.SPECS[key]
    width = spec.outputs
    configuration = {
        "training": {"steps": 8},
        "ensemble": {
            "members": [
                {"outputs": list(range(width // 2))},
                {"outputs": list(range(width // 2, width))},
            ]
        },
    }
    with _x64(key):
        recipe, raw_manifest, files, staging = _case(key, configuration)
        raw_train, inputs, targets = _train(key)
        query = np.ascontiguousarray(inputs[:3])
        material = physical_material.bundle_material(*key)
        kit = material["construction_kit"]
        result = direct_graph_construction_worker.reconstruct_and_infer_graph_public(
            SimpleNamespace(root=tmp_path),
            owner="test",
            identity="test",
            image=_image(),
            recipe=recipe,
            challenge_binding={
                "challenge_id": kit["id"],
                "challenge_version": kit["version"],
                "train_digest": kit["train_digest"],
                "interface_digest": kit["interface_digest"],
                "construction_limits_digest": kit["construction_limits_digest"],
            },
            limits_document=material["construction_limits_document"],
            source_envelope=canonical(staging.envelope(raw_manifest, files)),
            train=raw_train,
            inputs=query,
            expected_output_shape=(3, width),
            allowlist_bytes=adapter.served_allowlist_bytes(*key),
            seed=0,
            runner=_local_runner(),
            adapter_id=spec.adapter_id,
        )
        assert result.build.receipt["fit"]["members"] == 2
        predictions = np.asarray(result.inference.predictions, dtype=spec.dtype)
        model = adapter.build_validated_graph(
            recipe,
            raw_manifest,
            files,
            allowlist_bytes=adapter.served_allowlist_bytes(*key),
            train_cases=spec.rows,
        )
        model.fit(inputs, targets, seed=0)
        np.testing.assert_allclose(
            predictions, model.predict(query, isolated=True), rtol=1e-5, atol=1e-5
        )
    # No older loader reads an ensemble state as one graph.
    from carbon.development_session import physical_graph_state

    with pytest.raises(RecipeRefused):
        physical_graph_state.load(
            result.build.state_path.read_bytes(),
            recipe,
            allowlist_module.Allowlist(adapter.served_allowlist_bytes(*key)),
        )


# ---- Every offered version: registration points and routes -------------


def _offered():
    from carbon.challenge_registry.registry import _entries

    return sorted(
        {
            (entry.challenge_id, entry.version)
            for entry in _entries()
            if entry.version is not None and entry.describe is not None
        }
    )


def _routes(cid, version):
    """The construction routes a registered version serves."""
    from carbon.challenge_registry import campaigns
    from carbon.development_session.research_service import (
        recipe_source_kinds,
        takes_construction_recipes,
    )
    from carbon.research import ChallengeKey

    routes = set()
    if takes_construction_recipes(ChallengeKey(cid, version)):
        kinds = recipe_source_kinds(ChallengeKey(cid, version))
        routes.update("recipe." + kind for kind in kinds)
        if graph_adapters.module_for(cid, version) is adapter:
            routes.add("graph.v2")
        elif "graph" in kinds:
            routes.add("graph.v1")
    else:
        try:
            campaigns.campaign_for({"id": cid, "version": version})
        except Exception:  # noqa: BLE001, S110 - no campaign composes: no route
            pass
        else:
            routes.add("level0")
    return routes


def test_each_offered_version_lists_the_routes_it_serves():
    """Validator L19: which routes each offered version serves. The graph
    route v2 versions serve their own graph and their catalog (Motor and
    Cooling inherit 1.3's entries); Level 0 is listed where it is reachable."""
    routes = {key: _routes(*key) for key in _offered()}
    assert routes[(F08, "1.5")] == {"recipe.graph", "recipe.catalog", "graph.v2"}
    assert routes[(F02, "2.4")] == {"recipe.graph", "recipe.catalog", "graph.v2"}
    assert routes[(MOTOR, "1.4")] == {"recipe.graph", "recipe.catalog", "graph.v2"}
    assert routes[(COOLING, "1.4")] == {"recipe.graph", "recipe.catalog", "graph.v2"}
    assert routes[(F08, "1.4")] >= {"recipe.graph", "graph.v1"}
    # Level 0 is reachable only on the first versions (Motor 1.0, Cooling 1.0,
    # Battery 1.0); the page offers each Challenge's latest version only
    # (app.js `offeredChallenges`), and none of those serves it (L19 moot).
    level0 = sorted(key for key, served in routes.items() if "level0" in served)
    assert level0 == [
        ("battery-fastcharge-ageing-development-v1", "1.0"),
        (COOLING, "1.0"),
        (MOTOR, "1.0"),
    ]
    latest = {}
    for cid, version in routes:
        number = tuple(int(part) for part in version.split("."))
        if cid not in latest or number > latest[cid][0]:
            latest[cid] = (number, version)
    for cid in (F08, F02, MOTOR, COOLING):
        served = routes[(cid, latest[cid][1])]
        assert "graph.v2" in served and "level0" not in served, cid


@pytest.mark.parametrize("key", NEW)
def test_every_new_version_passes_each_registration_point(key):
    """The hard-coded version checks (LP_HARDCODED_VERSION_CHECKS_20261023):
    each registration a version is read through serves the new version."""
    from carbon.challenge_kit import physical_pack
    from carbon.challenge_registry import campaigns, registry
    from carbon.research import model

    cid, version = key
    assert (cid, version) in physical_pack.PACK_VERSIONS
    assert physical_pack.development_bank(cid, version)["inputs"].size
    assert (cid, version) in campaigns._versioned_campaigns()
    described = registry.describe(cid, version)
    example = described["graph_route"]["example"]["recipe"]
    assert example["source"]["kind"] == "graph"
    assert example["procedure"]["configuration"]["ensemble"]["members"]
    assert {"recipe": example} in described["examples"]
    recipe = graph_adapters.graph_recipe(cid, version, "sha256:" + "a" * 64)
    assert model._registered_train_use(ChallengeKeyOf(cid, version), recipe) == (
        adapter.SPECS[key].train_use
    )


def ChallengeKeyOf(cid, version):
    from carbon.research import ChallengeKey

    return ChallengeKey(cid, version)


def test_the_scaffold_material_offers_a_graph_recipe_on_each_new_version():
    from carbon.development_session.research_tasks import ready_recipes

    for key in NEW:
        document = ready_recipes(*key, {})
        assert "graph" in document["source_kinds"], key
        graph = document["recipes"]["graph"]
        assert (
            graph["procedure"]["train_use"]["dataset"] == adapter.SPECS[key].train_use
        )


# ---- The Ladder ----------------------------------------------------------


LADDER_GATES = ("native_valid", "complete_fixed_coverage")
EXAM = "sha256:" + "e" * 64
SEALED = "f08-dual-sealed-grid-8x1-v2"


def _ladder(tmp_path):
    from carbon.challenge_validator.ladder_store import LadderStore
    from carbon.challenge_validator.ledger import AttemptLedger

    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return LadderStore(AttemptLedger(root / "attempts.sqlite3"))


def _scored(total):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": total, "D": total},
        "gates": {g: "PASS" for g in LADDER_GATES},
        "components": {"robust_fidelity_benefit": total},
    }


def _grade(store, version, total, *, exam_version=SEALED, exam=EXAM):
    from carbon.research import ChallengeKey

    return store.record(
        "5Miner",
        ChallengeKey(F08, version),
        exam,
        _scored(total),
        exam_version=exam_version,
        gates=LADDER_GATES,
        rebuild_noise=None,
    )


def test_the_ladder_keys_on_the_evaluation_version(tmp_path):
    from carbon.research import ChallengeKey
    from carbon.scoring import sealed_versions

    assert sealed_versions.ladder_key(F08, "1.5") == sealed_versions.ladder_key(
        F08, "1.4"
    )
    assert sealed_versions.ladder_key(F08, "1.5") == SEALED
    # Cooling 1.4 keeps 1.3's sealed exam, so its Ladder key too (rc3).
    assert sealed_versions.ladder_key(COOLING, "1.4") == sealed_versions.ladder_key(
        COOLING, "1.3"
    )
    # No sealed exam registered: the construction version, marked.
    assert sealed_versions.ladder_key(COOLING, "1.0") == "construction:1.0"
    store = _ladder(tmp_path)
    key4 = store._key("hk", ChallengeKey(F08, "1.4"), EXAM)[0]
    assert key4 == store._key("hk", ChallengeKey(F08, "1.5"), EXAM)[0]
    assert store._key("hk", ChallengeKey(F08, "1.5"), "exam-b")[0] != key4


def test_a_best_carries_from_f08_1_4_to_1_5_on_the_same_exam(tmp_path):
    from carbon.research import ChallengeKey

    store = _ladder(tmp_path)
    first = _grade(store, "1.4", 0.60)
    assert first["status"] == "IMPROVED"
    carried = store.served("5Miner", ChallengeKey(F08, "1.5"), EXAM)
    assert carried["best"] == first
    lower = _grade(store, "1.5", 0.50)
    assert lower["status"] != "IMPROVED"
    assert store.served("5Miner", ChallengeKey(F08, "1.5"), EXAM)["best"] == first
    higher = _grade(store, "1.5", 0.70)
    assert higher["status"] == "IMPROVED"
    # Read back on 1.4 too: one ladder for the one exam.
    assert store.served("5Miner", ChallengeKey(F08, "1.4"), EXAM)["best"] == higher
    # A different exam version still starts a fresh ladder (grade_feedback).
    fresh = _grade(store, "1.5", 0.10, exam_version="f08-another-exam-v1")
    assert fresh["status"] == "IMPROVED"


def test_a_row_written_before_is_read_through_the_map_and_never_rewritten(tmp_path):
    from carbon.research import ChallengeKey

    store = _ladder(tmp_path)
    first = _grade(store, "1.4", 0.60)
    with store.ledger._db() as db:
        row = db.execute("SELECT * FROM ladder_feedback_v2").fetchone()
        db.execute("DELETE FROM ladder_feedback_v2")
        # The same documents as a row the construction-keyed table held.
        db.execute(
            "INSERT INTO ladder_feedback(hotkey, challenge_id, challenge_version,"
            " exam_key, best, latest, updated_ns) VALUES(?,?,?,?,?,?,?)",
            (row[0], row[1], "1.4", row[3], row[5], row[6], row[7]),
        )
        before = db.execute("SELECT * FROM ladder_feedback").fetchall()
    assert store.served("5Miner", ChallengeKey(F08, "1.5"), EXAM)["best"] == first
    _grade(store, "1.5", 0.70)
    with store.ledger._db() as db:
        assert db.execute("SELECT * FROM ladder_feedback").fetchall() == before
        (version,) = db.execute(
            "SELECT challenge_version FROM ladder_feedback_v2"
        ).fetchone()
    assert version == "1.5"


# ---- Motor and Cooling practice take a graph recipe ---------------------


def _catalog_practice(cid, version, tmp_path):
    from pathlib import Path

    from test_lp_prod_research_tools import ledger

    if cid == MOTOR:
        from carbon.motor.catalog_practice import MotorCatalogPractice as Practice

        root = "."
    else:
        from carbon.cold_plate.catalog_practice import (
            CoolingCatalogPractice as Practice,
        )

        root = Path(__file__).resolve().parents[2]
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    return Practice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        root=root,
        version=version,
        resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )


@pytest.mark.parametrize("cid", [MOTOR, COOLING])
def test_motor_and_cooling_1_4_practise_a_graph_recipe(cid, tmp_path, monkeypatch):
    calls = []

    def practise(ledger, **kwargs):
        calls.append(kwargs)
        query = kwargs.get("inputs")
        if query is None:
            query = kwargs["material"]["practice_inputs"]
        width = adapter.SPECS[(cid, "1.4")].outputs
        rows = np.full((len(query), width), 1.0).tolist()
        state = "sha256:" + "5" * 64
        result = SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=rows),
        )
        return result, {"kind": "C03_DOCKER", "adapter": "x"}

    monkeypatch.setattr(graph_adapters, "practise", practise)
    recipe = graph_adapters.graph_recipe(cid, "1.4", "sha256:" + "a" * 64)
    out = _catalog_practice(cid, "1.4", tmp_path)("graph-practice-0001", recipe)
    (call,) = calls
    assert call["recipe"].to_dict()["source"]["kind"] == "graph"
    assert call["binding"]["challenge_version"] == "1.4"
    assert out["source_kind"] == "graph"
    assert out["catalog_id"] is None and out["bundle_recipe_digest"] is None
    assert out["summary"]
    # 1.3 serves no graph adapter: the same recipe is refused, as before.
    monkeypatch.undo()
    old = graph_adapters.graph_recipe(cid, "1.4", "sha256:" + "a" * 64)
    kit = physical_material.construction_kit(cid, "1.3")
    old["challenge"] = kit
    old["output"]["interface_digest"] = kit["interface_digest"]
    with pytest.raises(ValueError, match="catalog_recipe_required"):
        _catalog_practice(cid, "1.3", tmp_path / "old")("graph-practice-0002", old)


def test_an_ensemble_state_with_a_bad_combination_is_refused():
    from carbon.development_session import physical_graph_state_v2 as state

    with pytest.raises(RecipeRefused) as raised:
        state._combine(np.full((2, 3), 0.25, dtype=np.float32), 2, 3, np.float32)
    assert raised.value.code == "ensemble_graph_state_combine_invalid"
    good = np.array([[1, 0.5, 0], [0, 0.5, 1]], dtype=np.float32)
    assert state._combine(good, 2, 3, np.float32) is not None
    with pytest.raises(RecipeRefused):
        # The decoder and combination share the interface dtype.
        state._combine(good, 2, 3, np.float64)


def test_each_adapter_s_specs_are_exactly_the_versions_declaring_it():
    from carbon.development_session import physical_graph_adapter as v1

    assert set(adapter.SPECS) == version_registry.keys(graph_adapter="v2")
    assert set(v1.SPECS) == version_registry.keys(graph_adapter="v1")
    for key, spec in adapter.SPECS.items():
        assert spec.predecessor == version_registry.entry(*key).predecessor


#: The sealed grid evaluation versions scoring v2 grades the launch Challenges
#: with: D = min(V, C) and the physics half. v1 stays as history only.
SEALED_V2 = {
    F08: "f08-dual-sealed-grid-8x1-v2",
    F02: "f02-dual-sealed-grid-8x1-v2",
    version_registry.MOTOR: "motor-dual-sealed-batch-30-v2",
    version_registry.COOLING: "cooling-dual-sealed-batch-16-v2",
}


def test_every_served_launch_version_is_sealed_graded_on_v2_never_v1():
    """The Validator (rc3): every served F08, F02, Motor and Cooling version with
    a sealed exam - graph route v2's included - dispatches to its grid grader's
    v2 evaluation version, in the registry and in the graders, never v1."""
    from carbon.scoring import (
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        f02_dual_pack,
        f02_sealed_dual_pack,
        f08_dual_pack,
        f08_sealed_dual_pack,
        motor_sealed_dual_pack,
    )

    graders = {
        F08: f08_sealed_dual_pack.VERSIONS,
        F02: f02_sealed_dual_pack.VERSIONS,
        version_registry.MOTOR: motor_sealed_dual_pack.VERSIONS,
    }
    _, sealed = _scorer_tables()
    checked = []
    for (cid, version), entry in version_registry.VERSIONS.items():
        if cid not in SEALED_V2 or entry.sealed_evaluation is None:
            continue
        checked.append((cid, version))
        assert entry.sealed_evaluation == SEALED_V2[cid], (cid, version)
        assert sealed[(cid, version)] == SEALED_V2[cid], (cid, version)
        if cid in graders:
            assert graders[cid][version][0] == SEALED_V2[cid], (cid, version)
        else:
            variant = cooling_encoded_dual_pack.sealed_adapter(version)
            assert variant is not None or version in cooling_dual_pack.SEALED_VERSIONS
    # The old flat v1 sealed path never takes a graph route v2 version.
    assert "1.5" not in f08_dual_pack.SEALED_VERSIONS
    assert "2.4" not in f02_dual_pack.SEALED_VERSIONS
    for key in ((F08, "1.5"), (F02, "2.4"), (version_registry.MOTOR, "1.4")):
        assert key in checked, key
    assert (version_registry.COOLING, "1.4") in checked


def test_cooling_1_3_and_1_4_decode_into_1_2s_output_space_and_share_its_sealed_exam():
    """The Validator's condition (rc3, Cooling key flag): 1.2, 1.3 and 1.4 share
    one evaluation-version key only because the encoded adapter decodes 1.3/1.4
    rows into exactly 1.2's native output space and grades 1.2's sealed batches."""
    from carbon.cold_plate.output_encoding import encode_targets
    from carbon.scoring import cooling_dual_pack, cooling_encoded_dual_pack

    rng = np.random.default_rng(0)
    profile = 40.0 + 20.0 * rng.random((6, 30))
    native = np.column_stack(
        [profile.max(axis=1) + 1.0 + rng.random(6), profile, 100.0 + rng.random(6)]
    )
    decoded = np.asarray(cooling_encoded_dual_pack._decoded(encode_targets(native)))
    assert decoded.shape == native.shape == (6, 32)
    np.testing.assert_allclose(decoded, native, rtol=1e-12, atol=1e-9)
    assert cooling_encoded_dual_pack.OUTPUT == cooling_dual_pack.OUTPUT
    raw = cooling_dual_pack.sealed_adapter("1.2")
    for version in ("1.3", "1.4"):
        encoded = cooling_encoded_dual_pack.sealed_adapter(version)
        assert (encoded.EVALUATION_VERSION, encoded.CASE_ID) == (
            raw.EVALUATION_VERSION,
            raw.CASE_ID,
        )
