"""Build the pinned wheelhouse for the backbone catalog's wheel-bearing entries
(owner-run, on each miner and receiver host; never from MCP).

Some catalog entries (deepxde.DeepONetCartesianProd and the THUML ones) declare
wheels in their bundle manifests. `python -m scripts.dev.catalog_install` reads
those wheels from a private operator cache, by default this directory:

    python -m scripts.dev.catalog_wheelhouse [DIR] [--from SOURCE_DIR ...]

DIR defaults to `~/.carbon/catalog-wheelhouse`, owner-only (mode 0700), one per
host. The wheel set is read from this checkout's catalog (the union over every
entry's bundle manifest; two entries that disagree on a hash are refused). Each
wheel is taken from a `--from` directory when one holds a file of that name with
the pinned sha256, and otherwise fetched by exact name and version with
`pip download --no-deps --only-binary=:all:` (a network step, which is why this
is an owner-run step on the host). A file whose sha256 differs from the catalog's
pin is never kept: the build fails.

`WHEELHOUSE.json` in the directory is the local build record (name, size and
sha256 per wheel); it is not a second pin. The pins are each bundle manifest's,
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
    sha256 is the pin."""
    with tempfile.TemporaryDirectory() as work:
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
        found = Path(work) / name
        if not found.is_file():
            raise WheelhouseRefused(f"the index did not give {name}")
        if _sha256(found) != hexdigest:
            raise WheelhouseRefused(f"{name}: the index's file is not the pinned one")
        shutil.copyfile(found, Path(into) / name)


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
        return _check_existing(directory, wanted)
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    try:
        for name, hexdigest in sorted(wanted.items()):
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
                raise WheelhouseRefused(f"{name}: written file differs from its pin")
            os.chmod(directory / name, 0o600)
        record = _record(directory, wanted)
        (directory / RECORD).write_text(
            json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.chmod(directory / RECORD, 0o600)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)  # never leave a part-built one
        raise
    return record


def _check_existing(directory, wanted):
    """A directory that is exactly this wheelhouse is accepted as is; anything
    else is refused, never overwritten."""
    if directory.is_symlink() or not directory.is_dir():
        raise WheelhouseRefused(f"{directory} exists and is not a directory")
    if (directory.stat().st_mode & 0o777) != 0o700:
        raise WheelhouseRefused(f"{directory} is not owner-only (0700)")
    expected = set(wanted) | {RECORD}
    present = {path.name for path in directory.iterdir()}
    if present != expected:
        raise WheelhouseRefused(
            f"{directory} exists with different contents; remove it to rebuild"
        )
    for name, hexdigest in wanted.items():
        path = directory / name
        if path.is_symlink() or _sha256(path) != hexdigest:
            raise WheelhouseRefused(f"{directory}/{name} differs from its pin")
    return _record(directory, wanted)


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
