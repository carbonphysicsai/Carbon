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
has only as source is rebuilt from its pinned source distribution with
pinned build requirements (`SOURCE_PINS`). Either is a network step on the
host, by its owner or the background catalog install it started; never an MCP
tool. A file whose sha256 differs from the catalog's pin is never kept: the
build fails.

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
    binary of is rebuilt from its pinned source distribution (`_rebuild`,
    `SOURCE_PINS`) and kept only on the same terms (M1 E2E R10-1:
    torch_harmonics 0.7.4 is published as an sdist only)."""
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
#: Pinned wheels the index publishes only as source, and how each is rebuilt:
#: its source distribution's file name and sha256 (checked before anything
#: of it runs), and every build requirement by exact version and sha256,
#: installed with `pip --require-hashes` into a fresh build environment
#: (Validator, R10-1 receipt). torch_harmonics 0.7.4 rebuilt with exactly
#: these is byte-identical to its catalog pin (sha256 326941e1...ab72; its
#: WHEEL names setuptools 84.2.1); the hashes are PyPI's published ones.
SOURCE_PINS = {
    "torch_harmonics-0.7.4-py3-none-any.whl": {
        "sdist": "torch_harmonics-0.7.4.tar.gz",
        "sdist_sha256": (
            "fa7b7a86ded81600e32b55bd0c3c040a5dfef96849305670b7bb24fb96dda2c7"
        ),
        "build": (
            (
                "setuptools",
                "84.2.1",
                "ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2",
            ),
            (
                "setuptools-scm",
                "10.3.4",
                "82f34c3e3084fc2b57d397200637cc13f2338004052d2fee47baa5f0e902464e",
            ),
            (
                "vcs-versioning",
                "2.6.0",
                "f8bebd1302ebc12e67ceb30fc7dd698ec969414b6fa43b30c3f14ac9b1e72c41",
            ),
            (
                "packaging",
                "26.3",
                "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c",
            ),
        ),
    }
}
#: Where a pinned source distribution is found: the index's JSON API, read
#: directly, so nothing of the package runs to fetch it (`pip download`
#: prepares an sdist's metadata by running its build backend).
INDEX_JSON = "https://pypi.org/pypi/{project}/{version}/json"


def _canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _download_sdist(name, filename):
    """The bytes of `filename`, the source distribution the index lists for
    the project and version `name` names; nothing of it is run."""
    import urllib.request

    project, version = requirement(name).split("==")
    with urllib.request.urlopen(
        INDEX_JSON.format(project=project, version=version), timeout=120
    ) as response:
        listing = json.load(response)
    url = next(
        (f["url"] for f in listing.get("urls", []) if f.get("filename") == filename),
        None,
    )
    if url is None or not url.startswith("https://"):
        raise WheelhouseRefused(f"{name}: the index lists no {filename}")
    with urllib.request.urlopen(url, timeout=600) as response:
        return response.read()


def _build_requirements(archive):
    """The build requirements an sdist declares (`[build-system] requires`),
    read from its pyproject.toml without running anything; setuptools'
    PEP 517 default when it declares none."""
    import tarfile
    import tomllib

    with tarfile.open(archive) as tar:
        roots = {member.split("/", 1)[0] for member in tar.getnames()}
        found = None
        if len(roots) == 1:
            try:
                found = tar.extractfile(roots.pop() + "/pyproject.toml")
            except KeyError:
                found = None
        if found is None:
            return ["setuptools>=40.8.0"]
        document = tomllib.loads(found.read().decode("utf-8"))
    return list((document.get("build-system") or {}).get("requires") or [])


def _rebuild(name, work):
    """`name` built from its pinned source distribution (`SOURCE_PINS`):
    the sdist is fetched and its sha256 checked before anything of it runs;
    every build requirement it declares must be pinned, and the pinned ones
    are installed with `pip --require-hashes` into a fresh environment; the
    wheel is built there with `pip wheel --no-deps --no-build-isolation` and
    SOURCE_DATE_EPOCH=0. The caller keeps it only when its sha256 is the
    pin. A wheel with no source pin is never built."""
    pin = SOURCE_PINS.get(name)
    if pin is None:
        raise WheelhouseRefused(
            f"{name}: the index has no wheel of it, and it has no pinned source"
        )
    archive = work / pin["sdist"]
    archive.write_bytes(_download_sdist(name, pin["sdist"]))
    if _sha256(archive) != pin["sdist_sha256"]:
        raise WheelhouseRefused(
            f"{name}: its source {pin['sdist']} differs from its pin"
        )
    pinned = {_canonical(project) for project, _, _ in pin["build"]}
    for declared in _build_requirements(archive):
        project = _canonical(re.split(r"[<>=!~;\[ ]", declared.strip(), maxsplit=1)[0])
        if project not in pinned:
            raise WheelhouseRefused(
                f"{name}: its build requirement {declared!r} is not pinned"
            )
    requirements = work / "build-requirements.txt"
    requirements.write_text(
        "".join(
            f"{project}=={version} --hash=sha256:{digest}\n"
            for project, version, digest in pin["build"]
        ),
        encoding="utf-8",
    )
    environment, built = work / "build-environment", work / "built"
    built.mkdir()
    python = environment / "bin" / "python"
    variables = {**os.environ, "SOURCE_DATE_EPOCH": "0"}
    try:
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "-q",
                "--require-hashes",
                "--no-deps",
                "--only-binary=:all:",
                "-r",
                str(requirements),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "wheel",
                "-q",
                "--no-deps",
                "--no-build-isolation",
                str(archive),
                "-w",
                str(built),
            ],
            check=True,
            env=variables,
        )
    except subprocess.CalledProcessError:
        raise WheelhouseRefused(
            f"{name}: the index has no wheel, and its pinned source could not be built"
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
