"""The catalog wheelhouse builder: pinned by the catalog's manifests, never keeps
a wheel whose hash differs, owner-only, idempotent, and refuses anything else it
finds in the directory (scripts/dev/catalog_wheelhouse.py)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

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


@posix_only
def test_a_wheelhouse_built_for_an_earlier_catalog_is_brought_up_to_date(
    parts, tmp_path
):
    """M1 E2E R10-1: new entries pinned wheels an existing wheelhouse lacked.
    A run adds each missing pinned wheel and removes a recorded wheel nothing
    pins any more; a file it never recorded is still refused."""
    checkout, source, wheels = parts
    target = tmp_path / "house"
    wheelhouse.build(target, sources=[source], checkout=checkout)
    name = min(wheels)
    (target / name).unlink()
    old = "retired-1.0-py3-none-any.whl"
    (target / old).write_bytes(b"old")
    record = json.loads((target / wheelhouse.RECORD).read_text())
    record["wheels"][old] = {"bytes": 3, "sha256": "0" * 64}
    (target / wheelhouse.RECORD).write_text(json.dumps(record))
    built = wheelhouse.build(target, sources=[source], checkout=checkout)
    assert (target / name).is_file() and not (target / old).exists()
    assert set(built["wheels"]) == set(wheels)
    assert json.loads((target / wheelhouse.RECORD).read_text()) == built
    (target / "stray.txt").write_text("x")
    with pytest.raises(wheelhouse.WheelhouseRefused, match="different contents"):
        wheelhouse.build(target, sources=[source], checkout=checkout)


SDIST_PYPROJECT = b"""[build-system]
requires = ["setuptools", "setuptools-scm"]
build-backend = "setuptools.build_meta"
"""


def _sdist(pyproject=SDIST_PYPROJECT):
    """A source distribution's bytes, with only its pyproject.toml."""
    import io
    import tarfile

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        info = tarfile.TarInfo("pkg-0.7.4/pyproject.toml")
        info.size = len(pyproject)
        tar.addfile(info, io.BytesIO(pyproject))
    return raw.getvalue()


NAME = "pkg-0.7.4-py3-none-any.whl"
BUILD = (
    ("setuptools", "84.2.1", "a" * 64),
    ("setuptools-scm", "10.3.4", "b" * 64),
)


class FakeIndex:
    """pip and the index as `_fetch` meets them: no binary of the wheel, its
    pinned sdist, and the wheel the pinned build environment makes."""

    def __init__(self, built, sdist=None):
        self.built, self.sdist, self.calls = built, sdist or _sdist(), []

    def run(self, command, check, env=None, preexec_fn=None):
        self.calls.append((command, env))
        self.preexec = getattr(self, "preexec", {})
        self.preexec["wheel" if "wheel" in command else "other"] = preexec_fn
        if "--only-binary=:all:" in command and "download" in command:
            raise subprocess.CalledProcessError(1, command)
        if "--require-hashes" in command:
            self.requirements = (
                Path(command[command.index("-r") + 1]).read_text().splitlines()
            )
        if "wheel" in command:
            out = Path(command[command.index("-w") + 1])
            (out / NAME).write_bytes(self.built)

    def download(self, name, filename):
        self.calls.append((["download-sdist", name, filename], None))
        return self.sdist


@pytest.fixture
def index(monkeypatch):
    def make(built, sdist=None, sdist_pin=None):
        fake = FakeIndex(built, sdist)
        pin = {
            "sdist": "pkg-0.7.4.tar.gz",
            "sdist_sha256": sdist_pin or _digest(fake.sdist),
            "build": BUILD,
        }
        monkeypatch.setattr(wheelhouse, "SOURCE_PINS", {NAME: pin})
        monkeypatch.setattr(wheelhouse.subprocess, "run", fake.run)
        monkeypatch.setattr(wheelhouse, "_download_sdist", fake.download)
        return fake

    return make


def test_a_pure_wheel_with_no_binary_is_rebuilt_from_its_pinned_source(index, tmp_path):
    """M1 E2E R10-1 (Validator receipt terms): the sdist's sha256 is checked
    before anything of it runs, the build requirements are installed by
    pinned version and hash into a fresh environment, the build runs without
    pip's isolation, and the wheel is kept only because its sha256 is the
    pin."""
    pinned = b"reproducible wheel bytes"
    fake = index(pinned)
    wheelhouse._fetch(NAME, _digest(pinned), tmp_path)
    assert (tmp_path / NAME).read_bytes() == pinned
    binary, sdist, venv, install, build = [command for command, _ in fake.calls]
    assert "--only-binary=:all:" in binary
    assert sdist == ["download-sdist", NAME, "pkg-0.7.4.tar.gz"]
    assert venv[1:3] == ["-m", "venv"]
    assert "--require-hashes" in install and "--no-deps" in install
    assert fake.requirements == [
        "setuptools==84.2.1 --hash=sha256:" + "a" * 64,
        "setuptools-scm==10.3.4 --hash=sha256:" + "b" * 64,
    ]
    assert "--no-build-isolation" in build and "--no-deps" in build
    assert fake.calls[-1][1]["SOURCE_DATE_EPOCH"] == "0"


def test_a_source_that_differs_from_its_pin_is_refused_before_any_build(
    index, tmp_path
):
    fake = index(b"x", sdist_pin="0" * 64)
    with pytest.raises(wheelhouse.WheelhouseRefused, match="differs from its pin"):
        wheelhouse._fetch(NAME, _digest(b"x"), tmp_path)
    assert [command[0] for command, _ in fake.calls][-1] == "download-sdist"
    assert not (tmp_path / NAME).exists()


def test_a_build_requirement_that_is_not_pinned_is_refused_before_any_build(
    index, tmp_path
):
    unpinned = _sdist(b'[build-system]\nrequires = ["setuptools", "hatchling>=1"]\n')
    fake = index(b"x", sdist=unpinned)
    with pytest.raises(wheelhouse.WheelhouseRefused, match="'hatchling>=1' is not"):
        wheelhouse._fetch(NAME, _digest(b"x"), tmp_path)
    assert [command[0] for command, _ in fake.calls][-1] == "download-sdist"


def test_a_rebuilt_wheel_that_differs_from_its_pin_is_never_kept(index, tmp_path):
    index(b"other")
    with pytest.raises(wheelhouse.WheelhouseRefused, match="not the pinned one"):
        wheelhouse._fetch(NAME, _digest(b"pinned"), tmp_path)
    assert not (tmp_path / NAME).exists()


def test_a_wheel_without_a_source_pin_is_never_built(index, tmp_path):
    fake = index(b"x")
    other = "unpinned-1.0-py3-none-any.whl"
    with pytest.raises(wheelhouse.WheelhouseRefused, match="no pinned source"):
        wheelhouse._fetch(other, _digest(b"x"), tmp_path)
    assert len(fake.calls) == 1  # the binary download only


def test_a_platform_wheel_is_never_rebuilt_from_source(index, tmp_path):
    fake = index(b"x")
    with pytest.raises(subprocess.CalledProcessError):
        wheelhouse._fetch(
            "native-1.0-cp311-cp311-manylinux_2_17_x86_64.whl", _digest(b"x"), tmp_path
        )
    assert len(fake.calls) == 1


def test_the_torch_harmonics_source_pin_names_every_build_requirement():
    """The one source pin: its sdist and each build requirement by exact
    version and a full sha256."""
    pin = wheelhouse.SOURCE_PINS["torch_harmonics-0.7.4-py3-none-any.whl"]
    assert pin["sdist"] == "torch_harmonics-0.7.4.tar.gz"
    assert wheelhouse.SHA256.fullmatch(pin["sdist_sha256"])
    assert {project for project, _, _ in pin["build"]} >= {
        "setuptools",
        "setuptools-scm",
    }
    for _, version, digest in pin["build"]:
        assert version and wheelhouse.SHA256.fullmatch(digest)


def test_the_rebuild_does_not_depend_on_the_owners_umask(index, tmp_path):
    """M1 rc26: the same pinned source built to a different wheel under an owner umask of 077 (0e2437f8...) than
    under 022 (the pin, 326941e1...): the zip's file modes follow what pip extracted. The build child now runs with
    umask 022, whatever the host's."""
    import os

    pinned = b"reproducible wheel bytes"
    fake = index(pinned)
    wheelhouse._fetch(NAME, _digest(pinned), tmp_path)
    child = fake.preexec["wheel"]
    assert child is wheelhouse._build_umask
    ambient = os.umask(0o077)
    try:
        child()  # what the forked build process does before pip runs
        assert os.umask(0o077) == 0o022
    finally:
        os.umask(ambient)
