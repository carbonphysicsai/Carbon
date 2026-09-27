"""Build, verify, reuse and adopt the authored-Julia depot.

The operational half of `julia_depot`: nothing here decides what the depot
contains, so nothing here is part of its identity. A depot is named by
`julia_depot.depot_digest()` alone; this module builds that depot when it is
absent, reuses it only when it verifies, and never serves one that does not.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

from .julia_depot import (
    ANALYSIS_ROOT,
    ARCHIVE,
    ARCHIVE_LABEL,
    DEPOT_LABEL,
    DEPOT_SCHEMA,
    ENVIRONMENTS,
    LAZY_ARTIFACTS,
    VERSION,
    VERSION_LABEL,
    base_recipe,
    depot_digest,
    environment_files,
    fetch_recipe,
    precompile_recipe,
)
from .profile import canonical, digest


@dataclass(frozen=True)
class JuliaDepotIdentity:
    #: The Julia-only depot image, by local image id (its config digest).
    image_id: str
    #: `depot_digest()` when it was built: Julia inputs only; the cache key.
    depot_digest: str
    #: Content of `ANALYSIS_ROOT` in that image: paths, types, modes, link
    #: targets and file bytes. The composed image must carry exactly this.
    tree_digest: str


def tree_digest(cli, image, path):
    """Content digest of one directory tree inside a local image.

    Streams the tree out of a created (never started) container and hashes, per
    member in sorted order: relative path, type, permission bits, link target
    and file bytes. Owner and timestamps are left out; they carry no content.
    """
    container = cli.run(["create", image], timeout=120).stdout.decode().strip()
    try:
        process = subprocess.Popen(
            ["docker", "cp", f"{container}:{path}", "-"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
        entries = []
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                name = member.name.split("/", 1)[1] if "/" in member.name else ""
                content = ""
                if member.isfile():
                    hasher = hashlib.sha256()
                    stream = archive.extractfile(member)
                    while block := stream.read(1 << 20):
                        hasher.update(block)
                    content = hasher.hexdigest()
                entries.append(
                    [
                        name,
                        member.type.decode("latin-1"),
                        member.mode & 0o7777,
                        member.linkname,
                        content,
                    ]
                )
        if process.wait(timeout=600) != 0 or not entries:
            raise ValueError("Julia tree could not be read in full")
    finally:
        cli.run(["rm", "--force", container], timeout=120)
    entries.sort()
    return digest(json.dumps(entries, separators=(",", ":")).encode())


def _record(root, **event):
    """Append what happened to this depot root's event log: evidence of whether
    a run reused, adopted or built the depot, and how long that took."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    line = json.dumps({"at": round(time.time()), **event}, sort_keys=True)
    with (root / "events.jsonl").open("a", encoding="utf-8") as log:
        log.write(line + "\n")


def verify_depot(depot, cli):
    """The depot image is the one recorded, built from today's Julia inputs."""
    if type(depot) is not JuliaDepotIdentity:
        raise ValueError("separate authored Julia depot required")
    if depot.depot_digest != depot_digest():
        raise ValueError("authored Julia depot inputs differ")
    metadata = cli.json(["image", "inspect", depot.image_id, "--format", "{{json .}}"])
    labels = metadata.get("Config", {}).get("Labels", {}) or {}
    if (
        metadata.get("Id") != depot.image_id
        or metadata.get("Os") != "linux"
        or metadata.get("Architecture") != "amd64"
        or labels.get(DEPOT_LABEL) != depot.depot_digest
        or labels.get(VERSION_LABEL) != VERSION
        or labels.get(ARCHIVE_LABEL) != ARCHIVE
    ):
        raise ValueError("authored Julia depot image binding differs")
    return depot


def load_depot(path):
    if path.is_symlink() or path.stat().st_size > 4096:
        raise ValueError("bounded authored Julia depot manifest required")
    value = json.loads(path.read_bytes())
    if (
        set(value) != {"schema", "image_id", "depot_digest", "tree_digest"}
        or value.pop("schema") != DEPOT_SCHEMA
    ):
        raise ValueError("closed authored Julia depot manifest required")
    return JuliaDepotIdentity(**value)


def depot_manifest(root):
    """Where the depot for today's Julia inputs is recorded under `root`."""
    return root / depot_digest()[7:] / "julia-depot.json"


def _local_tag(cli, image, name):
    # BuildKit resolves a bare image id in FROM as a registry name and tries to
    # pull it, so a local image is addressed by a tag that embeds its id, and
    # the tag is checked.
    tag = f"{name}:{image.removeprefix('sha256:')}"
    cli.run(["tag", image, tag])
    if cli.json(["image", "inspect", tag, "--format", "{{json .}}"])["Id"] != image:
        raise ValueError("authored Julia build tag changed")
    return tag


def _build(cli, context, recipe, *, network, timeout):
    from .data import write_once

    write_once(context / "Dockerfile", recipe.encode())
    arguments = ["build", "--pull=false", "--platform=linux/amd64", "-q"]
    if not network:
        arguments.insert(1, "--network=none")
    built = cli.run([*arguments, str(context)], timeout=timeout)
    return built.stdout.decode().strip()


def build_depot(root, cli):
    """Reuse the verified depot for today's Julia inputs, or build it.

    A recorded depot that fails verification - its image missing, relabelled or
    built from other inputs - is never used: its record is discarded and the
    depot is rebuilt from nothing.
    """
    from .data import write_once

    started = time.monotonic()
    fingerprint = depot_digest()
    manifest = depot_manifest(root)
    if manifest.exists():
        try:
            depot = verify_depot(load_depot(manifest), cli)
        except Exception as refused:  # noqa: BLE001 - any failed check: rebuild
            manifest.unlink()
            _record(
                root,
                depot_digest=fingerprint,
                how="discarded",
                reason=type(refused).__name__,
            )
        else:
            _record(root, depot_digest=fingerprint, how="reused", image=depot.image_id)
            return depot, "reused"
    directory = manifest.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    base_context = directory / "base-context"
    base_context.mkdir(mode=0o700, exist_ok=True)
    base = _local_tag(
        cli,
        _build(cli, base_context, base_recipe(), network=True, timeout=3600),
        "carbon-julia-depot-base",
    )
    fetch_context = directory / "fetch-context"
    fetch_context.mkdir(mode=0o700, exist_ok=True)
    for name in ENVIRONMENTS:
        project, pinned = environment_files(name)
        (fetch_context / name).mkdir(mode=0o700, exist_ok=True)
        write_once(fetch_context / name / "Project.toml", project)
        write_once(fetch_context / name / "Manifest.toml", pinned)
    write_once(fetch_context / "artifacts.jl", LAZY_ARTIFACTS.encode())
    packages = _local_tag(
        cli,
        _build(cli, fetch_context, fetch_recipe(base), network=True, timeout=2 * 3600),
        "carbon-julia-depot-packages",
    )
    compile_context = directory / "compile-context"
    compile_context.mkdir(mode=0o700, exist_ok=True)
    image = _build(
        cli,
        compile_context,
        precompile_recipe(base, packages, fingerprint),
        network=False,
        timeout=4 * 3600,
    )
    depot = JuliaDepotIdentity(
        image, fingerprint, tree_digest(cli, image, ANALYSIS_ROOT)
    )
    verify_depot(depot, cli)
    write_once(manifest, canonical({"schema": DEPOT_SCHEMA, **depot.__dict__}))
    _record(
        root,
        depot_digest=fingerprint,
        how="built",
        image=depot.image_id,
        seconds=round(time.monotonic() - started),
    )
    return depot, "built"


#: Where a published depot is pulled from: by immutable digest, never by tag,
#: with no credential. The lock names which depot it holds; it is a transport
#: pointer, not an input, and is never part of the depot's identity.
REGISTRY = "ghcr.io/carbonphysicsai/carbon-julia-depot"
LOCK = Path(__file__).resolve().parents[2] / "scripts/dev/julia_depot.lock.json"
LOCK_SCHEMA = "carbon.authored-julia.depot-lock.v1"


def read_lock(path=LOCK):
    """The published depot for today's Julia inputs, or None.

    None when there is no lock, or when it names a depot for other inputs -
    after a Manifest.toml change, until a depot for the new inputs is published.
    """
    if not path.exists():
        return None
    value = json.loads(path.read_bytes())
    if set(value) != {"schema", "depot_digest", "image"} or (
        value["schema"] != LOCK_SCHEMA
    ):
        raise ValueError("closed authored Julia depot lock required")
    if not value["image"].startswith(REGISTRY + "@sha256:"):
        raise ValueError("a published depot is pinned by digest")
    if value["depot_digest"] != depot_digest():
        return None
    return value


def adopt_depot(root, cli, reference):
    """Record a pulled depot image for reuse, after checking it from nothing.

    The image must carry today's depot digest; its tree digest is computed
    here from the pulled bytes, never taken from the publisher. Whatever is
    recorded is verified again, like a locally built depot, before every use.
    """
    from .data import write_once

    image = cli.json(["image", "inspect", reference, "--format", "{{json .}}"])["Id"]
    depot = JuliaDepotIdentity(
        image, depot_digest(), tree_digest(cli, image, ANALYSIS_ROOT)
    )
    verify_depot(depot, cli)
    manifest = depot_manifest(root)
    if manifest.exists():
        manifest.unlink()
    manifest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(manifest, canonical({"schema": DEPOT_SCHEMA, **depot.__dict__}))
    _record(
        root,
        depot_digest=depot.depot_digest,
        how="adopted",
        image=image,
        reference=reference,
    )
    return depot
