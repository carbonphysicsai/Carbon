"""The catalog install finds the host's wheelhouse (M1 rehearsal, 2026-10-21).

`python -m scripts.dev.catalog_install` reads the pinned wheels from
`--wheelhouse`, by default the host's own `~/.carbon/catalog-wheelhouse`
(`scripts.dev.catalog_wheelhouse`) when it exists. Without one, an install of
every entry installs the entries that need no wheels and skips each that does,
naming the command that builds the wheelhouse; an entry named by id that needs
wheels is refused, as before.
"""

from __future__ import annotations

import json

import pytest

from carbon.backbone_catalog import pipeline
from scripts.dev import catalog_install, catalog_wheelhouse


def _wheel_ids():
    return {
        item["catalog_id"]
        for item in pipeline.load()["entries"]
        if json.loads(pipeline.bundle_files(item)["bundle.json"])["wheels"]
    }


@pytest.fixture
def host(tmp_path, monkeypatch):
    seen = {"wheelhouse": {}, "installed": []}

    def bundle_directory(item, target, *, wheelhouse=None):
        seen["wheelhouse"][item["catalog_id"]] = wheelhouse
        if item["catalog_id"] in _wheel_ids() and wheelhouse is None:
            raise pipeline.CatalogBroken(
                f"{item['catalog_id']}: its pinned wheels need --wheelhouse"
            )
        return target

    def install_bundle(directory, **kwargs):
        seen["installed"].append(directory)
        return {"status": "INSTALLED_VERIFIED"}

    monkeypatch.setattr(pipeline, "bundle_directory", bundle_directory)
    monkeypatch.setattr(
        catalog_install.library_bundle, "install_bundle", install_bundle
    )
    monkeypatch.setattr(
        catalog_wheelhouse, "DEFAULT_DIRECTORY", tmp_path / "no-wheelhouse"
    )
    return seen


def test_without_a_wheelhouse_the_wheel_entries_are_skipped_by_name(host, capsys):
    wheels = _wheel_ids()
    assert wheels, "the catalog has entries with pinned wheels"
    installed = catalog_install.install(state_dir=None)
    names = {item["catalog_id"] for item in installed}
    everything = {item["catalog_id"] for item in pipeline.load()["entries"]}
    assert names == everything - wheels
    err = capsys.readouterr().err
    for catalog_id in wheels:
        assert f"skipped {catalog_id}:" in err
    assert catalog_install.WHEELHOUSE_STEP in err


def test_the_host_wheelhouse_is_used_when_it_exists(host, tmp_path, monkeypatch):
    built = tmp_path / "catalog-wheelhouse"
    built.mkdir(mode=0o700)
    monkeypatch.setattr(catalog_wheelhouse, "DEFAULT_DIRECTORY", built)
    installed = catalog_install.install()
    assert len(installed) == len(pipeline.load()["entries"])
    assert set(host["wheelhouse"].values()) == {built}


def test_a_named_wheel_entry_without_a_wheelhouse_is_refused(host):
    (catalog_id,) = sorted(_wheel_ids())[:1]
    with pytest.raises(pipeline.CatalogBroken, match="--wheelhouse"):
        catalog_install.install([catalog_id])


def test_an_explicit_wheelhouse_wins_over_the_default(host, tmp_path, monkeypatch):
    built = tmp_path / "catalog-wheelhouse"
    built.mkdir(mode=0o700)
    monkeypatch.setattr(catalog_wheelhouse, "DEFAULT_DIRECTORY", built)
    mine = tmp_path / "mine"
    catalog_install.install(sorted(_wheel_ids())[:1], wheelhouse=mine)
    assert set(host["wheelhouse"].values()) == {mine}
