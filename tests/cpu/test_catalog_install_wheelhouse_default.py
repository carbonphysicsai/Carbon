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
    for item in pipeline.load()["entries"]:
        for name in json.loads(pipeline.bundle_files(item)["bundle.json"])["wheels"]:
            (built / name).write_bytes(b"fixture")
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


def test_a_wheel_missing_from_the_wheelhouse_skips_only_its_entries(
    host, tmp_path, monkeypatch, capsys
):
    """M1 E2E R10-1: new entries pinned a wheel an existing wheelhouse
    lacked, and the whole catalog stopped at 12 of 56. Each entry needing it
    is skipped and named with the wheel; every other entry installs."""
    declared = {
        item["catalog_id"]: json.loads(pipeline.bundle_files(item)["bundle.json"])[
            "wheels"
        ]
        for item in pipeline.load()["entries"]
    }
    every = {name for wheels in declared.values() for name in wheels}
    gone = min(every)
    built = tmp_path / "catalog-wheelhouse"
    built.mkdir(mode=0o700)
    for name in every - {gone}:
        (built / name).write_bytes(b"fixture")
    monkeypatch.setattr(catalog_wheelhouse, "DEFAULT_DIRECTORY", built)
    skipped = []
    installed = catalog_install.install(skipped=skipped)
    needing = {cid for cid, wheels in declared.items() if gone in wheels}
    assert needing
    assert {s["catalog_id"] for s in skipped} == needing
    assert {s["reason"] for s in skipped} == {"wheel_missing"}
    assert {s["wheel"] for s in skipped} == {gone}
    assert {i["catalog_id"] for i in installed} == set(declared) - needing
    err = capsys.readouterr().err
    assert f"its pinned wheel {gone} is not in the wheelhouse" in err


def test_one_entrys_failed_install_never_stops_the_rest(host, tmp_path, monkeypatch):
    built = tmp_path / "catalog-wheelhouse"
    built.mkdir(mode=0o700)
    monkeypatch.setattr(catalog_wheelhouse, "DEFAULT_DIRECTORY", built)
    monkeypatch.setattr(catalog_install, "_missing_wheel", lambda item, house: None)
    first = pipeline.load()["entries"][0]["catalog_id"]
    calls = []

    def install_bundle(directory, **kwargs):
        calls.append(directory)
        if len(calls) == 1:
            raise RuntimeError("docker build failed")
        return {"status": "INSTALLED_VERIFIED"}

    monkeypatch.setattr(
        catalog_install.library_bundle, "install_bundle", install_bundle
    )
    skipped = []
    installed = catalog_install.install(skipped=skipped)
    assert skipped == [
        {
            "catalog_id": first,
            "reason": "install_failed",
            "detail": "RuntimeError: docker build failed",
        }
    ]
    assert len(installed) == len(pipeline.load()["entries"]) - 1


def test_the_report_names_what_was_skipped(host, tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    assert catalog_install.main(["--report", str(report)]) == 0
    written = json.loads(report.read_text())
    assert {s["catalog_id"] for s in written["skipped"]} == _wheel_ids()
    assert {s["reason"] for s in written["skipped"]} == {"wheelhouse_missing"}
