"""The catalog's GPU twins are staged for the GPU workers an install has
(M1 E2E S4).

On the 12g rehearsal every catalog GPU practice fell back to CPU before the
remote GPU was used: "pinned bundle material is not staged". The catalog
install staged each entry's CPU build only, never its GPU twin's material,
which practice's GPU build prepares the overlay from. These tests hold:
- `pipeline.twin_directory` writes an entry's pinned twin for a runtime it
  has a build for, and refuses one it has none for;
- `catalog_install` stages each entry's twin for every GPU runtime the
  install's GPU workers serve, names one it cannot stage, and goes on;
- the catalog's state counts an entry whose served twin is not staged as
  not installed, so setup lists the catalog step and the page installs it;
- setup's compute check starts the twins' staging when it adds a GPU worker,
  inertly (`catalog_install --gpu-twins-only`), and never fails for it.
"""

from __future__ import annotations

import json

import pytest

from carbon.backbone_catalog import pipeline
from scripts.dev import catalog_install
from scripts.dev.miner_launchpad import catalog_build, catalog_state

TORCH = "torch-cu130-py311"
JAX = "jax-cuda13-py311"


def with_twin(runtime):
    return next(
        item
        for item in pipeline.load()["entries"]
        if runtime in (item.get("bundle_refs") or {})
    )


def test_a_twin_directory_holds_the_pinned_twin(tmp_path):
    item, runtime = next(
        (item, runtime)
        for item in pipeline.load()["entries"]
        for runtime in (item.get("bundle_refs") or {})
        if not json.loads(
            (
                pipeline.BUNDLES / item["catalog_id"] / runtime / "bundle.json"
            ).read_bytes()
        )["wheels"]
    )
    target = pipeline.twin_directory(item, runtime, tmp_path / "twin")
    for name in ("bundle.json", "source.tar.gz", "requirements.txt", "LICENSE"):
        assert (target / name).read_bytes() == (
            pipeline.BUNDLES / item["catalog_id"] / runtime / name
        ).read_bytes()
    other = JAX if runtime == TORCH else TORCH
    if other not in (item.get("bundle_refs") or {}):
        with pytest.raises(pipeline.CatalogBroken, match=f"no {other} build"):
            pipeline.twin_directory(item, other, tmp_path / "none")


def test_the_install_stages_each_served_twin_and_names_one_it_cannot(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(catalog_install, "gpu_runtimes", lambda state_dir: [TORCH])
    written, staged = [], []

    def twin_directory(item, runtime, target, *, wheelhouse=None):
        written.append((item["catalog_id"], runtime))
        if len(written) == 1:
            raise pipeline.CatalogBroken(f"{item['catalog_id']}: wheel x is missing")
        return target

    monkeypatch.setattr(pipeline, "twin_directory", twin_directory)
    monkeypatch.setattr(
        catalog_install.library_bundle,
        "stage_bundle",
        lambda directory, state_dir: staged.append(directory),
    )
    skipped = []
    done = catalog_install.stage_gpu_twins(state_dir=tmp_path, skipped=skipped)
    torch_twins = [
        item["catalog_id"]
        for item in pipeline.load()["entries"]
        if TORCH in (item.get("bundle_refs") or {})
    ]
    assert [w[0] for w in written] == torch_twins
    assert len(done) == len(torch_twins) - 1 == len(staged)
    assert skipped == [
        {
            "catalog_id": torch_twins[0],
            "reason": "gpu_twin_not_staged",
            "runtime": TORCH,
            "detail": f"CatalogBroken: {torch_twins[0]}: wheel x is missing",
        }
    ]
    # No GPU worker: nothing is staged.
    monkeypatch.setattr(catalog_install, "gpu_runtimes", lambda state_dir: [])
    assert catalog_install.stage_gpu_twins(state_dir=tmp_path) == []


def test_an_unstaged_served_twin_reads_not_installed(tmp_path, monkeypatch):
    item = with_twin(TORCH)
    cpu = item["bundle_ref"]
    parent = "sha256:" + "2" * 64
    cfg = {"campaigns_root": str(tmp_path / "campaigns")}
    root = catalog_state.cache_root(cfg)
    receipt = root / cpu["bundle_digest"][7:] / (parent[7:] + ".image.json")
    receipt.parent.mkdir(parents=True)
    receipt.write_text("{}")
    from carbon.backbone_catalog import listing

    monkeypatch.setattr(listing, "load", lambda: {"entries": [item]})
    served = {cpu["runtime_profile_id"]: parent}
    monkeypatch.setattr(catalog_state, "parents", lambda _: dict(served))
    assert catalog_state.state(cfg)["missing"] == []  # no GPU worker
    served[TORCH] = "sha256:" + "3" * 64
    assert catalog_state.state(cfg)["missing"] == [item["catalog_id"]]
    twin = item["bundle_refs"][TORCH]["bundle_digest"]
    (root / "materials" / twin[7:]).mkdir(parents=True)
    assert catalog_state.state(cfg)["missing"] == []
    assert catalog_state.progress(cfg)["installed"] == 1


def test_staging_the_twins_spawns_the_inert_install(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    spawned = []
    assert catalog_build.stage_twins(state, []) is False
    assert catalog_build.stage_twins(
        state, [TORCH], spawn=lambda argv, **kw: spawned.append((argv, kw))
    )
    ((argv, kw),) = spawned
    assert argv[1:] == [
        "-B",
        "-m",
        "scripts.dev.catalog_install",
        "--state-dir",
        str(state),
        "--gpu-twins-only",
    ]
    assert kw["start_new_session"] is True


def test_the_compute_check_starts_the_twins_staging(tmp_path, monkeypatch):
    from test_battery_gpu_practice import HOTKEY, Onboarding
    from test_gpu_per_backend import JAX as JAX_IMAGE
    from test_gpu_per_backend import MOTOR, BothChecks

    from scripts.dev.miner_launchpad.environment_setup import (
        LOCAL_GPU,
        EnvironmentSetup,
    )

    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    home = tmp_path / "miner"
    home.mkdir(mode=0o700)
    for name in ("worker.json", "analysis.json", "gpu.json"):
        (home / name).write_text("{}")
    setup = EnvironmentSetup(root, onboarding=Onboarding(), checks=BothChecks())
    setup.begin({"address": HOTKEY})
    monkeypatch.setattr(catalog_state, "parents", lambda cfg: {JAX: "x", "c": "y"})
    started = []
    monkeypatch.setattr(
        catalog_build,
        "stage_twins",
        lambda state_dir, runtimes: started.append((state_dir, runtimes)),
    )
    setup.compute(
        {
            "choice": LOCAL_GPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
            "gpu_image_manifest": str(home / "gpu.json"),
            "challenge": MOTOR,
        }
    )
    assert started == [(root, [JAX])]
    assert JAX_IMAGE is not None
    # A failure to stage never fails the check.
    monkeypatch.setattr(catalog_build, "stage_twins", lambda state_dir, runtimes: 1 / 0)
    setup.compute(
        {
            "choice": LOCAL_GPU,
            "image_manifest": str(home / "worker.json"),
            "analysis_image_manifest": str(home / "analysis.json"),
            "gpu_image_manifest": str(home / "gpu.json"),
            "challenge": MOTOR,
        }
    )
