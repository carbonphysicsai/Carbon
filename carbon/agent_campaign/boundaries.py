"""Execution and information boundaries for external research-agent sessions.

Handoff §6: separate workspaces and credentials for the agent's legitimate
construction research, its adversarial research, its optimizer-development
work, and Carbon's independent evaluation. Research sessions receive published
challenge material and permitted development feedback; confirmation material
stays outside their repositories, tools, logs and memory.

Carbon's full repository holds development evidence an attacker could read, so
a research session never gets a clone of it. It gets an **allowlisted
checkout**: a manifest of exact files and digests, materialized into an empty
directory. A branch or folder name hides nothing; the manifest is the boundary.
The denylist wins over the allowlist, symlinks are refused, and every copied
file is re-verified against its manifest digest.

The allowlists below are working engineering decision MIRA-D3 (published
material only); a lead may narrow or widen them by editing this module, which
changes the manifest digest a campaign binds.

Canaries are synthetic secrets: random tokens planted in places the agent must
not read. Any exported artifact or event that contains one is evidence of
exposure. Canaries are never real credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
from enum import Enum
from pathlib import Path, PurePosixPath

MANIFEST_SCHEMA = "carbon.agent-campaign.research-checkout.v1"
CANARY_PREFIX = "CARBON-CANARY-"


class Role(str, Enum):
    CONSTRUCTION = "construction_research"
    ADVERSARIAL = "adversarial_research"
    OPTIMIZER = "optimizer_development"
    #: Carbon's own evaluation and evidence collection. Never dispatched to an
    #: external provider, never shares a workspace or credential with a session.
    EVALUATION = "carbon_evaluation"


AGENT_ROLES = frozenset({Role.CONSTRUCTION, Role.ADVERSARIAL, Role.OPTIMIZER})

#: Published battery challenge material a construction or adversarial session
#: may read (Level 0): the interface, the recipes and their training code, the
#: public reference solver (invariant 33), the construction contract and the
#: strategy schema.
_PUBLISHED_CHALLENGE = (
    "carbon/battery/domain.py",
    "carbon/battery/challenge.py",
    "carbon/battery/recipes.py",
    "carbon/battery/training.py",
    "carbon/battery/reference.py",
    "carbon/reconstruction/capability_registry.py",
    "carbon/schema/strategy.py",
)
ALLOWLIST = {
    Role.CONSTRUCTION: _PUBLISHED_CHALLENGE,
    Role.ADVERSARIAL: _PUBLISHED_CHALLENGE,
    Role.OPTIMIZER: (
        "carbon/battery/value/contract.py",
        "carbon/battery/value/decision.py",
        "carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json",
        "carbon/battery/value/search_commitment.py",
        "docs/development/DESIGN_OPTIMIZER_SCOPE.md",
    ),
    Role.EVALUATION: (),
}
#: Never copied, whatever an allowlist says. Matched on path components and
#: lower-cased names.
DENY_PREFIXES = (
    ".agent/",
    "docs/development/evidence/",
    "carbon/agent_campaign/",
    "tests/",
)
DENY_FRAGMENTS = (
    "ev4",
    "ev5",
    "confirmation",
    "secret",
    "credential",
    ".env",
    "canary",
)


class BoundaryError(ValueError):
    """A boundary refused an operation."""


def _denied(relative: str) -> bool:
    lowered = relative.lower()
    return lowered.startswith(DENY_PREFIXES) or any(
        fragment in lowered for fragment in DENY_FRAGMENTS
    )


def _safe_relative(relative: str) -> str:
    path = PurePosixPath(relative)
    if (
        type(relative) is not str
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != relative
    ):
        raise BoundaryError("checkout_path_not_relative")
    return relative


def _no_symlink(repository: Path, relative: str) -> Path:
    current = repository
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise BoundaryError("checkout_symlink_refused")
    return current


def checkout_manifest(repository, role, paths=None):
    """The exact files a session of `role` receives, with their digests."""
    if type(role) is not Role:
        raise TypeError("exact Role required")
    if role not in AGENT_ROLES:
        raise BoundaryError("evaluation_material_never_checked_out")
    repository = Path(repository).resolve()
    entries = []
    for relative in sorted(ALLOWLIST[role] if paths is None else paths):
        _safe_relative(relative)
        if _denied(relative):
            raise BoundaryError("checkout_path_denied: " + relative)
        path = _no_symlink(repository, relative)
        if not path.is_file():
            raise BoundaryError("checkout_path_missing: " + relative)
        body = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
            }
        )
    return {"schema": MANIFEST_SCHEMA, "role": role.value, "files": entries}


def manifest_digest(manifest) -> str:
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def materialize(repository, manifest, target):
    """Copy exactly the manifest's files into an empty `target`; re-verify
    each digest after the copy. Returns the manifest digest."""
    repository = Path(repository).resolve()
    target = Path(target)
    if target.exists() and (target.is_symlink() or any(target.iterdir())):
        raise BoundaryError("checkout_target_not_empty")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    for entry in manifest["files"]:
        relative = _safe_relative(entry["path"])
        if _denied(relative):
            raise BoundaryError("checkout_path_denied: " + relative)
        source = _no_symlink(repository, relative)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination, follow_symlinks=False)
        body = destination.read_bytes()
        if "sha256:" + hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise BoundaryError("checkout_digest_mismatch: " + relative)
    copied = sorted(
        str(PurePosixPath(p.relative_to(target)))
        for p in target.rglob("*")
        if p.is_file() or p.is_symlink()
    )
    if copied != sorted(e["path"] for e in manifest["files"]):
        raise BoundaryError("checkout_contains_unlisted_files")
    return manifest_digest(manifest)


def make_canaries(count=4):
    """Synthetic secrets to plant where a session must not read."""
    return tuple(CANARY_PREFIX + secrets.token_hex(16) for _ in range(count))


def plant(directory, canaries):
    """Write each canary into its own file under `directory` (a disposable,
    Carbon-held location). Returns the paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = []
    for index, token in enumerate(canaries):
        path = directory / f"canary-{index:02d}.txt"
        path.write_text(token + "\n")
        os.chmod(path, 0o600)
        paths.append(path)
    return paths


def exposed(body, canaries):
    """The canaries that appear in untrusted bytes or text."""
    if type(body) is str:
        body = body.encode("utf-8", "surrogatepass")
    return sorted(token for token in canaries if token.encode() in body)
