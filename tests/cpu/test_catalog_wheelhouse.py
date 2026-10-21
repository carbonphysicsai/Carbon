"""The catalog wheelhouse builder: pinned by the catalog's manifests, never keeps
a wheel whose hash differs, owner-only, idempotent, and refuses anything else it
finds in the directory (scripts/dev/catalog_wheelhouse.py)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess

import pytest

from scripts.dev import catalog_wheelhouse as wheelhouse

posix_only = pytest.mark.skipif(os.name != "posix", reason="file modes")


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _catalog(root, entries):
    """A catalog checkout whose entries declare the given {wheel: bytes} sets."""
    for entry, wheels in entries.items():
        directory = root / "carbon" / "backbone_catalog" / "bundles" / entry
        directory.mkdir(parents=True)
        manifest = {"wheels": {n: "sha256:" + _digest(b) for n, b in wheels.items()}}
        (directory / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture
def parts(tmp_path):
    wheels = {
        "alpha-1.0-py3-none-any.whl": b"alpha wheel bytes",
        "beta_gamma-2.1-py3-none-any.whl": b"beta gamma wheel bytes",
    }
    checkout = _catalog(
        tmp_path / "checkout", {"one": wheels, "two": dict(wheels), "none": {}}
    )
    source = tmp_path / "source"
    source.mkdir()
    for name, raw in wheels.items():
        (source / name).write_bytes(raw)
    return checkout, source, wheels


def test_the_real_catalogs_wheel_pins_are_well_formed_when_it_has_any():
    try:
        wanted = wheelhouse.pinned_wheels()
    except wheelhouse.WheelhouseRefused as refused:
        assert "no wheels" in str(refused)  # a catalog of wheel-free entries
        pytest.skip("this catalog's entries declare no wheels")
    assert all(
        name.endswith(".whl") and len(digest) == 64 for name, digest in wanted.items()
    )


def test_the_default_directory_is_the_per_host_private_one():
    assert wheelhouse.DEFAULT_DIRECTORY.parts[-2:] == (".carbon", "catalog-wheelhouse")
    assert wheelhouse.DEFAULT_DIRECTORY.is_relative_to(wheelhouse.Path.home())


def test_requirement_names_come_from_the_wheel_file_names():
    assert (
        wheelhouse.requirement("deepxde-1.15.0-py3-none-any.whl") == "deepxde==1.15.0"
    )
    assert (
        wheelhouse.requirement("scikit_learn-1.7.2-cp311-x-y.whl")
        == "scikit-learn==1.7.2"
    )


def test_the_union_of_every_entrys_wheels_is_pinned_by_its_own_hash(parts):
    checkout, _, wheels = parts
    assert wheelhouse.pinned_wheels(checkout) == {
        name: _digest(raw) for name, raw in wheels.items()
    }


def test_two_entries_that_disagree_on_a_hash_are_refused(tmp_path):
    name = "alpha-1.0-py3-none-any.whl"
    checkout = _catalog(tmp_path, {"one": {name: b"a"}, "two": {name: b"b"}})
    with pytest.raises(wheelhouse.WheelhouseRefused, match="disagree"):
        wheelhouse.pinned_wheels(checkout)


def test_a_catalog_without_wheels_is_refused(tmp_path):
    with pytest.raises(wheelhouse.WheelhouseRefused, match="no wheels"):
        wheelhouse.pinned_wheels(_catalog(tmp_path, {"one": {}}))


def test_a_manifest_naming_a_path_or_a_short_hash_is_refused(tmp_path):
    directory = tmp_path / "carbon" / "backbone_catalog" / "bundles" / "one"
    directory.mkdir(parents=True)
    for wheels in (
        {"../x.whl": "sha256:" + "0" * 64},
        {"a-1-py3-none-any.whl": "sha256:ab"},
    ):
        (directory / "bundle.json").write_text(json.dumps({"wheels": wheels}))
        with pytest.raises(wheelhouse.WheelhouseRefused, match="malformed"):
            wheelhouse.pinned_wheels(tmp_path)


@posix_only
def test_an_offline_build_copies_the_pinned_files_owner_only(parts, tmp_path):
    checkout, source, wheels = parts
    target = tmp_path / "house"
    record = wheelhouse.build(target, sources=[source], checkout=checkout)
    assert sorted(p.name for p in target.iterdir()) == sorted(
        [*wheels, "WHEELHOUSE.json"]
    )
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in target.iterdir())
    for name, raw in wheels.items():
        assert (target / name).read_bytes() == raw
    assert record["wheels"][next(iter(wheels))]["sha256"] == _digest(
        next(iter(wheels.values()))
    )
    assert json.loads((target / "WHEELHOUSE.json").read_text()) == record


def test_a_source_file_with_another_hash_is_not_used_and_the_index_is_asked(
    parts, tmp_path, monkeypatch
):
    checkout, source, wheels = parts
    name = next(iter(wheels))
    (source / name).write_bytes(b"tampered")
    asked = []

    def fetch(wanted_name, hexdigest, into):
        asked.append(wanted_name)
        (into / wanted_name).write_bytes(wheels[wanted_name])

    monkeypatch.setattr(wheelhouse, "_fetch", fetch)
    target = tmp_path / "house"
    wheelhouse.build(target, sources=[source], checkout=checkout)
    assert asked == [name]
    assert (target / name).read_bytes() == wheels[name]


def test_a_fetched_file_with_another_hash_fails_the_build_and_leaves_nothing(
    parts, tmp_path, monkeypatch
):
    checkout, _, _ = parts

    def fetch(name, hexdigest, into):
        (into / name).write_bytes(b"not the pinned bytes")

    monkeypatch.setattr(wheelhouse, "_fetch", fetch)
    target = tmp_path / "house"
    with pytest.raises(wheelhouse.WheelhouseRefused, match="differs from its pin"):
        wheelhouse.build(target, checkout=checkout)
    assert not target.exists()


def test_the_index_download_is_pinned_by_exact_name_and_checked_by_hash(
    tmp_path, monkeypatch
):
    seen = []

    def fake_run(command, check):
        seen.append(command)
        work = command[command.index("-d") + 1]
        with open(os.path.join(work, "alpha-1.0-py3-none-any.whl"), "wb") as handle:
            handle.write(b"other bytes")

    monkeypatch.setattr(wheelhouse.subprocess, "run", fake_run)
    with pytest.raises(wheelhouse.WheelhouseRefused, match="not the pinned one"):
        wheelhouse._fetch("alpha-1.0-py3-none-any.whl", _digest(b"alpha"), tmp_path)
    command = seen[0]
    assert "alpha==1.0" in command and "--no-deps" in command
    assert "--only-binary=:all:" in command


@posix_only
def test_a_second_run_on_the_built_directory_checks_it_and_changes_nothing(
    parts, tmp_path
):
    checkout, source, _ = parts
    target = tmp_path / "house"
    first = wheelhouse.build(target, sources=[source], checkout=checkout)
    before = {p.name: p.stat().st_mtime_ns for p in target.iterdir()}
    assert wheelhouse.build(target, checkout=checkout) == first
    assert {p.name: p.stat().st_mtime_ns for p in target.iterdir()} == before


@posix_only
def test_a_directory_with_anything_else_or_a_wrong_file_is_refused_never_overwritten(
    parts, tmp_path
):
    checkout, source, wheels = parts
    target = tmp_path / "house"
    wheelhouse.build(target, sources=[source], checkout=checkout)
    (target / "extra.txt").write_text("x")
    with pytest.raises(wheelhouse.WheelhouseRefused, match="different contents"):
        wheelhouse.build(target, checkout=checkout)
    (target / "extra.txt").unlink()
    name = next(iter(wheels))
    (target / name).write_bytes(b"changed")
    with pytest.raises(wheelhouse.WheelhouseRefused, match="differs from its pin"):
        wheelhouse.build(target, checkout=checkout)
    assert (target / name).read_bytes() == b"changed"


@posix_only
def test_a_directory_that_is_not_owner_only_is_refused(parts, tmp_path):
    checkout, source, _ = parts
    target = tmp_path / "house"
    wheelhouse.build(target, sources=[source], checkout=checkout)
    os.chmod(target, 0o755)
    with pytest.raises(wheelhouse.WheelhouseRefused, match="owner-only"):
        wheelhouse.build(target, checkout=checkout)


def test_the_command_line_reports_a_refusal_with_status_one(
    tmp_path, capsys, monkeypatch
):
    def refuse(*args, **kwargs):
        raise wheelhouse.WheelhouseRefused("no wheels")

    monkeypatch.setattr(wheelhouse, "build", refuse)
    assert wheelhouse.main([str(tmp_path / "x")]) == 1
    assert "refused: no wheels" in capsys.readouterr().err


def test_a_failed_pip_run_is_a_refusal_not_a_traceback(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        wheelhouse,
        "build",
        lambda *a, **k: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "pip")),
    )
    assert wheelhouse.main([str(tmp_path / "x")]) == 1
    assert "refused:" in capsys.readouterr().err
