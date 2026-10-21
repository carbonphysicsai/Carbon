"""The backbone catalog (OWNER-BACKBONE-CATALOG-01): a tested backbone is
selected by id and bounded settings, and Carbon's pinned code builds and
trains it deterministically. No graph, no miner source, no weights."""

from __future__ import annotations

import json

import numpy as np
import pytest

from carbon.backbone_catalog import entries

MOTOR_SHAPE = (8, 60, (6, 10))


def test_every_entry_is_pinned_and_its_defaults_resolve():
    for item in entries.ENTRIES:
        assert item.library in entries.LIBRARIES
        assert item.adapter in entries.ADAPTERS
        settings = entries.resolve(item.catalog_id, {})
        assert set(settings) == {s.name for s in item.settings + entries.TRAINING}
    document = entries.document()
    assert json.loads(json.dumps(document)) == document
    assert set(document["entries"]) == {e.catalog_id for e in entries.ENTRIES}
    assert not set(document["entries"]) & set(entries.LIMITS)


def test_only_the_step_count_has_no_fixed_cap():
    uncapped = {
        (item.catalog_id, s.name)
        for item in entries.ENTRIES
        for s in item.settings + entries.TRAINING
        if s.kind != "choice" and s.high is None
    }
    assert {name for _, name in uncapped} == {"steps"}


@pytest.mark.parametrize(
    "catalog_id, settings, code",
    [
        ("neuralop.FNOX", {}, "catalog_entry_unknown"),
        ("neuralop.SFNO", {}, "catalog_entry_unknown"),
        ("neuralop.FNO", {"width": 3}, "catalog_setting_unknown"),
        ("neuralop.FNO", {"n_modes": 0}, "catalog_setting_invalid"),
        ("neuralop.FNO", {"n_modes": 2.0}, "catalog_setting_invalid"),
        ("neuralop.FNO", {"hidden_channels": True}, "catalog_setting_invalid"),
        ("neuralop.FNO", {"learning_rate": float("nan")}, "catalog_setting_invalid"),
        ("neuralop.TFNO", {"factorization": "dense"}, "catalog_setting_invalid"),
        (
            "physicsnemo.AFNO",
            {"embed_dim": 30, "num_blocks": 4},
            "catalog_settings_inconsistent",
        ),
        ("neuralop.FNO", [], "catalog_setting_invalid"),
    ],
)
def test_a_bad_selection_is_refused_with_its_code(catalog_id, settings, code):
    with pytest.raises(entries.CatalogRefused) as refused:
        entries.resolve(catalog_id, settings)
    assert refused.value.code == code


def test_a_documented_limit_says_why():
    with pytest.raises(entries.CatalogRefused, match="torch-harmonics"):
        entries.entry("neuralop.LocalNO")


# --- Carbon's pinned code: needs the Torch build base -------------------------

torch = pytest.importorskip("torch")
pytest.importorskip("neuralop")
pytest.importorskip("physicsnemo")

from carbon.backbone_catalog import torch_backbones, torch_loop


def _shape():
    return torch_backbones.Shape(*MOTOR_SHAPE)


def _train(cases=12):
    rng = np.random.default_rng(7)
    x = rng.uniform(-1.0, 1.0, (cases, 8))
    angle = np.linspace(0.0, 1.0, 60)
    y = np.sin(2 * np.pi * (angle[None, :] + x[:, :1])) * (1.0 + x[:, 1:2]) + 3.0
    return x, y


@pytest.mark.parametrize("catalog_id", [e.catalog_id for e in entries.ENTRIES])
def test_every_entry_trains_and_predicts_on_motors_shape(catalog_id):
    x, y = _train()
    fitted, record = torch_loop.fit(
        catalog_id, {"steps": 3}, x, y, seed=11, shape=_shape()
    )
    out = fitted.predict(x)
    assert out.shape == (12, 60) and out.dtype == np.float64 and np.isfinite(out).all()
    assert record["catalog_id"] == catalog_id and record["threads"] == 1
    assert record["settings"]["steps"] == 3 and record["parameters"] > 0


@pytest.mark.parametrize(
    "catalog_id", ["neuralop.FNO", "physicsnemo.AFNO", "neuralop.GINO"]
)
def test_the_same_seed_rebuilds_the_same_model(catalog_id):
    x, y = _train()
    first, _ = torch_loop.fit(catalog_id, {"steps": 4}, x, y, seed=5, shape=_shape())
    second, _ = torch_loop.fit(catalog_id, {"steps": 4}, x, y, seed=5, shape=_shape())
    other, _ = torch_loop.fit(catalog_id, {"steps": 4}, x, y, seed=6, shape=_shape())
    assert np.array_equal(first.predict(x), second.predict(x))
    assert not np.array_equal(first.predict(x), other.predict(x))


def test_modes_past_the_grid_are_refused():
    x, y = _train()
    with pytest.raises(entries.CatalogRefused) as refused:
        torch_loop.fit(
            "neuralop.FNO",
            {"n_modes": 30, "steps": 1},
            x[:, :8],
            y[:, :40],
            seed=1,
            shape=torch_backbones.Shape(8, 40, (5, 8)),
        )
    assert refused.value.code == "catalog_settings_inconsistent"


def test_an_unpinned_library_is_refused(monkeypatch):
    monkeypatch.setitem(entries.LIBRARIES, "neuraloperator", ("neuralop", "0.0.1"))
    x, y = _train()
    with pytest.raises(entries.CatalogRefused) as refused:
        torch_loop.fit("neuralop.FNO", {"steps": 1}, x, y, seed=1, shape=_shape())
    assert refused.value.code == "catalog_library_not_pinned"


def test_a_seed_is_required():
    x, y = _train()
    with pytest.raises(ValueError, match="seed"):
        torch_loop.fit("neuralop.FNO", {"steps": 1}, x, y, seed=None, shape=_shape())


def test_fit_leaves_torchs_process_settings_as_it_found_them():
    x, y = _train()
    before = torch.get_num_threads(), torch.are_deterministic_algorithms_enabled()
    fitted, _ = torch_loop.fit(
        "neuralop.FNO", {"steps": 1}, x, y, seed=1, shape=_shape()
    )
    fitted.predict(x)
    assert (
        torch.get_num_threads(),
        torch.are_deterministic_algorithms_enabled(),
    ) == before
