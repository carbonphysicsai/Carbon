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
from dataclasses import dataclass
from pathlib import Path

from carbon.reconstruction.worker.docker_runtime import DockerCLI

from .data import write_once
from .profile import canonical, digest
from .research_image import ResearchImageIdentity, build_analysis_image, verify_image

SCHEMA = "carbon.authored-julia.analysis-image.v1"
VERSION = "1.13.0"
ARCHIVE = "sha256:8975da61c128a5e5ded3e719e868da8c8781deb7ad7913d37fb99be02a81904b"

#: Two pinned package environments, because the newest SciML core cannot yet
#: coexist with the packages that have not migrated to it (owner decision,
#: 23 September 2026). `current` carries the newest core - ModelingToolkit 11,
#: Symbolics 7, OrdinaryDiffEq 7, SciMLBase 3 - and everything compatible with
#: it; `pde` carries NeuralPDE, MethodOfLines and DataDrivenDiffEq on the prior
#: core. Each is a committed Project.toml and Manifest.toml: every package and
#: binary artifact pinned by content hash, installed and precompiled when the
#: image is built, never at request time.
ENVIRONMENTS = ("current", "pde")
DEFAULT_ENVIRONMENT = "current"
ENVIRONMENT_ROOT = Path(__file__).resolve().parent / "julia_environments"
ANALYSIS_ROOT = "/opt/carbon-julia-analysis"

#: Precompiled once for a portable set of x86-64 targets - Julia's own release
#: target - so one image serves every miner's host rather than the builder's.
CPU_TARGET = "generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)"


def environment_files(name):
    """The committed Project.toml and Manifest.toml bytes for one environment."""
    if name not in ENVIRONMENTS:
        raise ValueError("unknown authored Julia environment")
    directory = ENVIRONMENT_ROOT / name
    return (
        (directory / "Project.toml").read_bytes(),
        (directory / "Manifest.toml").read_bytes(),
    )


def bootstrap_for(name):
    """The fixed worker bootstrap for one environment. The miner chooses which
    environment, never a path, project, depot or flag."""
    if name not in ENVIRONMENTS:
        raise ValueError("unknown authored Julia environment")
    project = f"{ANALYSIS_ROOT}/{name}"
    return f"""import os,shutil
from pathlib import Path
work=Path('/scratch/workspace');work.mkdir()
Path('/scratch/output').mkdir()
for item in Path('/input').iterdir():
    if item.name!='program.jl':shutil.copyfile(item,work/item.name)
os.chdir(work)
env={{'PATH':'/opt/carbon-julia/bin:/usr/bin:/bin','HOME':'/scratch/home',
     'TMPDIR':'/scratch/tmp','LANG':'C.UTF-8','JULIA_DEPOT_PATH':'{ANALYSIS_ROOT}/depot',
     'JULIA_LOAD_PATH':'{project}:@stdlib',
     'JULIA_PROJECT':'{project}','JULIA_PKG_OFFLINE':'true',
     'JULIA_PKG_SERVER':'','JULIA_PKG_PRECOMPILE_AUTO':'0',
     'JULIA_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}}
os.execve('/opt/carbon-julia/bin/julia',['julia','--startup-file=no',
    '--history-file=no','--project={project}',
    '--compiled-modules=existing','--threads=1','--','/input/program.jl'],env)
"""


#: The default environment's bootstrap, for the registered routes that run
#: authored Julia without a miner choosing an environment.
BOOTSTRAP = bootstrap_for(DEFAULT_ENVIRONMENT)


@dataclass(frozen=True)
class JuliaResearchImageIdentity:
    image_id: str
    parent: ResearchImageIdentity
    runtime_digest: str


def runtime_document(parent):
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


def verify_julia_image(image, cli=None):
    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    cli = cli or DockerCLI()
    verify_image(image.parent, cli)
    expected = digest(canonical(runtime_document(image.parent)))
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
        or labels.get("org.opencontainers.image.carbon.authored-julia.runtime")
        != expected
        or not layers
        or metadata.get("RootFS", {}).get("Layers", [])[: len(layers)] != layers
    ):
        raise ValueError("authored Julia image binding differs")
    return image


def build_julia_analysis_image(parent_manifest, root):
    """Operator build only; parent already contains the checksum-pinned Julia."""
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
    document = runtime_document(parent)
    fingerprint = digest(canonical(document))
    directory = root / fingerprint[7:]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = directory / "julia-analysis-image.json"
    if manifest.exists():
        return verify_julia_image(load_julia_analysis_image(manifest), cli)
    tag = "carbon-authored-julia-parent:" + parent.image_id[7:]
    cli.run(["tag", parent.image_id, tag])
    if (
        cli.json(["image", "inspect", tag, "--format", "{{json .}}"])["Id"]
        != parent.image_id
    ):
        raise ValueError("Julia analysis parent tag changed")
    fetched = _fetch_environments(cli, directory, tag)
    context = directory / "build-context"
    context.mkdir(mode=0o700, exist_ok=True)
    precompile = " && ".join(
        f"JULIA_PROJECT={ANALYSIS_ROOT}/{name} /opt/carbon-julia/bin/julia "
        "--startup-file=no --history-file=no --threads=1 "
        "-e 'using Pkg; Pkg.precompile(; strict=true)'"
        for name in ENVIRONMENTS
    )
    # Network off for the image itself. The packages arrive from the fetch
    # image, where each was verified against its manifest's content hash; this
    # step only compiles them, for the portable CPU target, with the flags the
    # runtime uses, and then makes the whole environment read-only.
    recipe = f"""FROM {fetched} AS packages
FROM {tag}
USER 0:0
COPY --from=packages {ANALYSIS_ROOT} {ANALYSIS_ROOT}
RUN export JULIA_DEPOT_PATH={ANALYSIS_ROOT}/depot JULIA_PKG_OFFLINE=true \\
      JULIA_CPU_TARGET='{CPU_TARGET}' HOME=/tmp TMPDIR=/tmp \\
    && rm -rf {ANALYSIS_ROOT}/depot/compiled \\
    && {precompile} \\
    && rm -rf {ANALYSIS_ROOT}/depot/logs {ANALYSIS_ROOT}/depot/scratchspaces \\
    && chmod -R a+rX,a-w {ANALYSIS_ROOT}
LABEL org.opencontainers.image.carbon.authored-julia.runtime="{fingerprint}"
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
        timeout=4 * 3600,
    )
    image = JuliaResearchImageIdentity(
        built.stdout.decode().strip(), parent, fingerprint
    )
    verify_julia_image(image, cli)
    write_once(directory / "runtime-material.json", canonical(document))
    write_once(
        manifest,
        canonical(
            {
                "schema": SCHEMA,
                "image_id": image.image_id,
                "parent": {
                    "image_id": parent.image_id,
                    "parent_image": parent.parent_image,
                    "runtime_digest": parent.runtime_digest,
                },
                "runtime_digest": fingerprint,
            }
        ),
    )
    return image


def _fetch_environments(cli, directory, tag):
    """Install every pinned package and binary artifact; compile nothing.

    The one step with network. Pkg verifies each package's tree hash and each
    artifact's SHA-256 against the committed manifests, so what arrives is
    exactly what the manifests name. Returns the fetch image's id, which the
    network-off build copies from.
    """
    context = directory / "fetch-context"
    context.mkdir(mode=0o700, exist_ok=True)
    for name in ENVIRONMENTS:
        project, manifest = environment_files(name)
        (context / name).mkdir(mode=0o700, exist_ok=True)
        write_once(context / name / "Project.toml", project)
        write_once(context / name / "Manifest.toml", manifest)
    instantiate = " && ".join(
        f"JULIA_PROJECT={ANALYSIS_ROOT}/{name} /opt/carbon-julia/bin/julia "
        "--startup-file=no --history-file=no "
        "-e 'using Pkg; Pkg.instantiate(; allow_autoprecomp=false)'"
        for name in ENVIRONMENTS
    )
    copies = "\n".join(
        f"COPY {name}/Project.toml {name}/Manifest.toml {ANALYSIS_ROOT}/{name}/"
        for name in ENVIRONMENTS
    )
    recipe = f"""FROM {tag}
USER 0:0
{copies}
RUN export JULIA_DEPOT_PATH={ANALYSIS_ROOT}/depot JULIA_PKG_PRECOMPILE_AUTO=0 \\
      HOME=/tmp TMPDIR=/tmp \\
    && {instantiate}
"""
    write_once(context / "Dockerfile", recipe.encode())
    built = cli.run(
        ["build", "--pull=false", "--platform=linux/amd64", "-q", str(context)],
        timeout=2 * 3600,
    )
    image = built.stdout.decode().strip()
    # BuildKit resolves a bare image id in FROM as a registry name and tries to
    # pull it, so the local fetch image is addressed by a tag that embeds its
    # id - the same treatment the parent gets - and the tag is checked.
    tag = "carbon-authored-julia-packages:" + image.removeprefix("sha256:")
    cli.run(["tag", image, tag])
    if cli.json(["image", "inspect", tag, "--format", "{{json .}}"])["Id"] != image:
        raise ValueError("Julia package image tag changed")
    return tag


def load_julia_analysis_image(path):
    if path.is_symlink() or path.stat().st_size > 8192:
        raise ValueError("bounded authored Julia manifest required")
    value = json.loads(path.read_bytes())
    if (
        set(value) != {"schema", "image_id", "parent", "runtime_digest"}
        or value.pop("schema") != SCHEMA
    ):
        raise ValueError("closed authored Julia image manifest required")
    value["parent"] = ResearchImageIdentity(**value["parent"])
    return JuliaResearchImageIdentity(**value)


def authored_julia_scope(image):
    if type(image) is not JuliaResearchImageIdentity:
        raise ValueError("separate authored Julia image required")
    return {
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


def authorize_julia(ledger, owner, image):
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    manifest = json.loads(row[0]) if row else {}
    if (
        not ledger.controlled(manifest)
        or manifest.get("owner") != owner
        or manifest.get("runtime", {}).get("authored_research")
        != [authored_julia_scope(image)]
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
    if type(source) is not str or not 1 <= len(source.encode()) <= 65536:
        raise ValueError("bounded authored Julia source required")
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
    )
