"""Catalog install on a receiver host (OWNER-BACKBONE-CATALOG-01; Test Lead,
2026-10-20: a receiver has no Launchpad miner setup, so `pipeline install`
refused `step_not_checked` there). A receiver install reads the receiver's own
operator record and installs over the parent, into the cache, that the
receiver verifies when it starts; it never asks for a miner setup."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from carbon.backbone_catalog import pipeline
from carbon.challenge_validator import direct_receiver
from carbon.reconstruction import torch_profile
from carbon.reconstruction.worker.model import WorkerImageIdentity
from scripts.dev import catalog_install, library_bundle

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return "sha256:" + hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def torch_parent(**changes):
    fields = {
        "image_id": "sha256:" + "b" * 64,
        "config_digest": "sha256:" + "b" * 64,
        "source_tree_digest": "sha256:" + "c" * 64,
        "wheel_digest": "sha256:" + "d" * 64,
        "lock_digest": torch_profile.requirements_digest(ROOT),
        "base_image_digest": "sha256:" + "a" * 64,
        "build_recipe_digest": sha(".devcontainer/torch/Dockerfile"),
        "entrypoint_digest": sha("carbon/reconstruction/worker/entrypoint.py"),
    }
    return WorkerImageIdentity(**{**fields, **changes})


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    campaigns = tmp_path / "environment" / "campaigns"
    campaigns.mkdir(parents=True, mode=0o700)
    cache = campaigns / ".direct-development" / "library-cache"
    host = {"parent": torch_parent(), "installed": [], "sources": []}
    config = tmp_path / "receiver.json"
    config.write_text("{}", encoding="utf-8")

    def load_config(path):
        assert path == config
        return {"runner_profile": str(tmp_path / "runner-profile.json")}

    def installed_source(profile_path, **kwargs):
        host["sources"].append((profile_path, kwargs))
        return {}, host["parent"], None, cache

    def install(directory, cache_root, parent, *, expected_bundle, cli):
        del cli
        host["installed"].append((cache_root, parent, expected_bundle))

        class Image:
            bundle_ref = expected_bundle.to_dict()

        return Image()

    def no_miner_setup(*_args, **_kwargs):
        pytest.fail("a receiver install read the miner setup")

    monkeypatch.setattr(direct_receiver, "load_config", load_config)
    monkeypatch.setattr(direct_receiver, "installed_source", installed_source)
    monkeypatch.setattr(library_bundle, "install_pinned_library_worker_image", install)
    monkeypatch.setattr(library_bundle, "DockerCLI", lambda: object())
    monkeypatch.setattr(library_bundle, "EnvironmentSetup", no_miner_setup)
    host.update(config=config, cache=cache)
    return host


def test_a_receiver_installs_over_its_own_parent_into_its_own_cache(receiver):
    installed = catalog_install.install(
        ["neuralop.FNO"], receiver_config=receiver["config"]
    )
    item = pipeline.entry("neuralop.FNO")
    assert installed == [
        {
            "catalog_id": "neuralop.FNO",
            "status": "INSTALLED_VERIFIED",
            "host": "receiver",
            "bundle_ref": item["bundle_ref"],
            "parent_image": receiver["parent"].image_id,
            "qualification": "DEVELOPMENT_ONLY",
        }
    ]
    [(cache_root, parent, bundle)] = receiver["installed"]
    assert cache_root == receiver["cache"] and cache_root.is_dir()
    assert parent == receiver["parent"]
    assert bundle.to_dict() == item["bundle_ref"]
    # The receiver's own start-up check chose the parent and cache.
    assert len(receiver["sources"]) == 1


def test_a_receiver_parent_that_cannot_build_the_runtime_is_not_served(receiver):
    receiver["parent"] = torch_parent(lock_digest=sha("uv.lock"))
    with pytest.raises(ValueError, match="backend_not_served"):
        catalog_install.install(["neuralop.FNO"], receiver_config=receiver["config"])
    assert receiver["installed"] == []


def test_a_receiver_without_its_campaigns_root_is_refused(receiver):
    receiver["cache"].parent.parent.rmdir()
    with pytest.raises(ValueError, match="campaigns root missing"):
        catalog_install.install(["neuralop.FNO"], receiver_config=receiver["config"])
    assert receiver["installed"] == []


def test_install_is_for_a_miner_or_a_receiver_never_both(tmp_path, capsys):
    with pytest.raises(pipeline.CatalogBroken, match="not both"):
        catalog_install.install(state_dir=tmp_path, receiver_config=tmp_path / "r.json")
    with pytest.raises(SystemExit):
        catalog_install.main(
            ["--state-dir", str(tmp_path), "--receiver-config", "r.json"]
        )
    assert "not allowed with" in capsys.readouterr().err


def test_the_old_pipeline_install_names_the_owner_installer(capsys):
    # The catalog package imports nothing from scripts/ (Validator): the old
    # command refuses and names the new one, never installing.
    assert pipeline.main(["install", "neuralop.FNO", "--receiver-config", "r"]) == 2
    err = capsys.readouterr().err
    assert (
        "python -m scripts.dev.catalog_install neuralop.FNO --receiver-config r" in err
    )


def test_the_cli_passes_the_receiver_record(receiver, capsys):
    assert (
        catalog_install.main(
            ["neuralop.FNO", "--receiver-config", str(receiver["config"])]
        )
        == 0
    )
    assert '"host": "receiver"' in capsys.readouterr().out


def test_an_opted_in_receiver_installs_each_runtime_over_its_own_parent(
    receiver, monkeypatch
):
    from carbon.development_session.gpu_practice import DirectParents

    parents = DirectParents.from_torch(receiver["parent"])
    loaded = direct_receiver.load_config

    def opted_in(path):
        return {
            **loaded(path),
            "construction_runtimes": direct_receiver.CONSTRUCTION_RUNTIMES,
        }

    monkeypatch.setattr(direct_receiver, "load_config", opted_in)
    monkeypatch.setattr(
        direct_receiver, "construction_parents", lambda parent, _impl: parents
    )
    catalog_install.install(
        ["jno.fno1d", "neuralop.FNO"], receiver_config=receiver["config"]
    )
    assert [
        (parent, bundle.runtime_profile_id)
        for _, parent, bundle in receiver["installed"]
    ] == [
        (parents.for_runtime("python-cpu-py311"), "python-cpu-py311"),
        (receiver["parent"], "torch-cpu-py311"),
    ]


def test_a_receiver_that_did_not_opt_in_does_not_serve_jno(receiver):
    with pytest.raises(ValueError, match="backend_not_served"):
        catalog_install.install(["jno.fno1d"], receiver_config=receiver["config"])
    assert receiver["installed"] == []
