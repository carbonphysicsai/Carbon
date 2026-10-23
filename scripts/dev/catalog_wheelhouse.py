"""Build the pinned wheelhouse for the backbone catalog's wheel-bearing entries
(on each miner and receiver host: run by its owner, or by the Control
Center's background catalog install, `scripts/dev/miner_launchpad/
catalog_build.py`, before it installs; never from MCP).

Some catalog entries (deepxde.DeepONetCartesianProd and the THUML ones) declare
wheels in their bundle manifests. `python -m scripts.dev.catalog_install` reads
those wheels from a private operator cache, by default this directory:

    python -m scripts.dev.catalog_wheelhouse [DIR] [--from SOURCE_DIR ...]

DIR defaults to `~/.carbon/catalog-wheelhouse`, owner-only (mode 0700), one per
host. The wheel set is read from this checkout's catalog (the union over every
entry's bundle manifest; two entries that disagree on a hash are refused). Each
wheel is taken from a `--from` directory when one holds a file of that name with
the pinned sha256, and otherwise fetched by exact name and version with
`pip download --no-deps --only-binary=:all:`; a pure-Python wheel the index
has only as source is rebuilt from it with `pip wheel` (isolated,
SOURCE_DATE_EPOCH=0). Either is a network step on the host, by
its owner or the background catalog install it started; never an MCP tool). A
file whose sha256 differs from the catalog's
pin is never kept: the build fails.

`WHEELHOUSE.json` in the directory is the local build record (name, size and
sha256 per wheel); it is not a second pin. A directory this built for an
earlier catalog is brought up to the current pins: missing wheels are added,
and recorded wheels nothing pins any more are removed. The pins are each bundle manifest's,
which `library_bundles.load_cached_wheels` and `validate_bundle` enforce at
install time. Running this on a directory it already built, with unchanged
pins, checks it and changes nothing; a directory with any other content is
refused.

This lives under `scripts/dev`, beside the owner installers, and not in
`carbon.backbone_catalog`: miner paths read the catalog, and nothing they import
may reach these installers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_DIRECTORY = Path.home() / ".carbon" / "catalog-wheelhouse"
RECORD = "WHEELHOUSE.json"
SCHEMA = "carbon.catalog-wheelhouse.v1"
SHA256 = re.compile(r"[0-9a-f]{64}")


class WheelhouseRefused(RuntimeError):
    """The wheelhouse cannot be built as pinned."""


def pinned_wheels(checkout=REPOSITORY):
    """The catalog's wheel set: wheel file name -> sha256 hex, the union over
    every entry's bundle manifest."""
    wanted = {}
    manifests = sorted(
        (Path(checkout) / "carbon" / "backbone_catalog" / "bundles").glob(
            "*/bundle.json"
        )
    )
    for path in manifests:
        for name, digest in json.loads(path.read_bytes()).get("wheels", {}).items():
            hexdigest = digest.removeprefix("sha256:")
            if (
                not name.endswith(".whl")
                or Path(name).name != name
                or SHA256.fullmatch(hexdigest) is None
            ):
                raise WheelhouseRefused(f"{path.parent.name}: malformed wheel {name}")
            if wanted.setdefault(name, hexdigest) != hexdigest:
                raise WheelhouseRefused(f"entries disagree on the hash of {name}")
    if not wanted:
        raise WheelhouseRefused("the catalog declares no wheels")
    return wanted


def requirement(name):
    """`deepxde-1.15.0-py3-none-any.whl` -> `deepxde==1.15.0` (wheel file names
    write `-` inside a distribution name as `_`)."""
    distribution, version = name.split("-")[:2]
    return f"{distribution.replace('_', '-')}=={version}"


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fetch(name, hexdigest, into):
    """One wheel from the index, by exact name and version, kept only if its
    sha256 is the pin. A pure-Python wheel (`py3-none-any`) the index has no
    binary of is rebuilt from its source distribution (`_rebuild`) and kept
    only on the same terms (M1 E2E R10-1: torch_harmonics 0.7.4 is published
    as an sdist only)."""
    with tempfile.TemporaryDirectory() as work:
        found = Path(work) / name
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    requirement(name),
                    "--no-deps",
                    "--only-binary=:all:",
                    "--python-version",
                    "3.11",
                    "--implementation",
                    "cp",
                    "--abi",
                    "cp311",
                    "--platform",
                    "manylinux2014_x86_64",
                    "--platform",
                    "manylinux_2_17_x86_64",
                    "--platform",
                    "manylinux_2_28_x86_64",
                    "--platform",
                    "any",
                    "-d",
                    work,
                    "-q",
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            if not name.endswith(PURE):
                raise
        if not found.is_file():
            if not name.endswith(PURE):
                raise WheelhouseRefused(f"the index did not give {name}")
            found = _rebuild(name, Path(work))
        if _sha256(found) != hexdigest:
            raise WheelhouseRefused(f"{name}: the index's file is not the pinned one")
        shutil.copyfile(found, Path(into) / name)


#: The wheels `_rebuild` may build: pure Python, the same bytes on any host.
PURE = "-py3-none-any.whl"


def _rebuild(name, work):
    """`name` built from its source distribution on the index, by exact name
    and version: `pip wheel --no-deps` in pip's build isolation with
    SOURCE_DATE_EPOCH=0, which makes the archive reproducible (Graphite
    Test, 2026-10-23: torch_harmonics 0.7.4 rebuilt byte-identical to its
    pin, twice). The caller keeps it only when its sha256 is the pin."""
    sources, built = work / "sdist", work / "built"
    sources.mkdir()
    built.mkdir()
    environment = {**os.environ, "SOURCE_DATE_EPOCH": "0"}
    environment.pop("PIP_NO_BUILD_ISOLATION", None)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                requirement(name),
                "--no-deps",
                "--no-binary=:all:",
                "-d",
                str(sources),
                "-q",
            ],
            check=True,
        )
        archives = sorted(sources.iterdir())
        if len(archives) != 1:
            raise WheelhouseRefused(
                f"{name}: the index has no wheel and no single source distribution"
            )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                str(archives[0]),
                "-w",
                str(built),
                "-q",
            ],
            check=True,
            env=environment,
        )
    except subprocess.CalledProcessError:
        raise WheelhouseRefused(
            f"{name}: the index has no wheel, and its source could not be built"
        ) from None
    found = built / name
    if not found.is_file():
        raise WheelhouseRefused(f"{name}: its source did not build that wheel")
    return found


def _record(directory, wanted):
    return {
        "schema": SCHEMA,
        "wheels": {
            name: {
                "bytes": (Path(directory) / name).stat().st_size,
                "sha256": wanted[name],
            }
            for name in sorted(wanted)
        },
    }


def build(directory=DEFAULT_DIRECTORY, *, sources=(), checkout=REPOSITORY):
    """Build (or check an already built) wheelhouse in `directory`; returns its
    record. Offline when every wheel is in a `sources` directory."""
    wanted = pinned_wheels(checkout)
    directory = Path(directory)
    if directory.exists() or directory.is_symlink():
        return _check_existing(directory, wanted, sources)
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    try:
        for name, hexdigest in sorted(wanted.items()):
            _add(directory, name, hexdigest, sources)
        record = _record(directory, wanted)
        (directory / RECORD).write_text(
            json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.chmod(directory / RECORD, 0o600)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)  # never leave a part-built one
        raise
    return record


def _add(directory, name, hexdigest, sources):
    """One pinned wheel into `directory`: from a `sources` directory holding
    it with the pinned sha256, else fetched by exact name and version; kept
    only with the pinned sha256, owner-only."""
    local = next(
        (
            root / name
            for root in map(Path, sources)
            if (root / name).is_file() and _sha256(root / name) == hexdigest
        ),
        None,
    )
    if local is not None:
        shutil.copyfile(local, directory / name)
    else:
        _fetch(name, hexdigest, directory)
    if _sha256(directory / name) != hexdigest:
        (directory / name).unlink()
        raise WheelhouseRefused(f"{name}: written file differs from its pin")
    os.chmod(directory / name, 0o600)


def _recorded(directory):
    """The wheel names an earlier build of this directory recorded."""
    try:
        record = json.loads((directory / RECORD).read_text(encoding="utf-8"))
        return set(record["wheels"]) if record.get("schema") == SCHEMA else set()
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def _check_existing(directory, wanted, sources=()):
    """A directory that is exactly this wheelhouse is accepted as is. One
    built here before for an earlier catalog is brought up to its pins (M1
    E2E R10-1: new entries pinned wheels an existing wheelhouse lacked, and
    the catalog install stopped): each missing pinned wheel is added as a
    new build adds it, and a wheel the earlier build recorded that nothing
    pins any more is removed. Anything else - a file it never recorded, a
    wheel that differs from its pin - is refused, never overwritten."""
    if directory.is_symlink() or not directory.is_dir():
        raise WheelhouseRefused(f"{directory} exists and is not a directory")
    if (directory.stat().st_mode & 0o777) != 0o700:
        raise WheelhouseRefused(f"{directory} is not owner-only (0700)")
    expected = set(wanted) | {RECORD}
    present = {path.name for path in directory.iterdir()}
    stale = (present - expected) & _recorded(directory)
    if present - expected - stale or RECORD not in present:
        raise WheelhouseRefused(
            f"{directory} exists with different contents; remove it to rebuild"
        )
    for name in sorted(present & set(wanted)):
        path = directory / name
        if path.is_symlink() or _sha256(path) != wanted[name]:
            raise WheelhouseRefused(f"{directory}/{name} differs from its pin")
    missing = sorted(set(wanted) - present)
    if not missing and not stale:
        return _record(directory, wanted)
    for name in missing:
        _add(directory, name, wanted[name], sources)
    for name in sorted(stale):
        (directory / name).unlink()
    record = _record(directory, wanted)
    (directory / RECORD).write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(directory / RECORD, 0o600)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--from", dest="sources", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        record = build(args.directory, sources=args.sources)
    except (WheelhouseRefused, subprocess.CalledProcessError) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(json.dumps({"directory": str(args.directory), **record}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
