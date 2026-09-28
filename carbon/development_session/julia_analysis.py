"""Authored Julia analysis image and existing-carrier admission.

A campaign admits this language when its frozen runtime declares the exact
scope - a product campaign admitted by registration (C-MLP-02-D11) or a
development grant campaign alike. No grant is required.
This image has no evaluator modules; arbitrary source remains hostile and all
outputs remain miner self-report. No installation runs in the request path.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from carbon.reconstruction.worker.docker_runtime import DockerCLI

from .data import write_once
from .julia_depot import (
    ANALYSIS_ROOT,
    ARCHIVE,
    CPU_TARGET,
    DEFAULT_ENVIRONMENT,
    DEPOT_LABEL,
    ENVIRONMENT_ROOT,
    ENVIRONMENTS,
    JULIA_ROOT,
    TREE_LABEL,
    VERSION,
    bootstrap_for,
    environment_files,
)
from .julia_depot_build import (
    JuliaDepotIdentity,
    build_depot,
    tree_digest,
    verify_depot,
)
from .profile import canonical, digest
from .research_image import ResearchImageIdentity, build_analysis_image, verify_image

__all__ = [
    "ANALYSIS_ROOT",
    "ARCHIVE",
    "BOOTSTRAP",
    "CPU_TARGET",
    "DEFAULT_ENVIRONMENT",
    "ENVIRONMENTS",
    "ENVIRONMENT_ROOT",
    "SCHEMA",
    "SCHEMA_V2",
    "VERSION",
    "JuliaDepotIdentity",
    "JuliaResearchImageIdentity",
    "authored_julia_scope",
    "authorize_julia",
    "bootstrap_for",
    "build_julia_analysis_image",
    "environment_files",
    "image_record",
    "load_julia_analysis_image",
    "run_julia",
    "runtime_document",
    "runtime_document_v2",
    "validate_julia_output",
    "verify_julia_image",
]

#: Images built before the depot split. Their runtime digest hashes the Carbon
#: parent together with the Julia inputs, and every record written under this
#: schema keeps that meaning: it is read, verified and scoped exactly as it was.
SCHEMA = "carbon.authored-julia.analysis-image.v1"
#: Images composed from a separately built depot (`julia_depot`). The runtime
#: digest names both the Carbon parent and the depot; only the depot, whose
#: identity is Julia inputs alone, is reused across commits.
SCHEMA_V2 = "carbon.authored-julia.analysis-image.v2"
RUNTIME_LABEL = "org.opencontainers.image.carbon.authored-julia.runtime"


#: The default environment's bootstrap, for the registered routes that run
#: authored Julia without a miner choosing an environment.
BOOTSTRAP = bootstrap_for(DEFAULT_ENVIRONMENT)


@dataclass(frozen=True)
class JuliaResearchImageIdentity:
    image_id: str
    parent: ResearchImageIdentity
    runtime_digest: str
    #: None for a v1 image; the depot it was composed from for a v2 image.
    depot: JuliaDepotIdentity | None = None


def runtime_document(parent):
    """The v1 runtime document, unchanged: historical v1 digests mean this."""
    if type(parent) is not ResearchImageIdentity:
        raise ValueError("separate public analysis parent required")
    return {
        "schema": SCHEMA,
        "parent_image": parent.image_id,
        "parent_runtime": parent.runtime_digest,
        "julia_version": VERSION,
        "julia_archive": ARCHIVE,
        "environments": {
            name: {
                "project": digest(environment_files(name)[0]),
                "manifest": digest(environment_files(name)[1]),
                "bootstrap": digest(bootstrap_for(name).encode()),
            }
            for name in ENVIRONMENTS
        },
        "cpu_target": CPU_TARGET,
        "builder": digest(Path(__file__).read_bytes()),
        "package_artifacts": "PINNED_BY_MANIFEST_CONTENT_HASHES",
        "scope": "PUBLIC_MINER_AUTHORED_JULIA_NO_EVALUATOR",
        "qualification": False,
    }


def runtime_document_v2(parent, depot):
    """What ran: the exact Carbon parent and the exact depot composed onto it.

    The parent stays part of the composed runtime's identity - it is a true fact
    about what ran. It is not part of the depot's identity, which is the only
    thing reused across commits.
    """
    if type(parent) is not ResearchImageIdentity:
        raise ValueError("separate public analysis parent required")
    if type(depot) is not JuliaDepotIdentity:
        raise ValueError("separate authored Julia depot required")
    return {
        "schema": SCHEMA_V2,
        "parent_image": parent.image_id,
        "parent_runtime": parent.runtime_digest,
        "depot_image": depot.image_id,
        "depot_digest": depot.depot_digest,
        "depot_tree": depot.tree_digest,
        "julia_version": VERSION,
        "julia_archive": ARCHIVE,
        "composer": digest(Path(__file__).read_bytes()),
        "scope": "PUBLIC_MINER_AUTHORED_JULIA_NO_EVALUATOR",
        "qualification": False,
    }


def _expected_runtime(image):
    if image.depot is None:
        return digest(canonical(runtime_document(image.parent)))
    return digest(canonical(runtime_document_v2(image.parent, image.depot)))


def verify_julia_image(image, cli=None):
    """Check a v1 or v2 image against its own schema; never one against the
    other. A failure is final for this image: the builder rebuilds rather than
    relaxes."""
    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    cli = cli or DockerCLI()
    verify_image(image.parent, cli)
    if image.depot is not None:
        verify_depot(image.depot, cli)
    expected = _expected_runtime(image)
    if image.runtime_digest != expected:
        raise ValueError("authored Julia runtime source differs")
    metadata = cli.json(["image", "inspect", image.image_id, "--format", "{{json .}}"])
    parent = cli.json(
        ["image", "inspect", image.parent.image_id, "--format", "{{json .}}"]
    )
    config = metadata.get("Config", {})
    labels = config.get("Labels", {})
    layers = parent.get("RootFS", {}).get("Layers", [])
    if (
        metadata.get("Id") != image.image_id
        or metadata.get("Os") != "linux"
        or metadata.get("Architecture") != "amd64"
        or config.get("User") != "65532:65532"
        or config.get("Entrypoint") != parent.get("Config", {}).get("Entrypoint")
        or labels.get("org.opencontainers.image.carbon.julia.tarball") != ARCHIVE
        or labels.get("org.opencontainers.image.carbon.julia.version") != VERSION
        or labels.get(RUNTIME_LABEL) != expected
        or not layers
        or metadata.get("RootFS", {}).get("Layers", [])[: len(layers)] != layers
    ):
        raise ValueError("authored Julia image binding differs")
    if image.depot is not None and (
        labels.get(DEPOT_LABEL) != image.depot.depot_digest
        or labels.get(TREE_LABEL) != image.depot.tree_digest
        # The depot copy and the one-directory chmod that restores its root.
        or len(metadata.get("RootFS", {}).get("Layers", [])) != len(layers) + 2
    ):
        raise ValueError("authored Julia depot composition differs")
    return image


#: Run in the composed image under the parent's own Julia, with the depot
#: read-only: every package each environment names must load from the depot's
#: existing compiled cache. A package that would recompile at request time
#: means the composed environment is not the one that was built.
PRECOMPILED_CHECK = """using Pkg
deps = Pkg.project().dependencies
missing = String[]
for (name, uuid) in deps
    id = Base.PkgId(uuid, name)
    Base.in_sysimage(id) && continue
    Base.isprecompiled(id) || push!(missing, name)
end
isempty(missing) || (println(stderr, join(sort(missing), ",")); exit(3))
println(length(deps))
"""


def _precompiled_arguments(image, name, *, hide_compiled=False):
    """`docker run` arguments for PRECOMPILED_CHECK in one environment.

    `hide_compiled` mounts an empty directory over the depot's compiled caches:
    the specimen that shows the check fails when the caches are not there.
    """
    hidden = (
        [f"--mount=type=tmpfs,destination={ANALYSIS_ROOT}/depot/compiled"]
        if hide_compiled
        else []
    )
    return [
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--tmpfs=/tmp",
        "--user=65532:65532",
        *hidden,
        f"--entrypoint={JULIA_ROOT}/bin/julia",
        f"--env=JULIA_DEPOT_PATH=/tmp/julia-depot:{ANALYSIS_ROOT}/depot",
        f"--env=JULIA_PROJECT={ANALYSIS_ROOT}/{name}",
        f"--env=JULIA_LOAD_PATH={ANALYSIS_ROOT}/{name}:@stdlib",
        "--env=JULIA_PKG_OFFLINE=true",
        "--env=HOME=/tmp",
        # The image's own TMPDIR is the worker's scratch, absent here.
        "--env=TMPDIR=/tmp",
        image,
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=existing",
        "-e",
        PRECOMPILED_CHECK,
    ]


def _check_precompiled(cli, image):
    for name in ENVIRONMENTS:
        cli.run(_precompiled_arguments(image, name), timeout=1800)


def build_julia_analysis_image(parent_manifest, root):
    """Operator build only: compose the Julia-inputs-only depot onto the exact
    Carbon analysis parent.

    The depot under `root / "depot"` is reused whenever today's Julia inputs
    name one that verifies; otherwise it is built. Composition is one copy, and
    nothing is recorded until it is shown that the parent's Julia is the Julia
    the depot was compiled with, that the composed image carries exactly the
    depot's tree, and that every package loads precompiled.
    """
    parent = build_analysis_image(parent_manifest, root / "python-analysis-parent")
    cli = DockerCLI()
    parent_metadata = cli.json(
        ["image", "inspect", parent.image_id, "--format", "{{json .}}"]
    )
    labels = parent_metadata.get("Config", {}).get("Labels", {})
    if (
        labels.get("org.opencontainers.image.carbon.julia.tarball") != ARCHIVE
        or labels.get("org.opencontainers.image.carbon.julia.version") != VERSION
    ):
        raise ValueError("existing pinned Julia parent required; no runtime download")
    depot, _how = build_depot(root / "depot", cli)
    document = runtime_document_v2(parent, depot)
    fingerprint = digest(canonical(document))
    directory = root / fingerprint[7:]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = directory / "julia-analysis-image.json"
    if manifest.exists():
        try:
            return verify_julia_image(load_julia_analysis_image(manifest), cli)
        except Exception:  # noqa: BLE001 - any failed check means recompose
            manifest.unlink()
    # The depot was compiled by the Julia-only image's Julia; it is valid here
    # only if the parent's Julia is the same tree.
    if tree_digest(cli, parent.image_id, JULIA_ROOT) != tree_digest(
        cli, depot.image_id, JULIA_ROOT
    ):
        raise ValueError("parent Julia differs from the depot's Julia")
    tag = "carbon-authored-julia-parent:" + parent.image_id[7:]
    cli.run(["tag", parent.image_id, tag])
    depot_tag = "carbon-julia-depot:" + depot.image_id[7:]
    cli.run(["tag", depot.image_id, depot_tag])
    for name, expected in ((tag, parent.image_id), (depot_tag, depot.image_id)):
        if (
            cli.json(["image", "inspect", name, "--format", "{{json .}}"])["Id"]
            != expected
        ):
            raise ValueError("Julia analysis build tag changed")
    context = directory / "build-context"
    context.mkdir(mode=0o700, exist_ok=True)
    # COPY of a directory copies its contents but creates the destination
    # directory itself with default permissions, so the depot root arrives
    # writable by its owner where the depot has it read-only. The one-directory
    # chmod restores it; the tree check below requires the result to equal the
    # depot exactly, root included.
    recipe = f"""FROM {depot_tag} AS depot
FROM {tag}
COPY --from=depot {ANALYSIS_ROOT} {ANALYSIS_ROOT}
USER 0:0
RUN chmod a-w {ANALYSIS_ROOT}
LABEL {RUNTIME_LABEL}="{fingerprint}" \\
      {DEPOT_LABEL}="{depot.depot_digest}" \\
      {TREE_LABEL}="{depot.tree_digest}"
USER 65532:65532
"""
    write_once(context / "Dockerfile", recipe.encode())
    built = cli.run(
        [
            "build",
            "--network=none",
            "--pull=false",
            "--platform=linux/amd64",
            "-q",
            str(context),
        ],
        timeout=3600,
    )
    image = JuliaResearchImageIdentity(
        built.stdout.decode().strip(), parent, fingerprint, depot
    )
    verify_julia_image(image, cli)
    if tree_digest(cli, image.image_id, ANALYSIS_ROOT) != depot.tree_digest:
        raise ValueError("composed image does not carry the depot exactly")
    _check_precompiled(cli, image.image_id)
    write_once(directory / "runtime-material.json", canonical(document))
    write_once(manifest, canonical(image_record(image)))
    return image


def image_record(image):
    """The record a Julia image is written under, in its own schema: v1 with
    no depot field, v2 with it. Everything that records an image uses this,
    so a record can never pair one schema with the other's fields."""
    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    record = {
        "schema": SCHEMA if image.depot is None else SCHEMA_V2,
        "image_id": image.image_id,
        "parent": asdict(image.parent),
        "runtime_digest": image.runtime_digest,
    }
    if image.depot is not None:
        record["depot"] = asdict(image.depot)
    return record


def load_julia_analysis_image(path):
    """Read a v1 or v2 record, each under the schema it was written with."""
    if path.is_symlink() or path.stat().st_size > 8192:
        raise ValueError("bounded authored Julia manifest required")
    value = json.loads(path.read_bytes())
    schema = value.pop("schema", None)
    keys = {"image_id", "parent", "runtime_digest"}
    if schema == SCHEMA and set(value) == keys:
        value["parent"] = ResearchImageIdentity(**value["parent"])
        return JuliaResearchImageIdentity(**value)
    if schema == SCHEMA_V2 and set(value) == keys | {"depot"}:
        depot = value["depot"]
        if type(depot) is not dict or set(depot) != {
            "image_id",
            "depot_digest",
            "tree_digest",
        }:
            raise ValueError("closed authored Julia image manifest required")
        value["parent"] = ResearchImageIdentity(**value["parent"])
        value["depot"] = JuliaDepotIdentity(**depot)
        return JuliaResearchImageIdentity(**value)
    raise ValueError("closed authored Julia image manifest required")


def authored_julia_scope(image):
    """The scope a campaign freezes. A v1 image keeps its v2 scope byte for
    byte; a v2 image names its depot too, under scope v3."""
    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    scope = {
        "schema": "carbon.authored-julia.scope.v2",
        "language": "julia",
        "action": "run_julia",
        "image": image.image_id,
        "environment": image.runtime_digest,
        "package_environments": list(ENVIRONMENTS),
        "bootstrap": {
            name: digest(bootstrap_for(name).encode()) for name in ENVIRONMENTS
        },
        "provenance": "MINER_SELF_REPORTED",
        "official_eligible": False,
    }
    if image.depot is not None:
        scope["schema"] = "carbon.authored-julia.scope.v3"
        scope["depot"] = image.depot.depot_digest
    return scope


def authorize_julia(ledger, owner, image):
    """Admit authored Julia for this campaign's owner.

    A product campaign (C-MLP-02-D11) may use Julia at any time the host has a
    built image: nothing is declared at launch, because each run's execution
    contract records exactly which image, scope and environment ran. A
    development grant campaign keeps the frozen-scope rule it was built under.
    """
    from .research_ledger import PRODUCT

    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    manifest = json.loads(row[0]) if row else {}
    declared = manifest.get("runtime", {}).get("authored_research")
    if (
        not ledger.controlled(manifest)
        or manifest.get("owner") != owner
        or (
            declared != [authored_julia_scope(image)]
            and not (manifest.get("schema") == PRODUCT and declared is None)
        )
    ):
        raise ValueError("explicit prospective authored Julia scope required")
    ledger.authority(manifest)


def validate_julia_output(snapshot):
    """Validate declared portable data types without interpreting scientific truth."""

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate authored Julia output field")
            value[key] = item
        return value

    def finite(value, depth=0):
        if depth > 24:
            raise ValueError("authored Julia output nesting exceeded")
        if type(value) is float and not math.isfinite(value):
            raise ValueError("nonfinite authored Julia output")
        if type(value) is dict:
            for item in value.values():
                finite(item, depth + 1)
        elif type(value) is list:
            for item in value:
                finite(item, depth + 1)

    for path in snapshot.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size > 8 * 1024**2:
            raise ValueError("authored Julia output member too large")
        body = path.read_bytes()
        if path.suffix == ".json":
            finite(json.loads(body, object_pairs_hook=pairs))
        elif path.suffix == ".f64le":
            if len(body) % 8 or any(
                not math.isfinite(x[0]) for x in struct.iter_unpack("<d", body)
            ):
                raise ValueError("invalid finite little-endian float64 output")
        elif path.suffix == ".txt":
            body.decode("utf-8")
        else:
            raise ValueError("undeclared authored Julia output type")


def run_julia(
    ledger,
    *,
    owner,
    identity,
    source,
    files,
    image,
    seconds=600,
    environment=DEFAULT_ENVIRONMENT,
):
    from .research_carrier import PRECHARGED_TRIAL, _run

    authorize_julia(ledger, owner, image)
    if environment not in ENVIRONMENTS:
        raise ValueError("unknown authored Julia environment")
    if type(source) is not str or not source:
        raise ValueError("authored Julia source required")
    return _run(
        ledger,
        owner=owner,
        identity=identity,
        source=source,
        files=files,
        image=image,
        seconds=seconds,
        provenance="MINER_SELF_REPORTED",
        extra_resources=(
            {} if PRECHARGED_TRIAL.get() is not None else {"research_trials": 1}
        ),
        program_name="program.jl",
        bootstrap=bootstrap_for(environment),
        # The chosen environment is part of what ran, so it is part of the
        # operation's identity: a retry naming another environment conflicts.
        execution_contract={
            **authored_julia_scope(image),
            "selected_environment": environment,
        },
        output_validator=validate_julia_output,
        miner_authored=True,
    )
