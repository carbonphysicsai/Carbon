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
#: The five clean tested Torch entries. The DeepXDE/THUML six are out until
#: their bundles are rebuilt without KNO/WNO and re-tested (owner, 2026-10-20).
TORCH = {
    "neuralop.FNO",
    "neuralop.TFNO",
    "neuralop.UQNO",
    "physicsnemo.FullyConnected",
    "transolver",
}
#: A coverage-build entry as the cleaned DeepXDE/THUML bundles will declare it.
COVERAGE_ITEM = {
    "catalog_id": "thuml.FNO",
    "backbone": "thuml.FNO",
    "settings_schema": "carbon-candidate-coverage-v1",
    "defaults": {
        "configuration": {"backbone": "thuml.FNO", "learning_rate": 0.001},
        "train_use": {},
    },
}


def test_every_entry_verifies_and_motor_1_2_offers_the_eleven_torch_backbones():
    assert set(pipeline.verify_all()) == TORCH
    assert {
        e["catalog_id"] for e in pipeline.entries(MOTOR["id"], MOTOR["version"])
    } == TORCH
    # Never on a released or step-2 version (Validator): only Motor 1.2.
    for item in pipeline.entries():
        assert item["challenges"] == [MOTOR]
    for version in ("1.0", "1.1"):
        assert pipeline.entries(MOTOR["id"], version) == []


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
