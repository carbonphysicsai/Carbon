"""The backbone catalog pipeline (OWNER-BACKBONE-CATALOG-01): a tested
backbone becomes an entry by its bundle plus one manifest line, and one
command verifies it. Launchpad and the miner path read only the manifest."""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from carbon.backbone_catalog import entries as catalog_entries
from carbon.backbone_catalog import pipeline, settings

MOTOR = {"id": "electric-motor-magnetics", "version": "1.2"}
#: The five clean tested Torch entries.
TORCH = {
    "neuralop.FNO",
    "neuralop.TFNO",
    "neuralop.UQNO",
    "physicsnemo.FullyConnected",
    "transolver",
}
#: The eleven tested jNO (foundax) entries: python-cpu-py311 bundles on the C-03
#: CPU worker parent, catalogued as "jno.<name>".
JNO = {
    "jno." + name
    for name in (
        "deeponet",
        "fno1d",
        "fno2d",
        "fno3d",
        "geofno",
        "linear",
        "mgno1d",
        "mgno2d",
        "mlp",
        "unet1d",
        "unet2d",
    )
}
#: The six DeepXDE/THUML entries, rebuilt without KNO/WNO (MC601-606) and
#: pair-identical (Test Lead, PAIR_IDENTITY_CATALOG_CLEAN_20261020): coverage
#: builds with pinned wheels, offered on Motor 1.3.
CLEAN = {
    "deepxde.DeepONetCartesianProd",
    "thuml.FNO",
    "thuml.F_FNO",
    "thuml.Factformer",
    "thuml.Galerkin_Transformer",
    "thuml.Transolver",
}
#: Hard-remainder entries pair-identical on Motor 1.3 (Test Lead,
#: PAIR_IDENTITY_HARD_V7_20261021): v7 builds, offered on Motor 1.3.
HARD = {
    "cno.CNO1d",
    "thuml.MWT",
    "thuml.Transformer",
    "oformer.Encoder1D_PointWiseDecoder1D",
    "neuralop.SFNO",
    "neuralop.LocalNO",
    # PAIR_IDENTITY_HARD_V9_20261022: graph constants rebuilt in-graph (v7 caps).
    "lno.LNO1d",
    "neuralop.GINO",
    "physicsnemo.MeshGraphNet",
    # A variant: it uses upstream's instance-norm option (CATALOG_HARD_FIXES).
    "thuml.LSM",
}
#: F08 1.4 / F02 2.3 float32 builds, each with its own pair-identity receipt
#: (Test Lead, PAIR_IDENTITY_PX14_20261022), offered on their own version only.
F08 = {
    "f08.neuralop.FNO",
    "f08.neuralop.TFNO",
    "f08.neuralop.UQNO",
    "f08.physicsnemo.FullyConnected",
    "f08.transolver",
}
F02 = {"f02.physicsnemo.FullyConnected"}
#: The five Torch builds resized to Cooling's 32 outputs, each with its own
#: Cooling pair-identity receipt (Test Lead, PAIR_IDENTITY_COOLING_CATALOG_
#: 20261020), offered on Cooling 1.2 only.
#: The five Cooling baselines re-tested on Cooling 1.3 (law-safe output encoding; its TRAIN and interface digests
#: differ from 1.2's, so the 1.2 receipts cannot serve), offered on Cooling 1.3 only (PAIR_IDENTITY_C13_COOLING_20261022).
COOLING13 = {
    "cooling13.neuralop.FNO",
    "cooling13.neuralop.TFNO",
    "cooling13.neuralop.UQNO",
    "cooling13.physicsnemo.FullyConnected",
    "cooling13.transolver",
}
COOLING = {
    "cooling.neuralop.FNO",
    "cooling.neuralop.TFNO",
    "cooling.neuralop.UQNO",
    "cooling.physicsnemo.FullyConnected",
    "cooling.transolver",
}
#: A coverage-build entry as the cleaned DeepXDE/THUML bundles declare it.
COVERAGE_ITEM = {
    "catalog_id": "thuml.FNO",
    "backbone": "thuml.FNO",
    "settings_schema": "carbon-candidate-coverage-v1",
    "defaults": {
        "configuration": {"backbone": "thuml.FNO", "learning_rate": 0.001},
        "train_use": {},
    },
}


def test_every_entry_verifies_and_motor_1_2_offers_each_tested_backbone():
    assert set(pipeline.verify_all()) == (
        TORCH | JNO | CLEAN | HARD | COOLING | COOLING13 | F08 | F02
    )
    # Motor 1.2 is unchanged: the five Torch entries. Motor 1.3 (1.2 plus
    # allowlist v7) adds the eleven jNO entries, built on the C-03 CPU parent,
    # and the six cleaned DeepXDE/THUML entries.
    assert {e["catalog_id"] for e in pipeline.entries(MOTOR["id"], "1.2")} == TORCH
    assert {
        e["catalog_id"] for e in pipeline.entries(MOTOR["id"], "1.3")
    } == TORCH | JNO | CLEAN | HARD
    # Never on a released or step-2 version (Validator): only Motor's catalog
    # versions.
    for item in pipeline.entries():
        assert item["challenges"] == (
            [{"id": "chip-cold-plate", "version": "1.2"}]
            if item["catalog_id"] in COOLING
            else (
                [{"id": "chip-cold-plate", "version": "1.3"}]
                if item["catalog_id"] in COOLING13
                else (
                    [{"id": "f08-ribbed-bracket", "version": "1.4"}]
                    if item["catalog_id"] in F08
                    else (
                        [{"id": "f02", "version": "2.3"}]
                        if item["catalog_id"] in F02
                        else (
                            [{"id": "f08-ribbed-bracket", "version": "1.4"}]
                            if item["catalog_id"] in F08
                            else (
                                [{"id": "f02", "version": "2.3"}]
                                if item["catalog_id"] in F02
                                else (
                                    [{**MOTOR, "version": "1.3"}]
                                    if item["catalog_id"] in JNO | CLEAN | HARD
                                    else [MOTOR, {**MOTOR, "version": "1.3"}]
                                )
                            )
                        )
                    )
                )
            )
        )
    for version in ("1.0", "1.1"):
        assert pipeline.entries(MOTOR["id"], version) == []


@pytest.mark.parametrize(
    "catalog_id, challenge",
    [
        ("cooling.neuralop.FNO", {"id": "chip-cold-plate", "version": "1.1"}),
        ("neuralop.FNO", {"id": "electric-motor-magnetics", "version": "1.1"}),
        ("neuralop.FNO", {"id": "electric-motor-magnetics", "version": "1.4"}),
    ],
)
def test_an_entry_offered_where_no_catalog_is_served_is_refused(catalog_id, challenge):
    item = copy.deepcopy(pipeline.entry(catalog_id))
    item["challenges"].append(challenge)
    with pytest.raises(pipeline.CatalogBroken, match="serves no backbone catalog"):
        pipeline.verify(item)


# --- the receipt binds its run facts (Validator, 2026-10-21) ------------------


@pytest.mark.parametrize(
    "catalog_id, challenge",
    [
        ("neuralop.FNO", {"id": "chip-cold-plate", "version": "1.2"}),
        ("neuralop.FNO", {"id": "f08-ribbed-bracket", "version": "1.4"}),
        ("cooling.neuralop.FNO", {"id": "electric-motor-magnetics", "version": "1.3"}),
    ],
)
def test_an_entry_offered_off_its_tested_challenge_is_refused(catalog_id, challenge):
    # A Motor-tested entry is never offered on Cooling (or F08) on the strength
    # of its Motor receipt, nor a Cooling-tested one on Motor.
    item = copy.deepcopy(pipeline.entry(catalog_id))
    item["challenges"].append(challenge)
    with pytest.raises(pipeline.CatalogBroken, match="but tested on"):
        pipeline.verify(item)


@pytest.mark.parametrize(
    "fact, match",
    [
        ("tested_on", "tested Challenge"),
        ("image_digest", "worker image"),
        ("tested_train_digest", "tested train digest"),
        ("tested_interface_digest", "tested interface digest"),
    ],
)
def test_a_receipt_missing_a_run_fact_is_refused(tmp_path, monkeypatch, fact, match):
    receipts = tmp_path / "receipts"
    shutil.copytree(pipeline.RECEIPTS, receipts)
    path = receipts / "neuralop.FNO.json"
    receipt = json.loads(path.read_bytes())
    del receipt[fact]
    path.write_text(json.dumps(receipt))
    monkeypatch.setattr(pipeline, "RECEIPTS", receipts)
    with pytest.raises(pipeline.CatalogBroken, match=match):
        pipeline.verify(pipeline.entry("neuralop.FNO"))


def test_every_receipt_binds_its_packets_challenge_and_one_worker_image():
    import re

    for item in pipeline.entries():
        receipt = json.loads(
            (pipeline.RECEIPTS / (item["catalog_id"] + ".json")).read_bytes()
        )
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["image_digest"])
        tested_id = receipt["tested_on"].split("@")[0]
        assert {c["id"] for c in item["challenges"]} == {tested_id}


def test_bind_refuses_a_fact_that_differs_from_the_bound_one(tmp_path, monkeypatch):
    receipts = tmp_path / "receipts"
    shutil.copytree(pipeline.RECEIPTS, receipts)
    monkeypatch.setattr(pipeline, "RECEIPTS", receipts)
    bound = json.loads((receipts / "neuralop.FNO.json").read_bytes())
    again = pipeline.bind(
        "neuralop.FNO",
        tested_on=bound["tested_on"],
        image_digest=bound["image_digest"],
    )
    assert again == bound
    with pytest.raises(pipeline.CatalogBroken, match="already binds another"):
        pipeline.bind(
            "neuralop.FNO",
            tested_on=bound["tested_on"],
            image_digest="sha256:" + "0" * 64,
        )
    with pytest.raises(pipeline.CatalogBroken, match="id@version"):
        pipeline.bind(
            "neuralop.FNO", tested_on="motor", image_digest="sha256:" + "0" * 64
        )


def test_the_licence_screen_left_kno_and_wno_out():
    ids = {e["catalog_id"] for e in pipeline.entries()}
    assert not {i for i in ids if "kno" in i.lower() or "wno" in i.lower()}


@pytest.mark.parametrize(
    "change, why",
    [
        (
            lambda i: i["bundle_ref"].update(bundle_digest="sha256:" + "0" * 64),
            "bundle digest",
        ),
        (
            lambda i: i["defaults"]["configuration"].update(learning_rate=0.0123),
            "baseline",
        ),
        (lambda i: i["defaults"]["train_use"].update(steps=4000), "baseline"),
        (
            lambda i: i.update(
                settings_schema=(
                    "carbon-candidate-levers-v1"
                    if i["settings_schema"].endswith("coverage-v1")
                    else "carbon-candidate-coverage-v1"
                )
            ),
            "settings schema",
        ),
    ],
)
def test_an_entry_that_is_not_what_it_claims_is_refused(change, why):
    item = copy.deepcopy(pipeline.entry("neuralop.FNO"))
    change(item)
    with pytest.raises(pipeline.CatalogBroken, match=why):
        pipeline.verify(item)


def test_a_receipt_with_a_differing_pair_is_refused(tmp_path, monkeypatch):
    receipts = tmp_path / "receipts"
    shutil.copytree(pipeline.RECEIPTS, receipts)
    path = receipts / "neuralop.FNO.json"
    receipt = json.loads(path.read_bytes())
    receipt["differ"] = ["MT101"]
    path.write_text(json.dumps(receipt))
    monkeypatch.setattr(pipeline, "RECEIPTS", receipts)
    with pytest.raises(pipeline.CatalogBroken, match="pair-identity"):
        pipeline.verify(pipeline.entry("neuralop.FNO"))


def test_only_a_baseline_packet_becomes_an_entry(tmp_path):
    case = tmp_path / "t_fno_averaging_ema"
    case.mkdir()
    with pytest.raises(pipeline.CatalogBroken, match="baseline"):
        pipeline.add(
            case,
            challenges=["electric-motor-magnetics@1.2"],
            receipt=tmp_path / "r.json",
            receipt_key="fno",
            image_digest="sha256:" + "0" * 64,
        )


# --- settings: the bundle's own vocabulary, refused at the door ---------------


def _resolve(catalog_id, configuration=None, train_use=None):
    item = COVERAGE_ITEM if catalog_id == "thuml.FNO" else pipeline.entry(catalog_id)
    return settings.resolve(item, configuration or {}, train_use or {})


def test_defaults_are_the_tested_baseline_and_the_backbone_is_fixed():
    configuration, train_use = _resolve("neuralop.FNO")
    assert configuration == {
        "arch": {"hidden": 16, "layers": 2, "modes": 12},
        "backbone": "neuralop.FNO",
        "learning_rate": 0.002,
    }
    assert train_use == {}
    configuration, _ = _resolve("neuralop.FNO", {"arch": {"modes": 8}})
    assert configuration["arch"] == {"hidden": 16, "layers": 2, "modes": 8}


def test_a_lever_setting_passes_as_the_build_reads_it():
    _, train_use = _resolve(
        "neuralop.FNO",
        train_use={
            "steps": 4000,
            "averaging": {"kind": "ema", "decay": 0.98},
            "schedule": {"name": "warmup_cosine", "warmup": 50},
            "search": {
                "candidates": [{"learning_rate": 0.001}, {"arch": {"hidden": 32}}]
            },
        },
    )
    assert train_use["steps"] == 4000


@pytest.mark.parametrize(
    "catalog_id, configuration, train_use, code",
    [
        (
            "neuralop.FNO",
            {"backbone": "neuralop.SFNO"},
            None,
            "catalog_setting_unknown",
        ),
        ("neuralop.FNO", {"arch": {"width": 3}}, None, "catalog_setting_unknown"),
        ("neuralop.FNO", {"learning_rate": 0}, None, "catalog_setting_invalid"),
        (
            "neuralop.FNO",
            {"learning_rate": float("nan")},
            None,
            "catalog_setting_invalid",
        ),
        ("neuralop.FNO", None, {"steps": 0}, "catalog_setting_invalid"),
        (
            "neuralop.FNO",
            None,
            {"optimizer": {"name": "adagrad"}},
            "catalog_setting_invalid",
        ),
        (
            "neuralop.FNO",
            None,
            {"search": {"candidates": [{"backbone": "transolver"}]}},
            "catalog_setting_invalid",
        ),
        (
            "neuralop.FNO",
            None,
            {"distill": {"teacher": {"backbone": "transolver"}}},
            "catalog_setting_invalid",
        ),
        ("neuralop.FNO", None, {"prune": {"fraction": 1.0}}, "catalog_setting_invalid"),
        ("neuralop.FNO", None, {"quantize": {"bits": 1}}, "catalog_setting_invalid"),
        (
            "transolver",
            {"arch": {"hidden": 30, "heads": 4}},
            None,
            "catalog_settings_inconsistent",
        ),
        ("thuml.FNO", {"arch": {"modes": 8}}, None, "catalog_setting_unknown"),
        ("thuml.FNO", None, {"averaging": {"kind": "ema"}}, "catalog_setting_unknown"),
        ("thuml.FNO", None, {"loss": "huber"}, "catalog_setting_invalid"),
    ],
)
def test_a_setting_the_build_would_refuse_is_refused_first(
    catalog_id, configuration, train_use, code
):
    with pytest.raises(catalog_entries.CatalogRefused) as refused:
        _resolve(catalog_id, configuration, train_use)
    assert refused.value.code == code


def test_the_coverage_entries_take_their_builds_own_settings():
    _, train_use = _resolve(
        "thuml.FNO",
        train_use={"steps": 500, "loss": "derivative", "derivative_weight": 0.2},
    )
    assert train_use == {"steps": 500, "loss": "derivative", "derivative_weight": 0.2}


def test_an_entry_is_written_as_the_directory_the_owner_installer_reads(tmp_path):
    from carbon.development_session.library_bundles import (
        bundle_ref,
        load_pinned_bundle_directory,
    )

    item = pipeline.entry("neuralop.FNO")
    directory = pipeline.bundle_directory(item, tmp_path / "bundle")
    assert (
        bundle_ref(*load_pinned_bundle_directory(directory)).bundle_digest
        == item["bundle_ref"]["bundle_digest"]
    )


def _with_wheels(monkeypatch):
    """neuralop.FNO's pinned files, its manifest declaring one wheel while its
    lock stays empty, digest-consistent so only the lock rule can refuse."""
    item = copy.deepcopy(pipeline.entry("neuralop.FNO"))
    files = dict(pipeline.bundle_files(item))
    manifest = json.loads(files["bundle.json"])
    manifest["wheels"] = {"example-1.0-py3-none-any.whl": "sha256:" + "0" * 64}
    files["bundle.json"] = json.dumps(manifest).encode()
    item["bundle_ref"]["bundle_digest"] = pipeline._digest(
        pipeline._canonical(manifest)
    )
    monkeypatch.setattr(pipeline, "bundle_files", lambda _item: files)
    return item


def test_an_entry_with_pinned_wheels_needs_a_wheelhouse(tmp_path, monkeypatch):
    item = _with_wheels(monkeypatch)
    with pytest.raises(pipeline.CatalogBroken, match="wheelhouse"):
        pipeline.bundle_directory(item, tmp_path / "bundle")


def test_an_empty_lock_is_accepted_only_beside_an_empty_wheel_set(monkeypatch):
    # Declared wheels with an empty lock: a lock step that produced nothing.
    item = _with_wheels(monkeypatch)
    with pytest.raises(pipeline.CatalogBroken, match="lock and wheel set disagree"):
        pipeline.verify(item)


#: A jNO entry as the JAX levers build declares it (the 11 jNO baselines wait
#: on the parent-image decision before they are listed).
JAX_ITEM = {
    "catalog_id": "jno.fno1d",
    "backbone": "fno1d",
    "settings_schema": "carbon-candidate-jax-levers-v1",
    "defaults": {
        "configuration": {"backbone": "fno1d", "learning_rate": 0.001},
        "train_use": {},
    },
}


def test_the_jax_levers_build_takes_its_own_settings():
    configuration, train_use = settings.resolve(
        JAX_ITEM,
        {"learning_rate": 0.002},
        {"steps": 400, "precision": "float32", "averaging": {"kind": "swa"}},
    )
    assert configuration == {"backbone": "fno1d", "learning_rate": 0.002}
    assert train_use["precision"] == "float32"


@pytest.mark.parametrize(
    "configuration, train_use, code",
    [
        ({"arch": {"modes": 8}}, {}, "catalog_setting_unknown"),
        ({}, {"distill": {"teacher": {"backbone": "mlp"}}}, "catalog_setting_invalid"),
        (
            {},
            {"search": {"candidates": [{"backbone": "mlp"}]}},
            "catalog_setting_invalid",
        ),
        ({}, {"precision": "int8"}, "catalog_setting_invalid"),
    ],
)
def test_the_jax_levers_build_refuses_what_it_would(configuration, train_use, code):
    with pytest.raises(catalog_entries.CatalogRefused) as refused:
        settings.resolve(JAX_ITEM, configuration, train_use)
    assert refused.value.code == code


def test_torch_levers_still_refuse_float32_precision():
    with pytest.raises(catalog_entries.CatalogRefused):
        settings.resolve(pipeline.entry("neuralop.FNO"), {}, {"precision": "float32"})


def test_each_entry_names_its_own_runtime_and_jno_keeps_its_build_name():
    for item in pipeline.entries():
        runtime = item["bundle_ref"]["runtime_profile_id"]
        if item["catalog_id"] in JNO:
            assert runtime == "python-cpu-py311"
            assert item["settings_schema"] == "carbon-candidate-jax-levers-v1"
            assert item["backbone"] == item["catalog_id"].removeprefix("jno.")
        else:
            assert runtime == "torch-cpu-py311"


def test_no_entry_names_thuml_transolver_plus_until_its_noise_free_receipt():
    """A deliberate absence (Validator, 2026-10-20), not a forgotten entry.

    Every shipped coverage bundle carries `thuml.Transolver_plus` and its MIT
    source, unreachable because no entry names that catalog id and
    `settings.resolve` sets the entry's own backbone last. Upstream samples
    Gumbel noise (`rand_like`) on every forward pass, inference included.

    WHAT LIFTS THIS GUARD: the Validator's receipt for a separate Transolver++
    entry whose bundle's eval forward is noise-free (the Gumbel noise used only
    while training, from the training loop's seeded generator) and whose two
    inferences of one trained state are bit-identical, i.e. the packet
    `codex-queue/inputs/motor_step1/catalog_clean/t_thuml_transolver_plus_baseline`
    (owner yes, 2026-10-20) once pair-identity and that receipt exist. Replace
    this test with that entry's own noise-free double-inference test then.
    """
    named = {e["catalog_id"] for e in pipeline.entries()} | {
        e["backbone"] for e in pipeline.entries()
    }
    assert "thuml.Transolver_plus" not in named


# --- ruling 1: offered on another version only when TRAIN and interface match --


@pytest.mark.parametrize("field", ["train_digest", "interface_digest"])
def test_an_offered_version_whose_kit_differs_from_the_tested_one_is_refused(
    monkeypatch, field
):
    # Motor entries are tested on 1.0 and offered on 1.2/1.3, whose TRAIN and
    # interface are byte-equal today. A version whose kit differed would need
    # a re-run there.
    real = pipeline._served_kit_digests

    def drifted(challenge_id, version):
        digests = dict(real(challenge_id, version))
        if version == "1.3":
            digests[field] = "sha256:" + "f" * 64
        return digests

    monkeypatch.setattr(pipeline, "_served_kit_digests", drifted)
    with pytest.raises(pipeline.CatalogBroken, match="re-run it there"):
        pipeline.verify(pipeline.entry("neuralop.FNO"))


def test_every_receipt_binds_its_packet_kits_train_and_interface():
    for item in pipeline.entries():
        receipt = json.loads(
            (pipeline.RECEIPTS / (item["catalog_id"] + ".json")).read_bytes()
        )
        tested_id, tested_version = receipt["tested_on"].split("@")
        kit = pipeline._served_kit_digests(tested_id, tested_version)
        assert receipt["tested_train_digest"] == kit["train_digest"]
        assert receipt["tested_interface_digest"] == kit["interface_digest"]


def test_bind_refuses_a_malformed_tested_digest(tmp_path, monkeypatch):
    receipts = tmp_path / "receipts"
    shutil.copytree(pipeline.RECEIPTS, receipts)
    monkeypatch.setattr(pipeline, "RECEIPTS", receipts)
    bound = json.loads((receipts / "neuralop.FNO.json").read_bytes())
    with pytest.raises(pipeline.CatalogBroken, match="tested_train_digest"):
        pipeline.bind(
            "neuralop.FNO",
            tested_on=bound["tested_on"],
            image_digest=bound["image_digest"],
            tested_train_digest="not-a-digest",
        )
