"""Versioned battery recipe implementations (TORCH-GPU-01, the owner's option A).

The bytes of Carbon's battery implementation modules
(`contracts.IMPLEMENTATION_MODULES`) enter every battery recipe's plan digest,
and so every recipe digest. A change to those bytes is therefore a new
implementation version, never an edit of the old one (invariant 10): each
version keeps its own module bytes, and a record made under a version
recompiles and verifies under that version, from main, for as long as the
version is registered.

- `CURRENT` is the version new recipes compile under. Its bytes are the live
  modules in `carbon/battery/`.
- Every earlier version is a read-only snapshot under
  `implementation_snapshots/<version>/`: the module bytes as `<name>.snapshot`
  and a `MANIFEST.json` naming each module's sha256 and the version's
  implementation digest. A snapshot is refused unless its bytes are exactly the
  manifest's and its digest is the one pinned here (`PINNED`), so a snapshot
  cannot be edited, nor a version silently re-pinned.

Version 1.0 is the implementation main shipped up to TORCH-GPU-01 (CPU-only
PyTorch). Version 2.0 adds the PyTorch CUDA rebuild device; its CPU numerics
are version 1.0's.

Pure data and the standard library: importing this module initializes no
numerical runtime.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
SNAPSHOTS = HERE / "implementation_snapshots"
MANIFEST_SCHEMA = "carbon.battery-implementation-snapshot.v1"
#: Every module whose bytes determine what a battery recipe rebuilds.
MODULES = (
    "domain.py",
    "recipes.py",
    "training.py",
    "torch_training.py",
    "torch_families.py",
)
CURRENT = "2.0"
#: Each retained version's implementation digest. A retained version is never
#: re-pinned: a different digest is a new version.
PINNED = {
    "1.0": "sha256:e4c4f12958ba4cbbe5e088190eaeba19cc4a8e23378c8b119ca2bbaae96cc417",
}
VERSIONS = (*PINNED, CURRENT)


class ImplementationUnavailable(ValueError):
    """A version that is not registered, or a snapshot that is not its own."""


def _sha256(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def digest_of(modules: dict[str, bytes]) -> str:
    """The implementation digest of module bytes, as `contracts` defines it."""
    body = json.dumps(
        {name: _sha256(modules[name]) for name in MODULES},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(body)


def _snapshot(version: str, root: Path) -> dict[str, bytes]:
    folder = root / ("v" + version.split(".", 1)[0])
    try:
        manifest = json.loads((folder / "MANIFEST.json").read_bytes())
        modules = {
            name: (folder / (name + ".snapshot")).read_bytes() for name in MODULES
        }
    except (OSError, ValueError):
        raise ImplementationUnavailable(f"snapshot {version} unreadable") from None
    if (
        type(manifest) is not dict
        or manifest.get("schema") != MANIFEST_SCHEMA
        or manifest.get("version") != version
        or manifest.get("modules") != {name: _sha256(modules[name]) for name in MODULES}
        or manifest.get("implementation_digest") != PINNED[version]
        or digest_of(modules) != PINNED[version]
    ):
        raise ImplementationUnavailable(f"snapshot {version} is not its pinned bytes")
    return modules


def module_bytes(version: str = CURRENT, *, root: Path = SNAPSHOTS) -> dict[str, bytes]:
    """The exact module bytes of a registered implementation version."""
    if version == CURRENT:
        return {name: (HERE / name).read_bytes() for name in MODULES}
    if version not in PINNED:
        raise ImplementationUnavailable(f"implementation {version} is not registered")
    return _snapshot(version, root)


def implementation_digest(version: str = CURRENT) -> str:
    return digest_of(module_bytes(version))
