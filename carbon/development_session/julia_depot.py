# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The precompiled authored-Julia package depot, built from Julia inputs only.

The depot is the expensive part of the authored Julia image: every pinned
package and binary artifact of both environments, compiled for the portable CPU
target. Its identity - `depot_digest` - hashes exactly the inputs that decide
its content, and nothing from the Carbon source tree:

- the Julia version and checksum-pinned archive, and the pinned base the
  Julia-only build image starts from;
- the portable CPU target;
- each environment's committed Project.toml and Manifest.toml;
- each environment's worker bootstrap;
- this module's own bytes, which are the depot's whole recipe.

So a commit that does not touch those inputs names the same depot, and a depot
built once can be reused across commits. The depot is built on a Julia-only
image made from the same checksum-pinned archive the Carbon parent installs;
`julia_analysis` composes it onto that parent with one copy and proves, before
recording anything, that the two Julia trees are the same and that every
package is precompiled under the parent's own Julia.

This module is the recipe and nothing else, because its bytes are one of the
inputs: building, verifying, hashing trees and adopting a published depot live
in `julia_depot_build`, so changing how a depot is checked or moved never
changes which depot is named. It must stay free of Carbon imports beyond the
digest helpers; `test_julia_depot_identity` fails if the depot's identity
starts to depend on anything outside the inputs above.
"""

from __future__ import annotations

from pathlib import Path

from .profile import canonical, digest

DEPOT_SCHEMA = "carbon.authored-julia.depot.v1"

VERSION = "1.13.0"
ARCHIVE = "sha256:8975da61c128a5e5ded3e719e868da8c8781deb7ad7913d37fb99be02a81904b"
ARCHIVE_URL = (
    "https://julialang-s3.julialang.org/bin/linux/x64/1.13/"
    "julia-1.13.0-linux-x86_64.tar.gz"
)
#: The same digest-pinned base every Carbon worker image starts from.
BASE_IMAGE = (
    "ubuntu:24.04@sha256:"
    "33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"
)
JULIA_ROOT = "/opt/carbon-julia"

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

DEPOT_LABEL = "org.opencontainers.image.carbon.authored-julia.depot"
TREE_LABEL = "org.opencontainers.image.carbon.authored-julia.depot-tree"
VERSION_LABEL = "org.opencontainers.image.carbon.julia.version"
ARCHIVE_LABEL = "org.opencontainers.image.carbon.julia.tarball"


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
# A writable per-run depot first: packages such as GPUCompiler (under Enzyme)
# create scratch space when they load. The image depot stays read-only and
# still supplies every pinned, precompiled package.
Path('/scratch/julia-depot').mkdir()
for item in Path('/input').iterdir():
    if item.name!='program.jl':shutil.copyfile(item,work/item.name)
os.chdir(work)
env={{'PATH':'/opt/carbon-julia/bin:/usr/bin:/bin','HOME':'/scratch/home',
     'TMPDIR':'/scratch/tmp','LANG':'C.UTF-8',
     'JULIA_DEPOT_PATH':'/scratch/julia-depot:{ANALYSIS_ROOT}/depot',
     'JULIA_LOAD_PATH':'{project}:@stdlib',
     'JULIA_PROJECT':'{project}','JULIA_PKG_OFFLINE':'true',
     'JULIA_PKG_SERVER':'','JULIA_PKG_PRECOMPILE_AUTO':'0',
     'JULIA_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}}
os.execve('/opt/carbon-julia/bin/julia',['julia','--startup-file=no',
    '--history-file=no','--project={project}',
    '--compiled-modules=existing','--threads=1','--','/input/program.jl'],env)
"""


def depot_document():
    """Everything the depot's content depends on, and nothing else.

    Takes no argument on purpose: nothing a caller holds - a parent image, a
    source tree, a wheel - can enter the depot's identity.
    """
    return {
        "schema": DEPOT_SCHEMA,
        "base_image": BASE_IMAGE,
        "julia_version": VERSION,
        "julia_archive": ARCHIVE,
        "cpu_target": CPU_TARGET,
        "environments": {
            name: {
                "project": digest(environment_files(name)[0]),
                "manifest": digest(environment_files(name)[1]),
                "bootstrap": digest(bootstrap_for(name).encode()),
            }
            for name in ENVIRONMENTS
        },
        "builder": digest(Path(__file__).read_bytes()),
        "package_artifacts": "PINNED_BY_MANIFEST_CONTENT_HASHES",
    }


def depot_digest():
    return digest(canonical(depot_document()))


def base_recipe():
    """The Julia-only image: the pinned base plus the checksum-pinned archive,
    unpacked where the Carbon parent unpacks it and made read-only the same
    way. Nothing from the Carbon source tree."""
    return f"""FROM {BASE_IMAGE}
ADD --checksum={ARCHIVE} {ARCHIVE_URL} /tmp/carbon-julia.tar.gz
RUN tar -xzf /tmp/carbon-julia.tar.gz -C /opt \\
    && mv /opt/julia-{VERSION} {JULIA_ROOT} \\
    && rm /tmp/carbon-julia.tar.gz \\
    && {JULIA_ROOT}/bin/julia --startup-file=no --history-file=no --version \\
    && chmod -R a-w {JULIA_ROOT}
"""


LAZY_ARTIFACTS = """using Pkg, Pkg.Artifacts
for (root, dirs, files) in walkdir(joinpath(first(DEPOT_PATH), "packages"))
    if "Artifacts.toml" in files
        Pkg.Artifacts.ensure_all_artifacts_installed(
            joinpath(root, "Artifacts.toml"); include_lazy=true, quiet_download=true)
    end
end
"""


def fetch_recipe(base):
    """Install every pinned package and binary artifact; compile nothing.

    The one step with network. Pkg verifies each package's tree hash and each
    artifact's SHA-256 against the committed manifests, so what arrives is
    exactly what the manifests name.
    """
    instantiate = " && ".join(
        f"JULIA_PROJECT={ANALYSIS_ROOT}/{name} {JULIA_ROOT}/bin/julia "
        "--startup-file=no --history-file=no "
        "-e 'using Pkg; Pkg.instantiate(; allow_autoprecomp=false)'"
        for name in ENVIRONMENTS
    )
    copies = "\n".join(
        f"COPY {name}/Project.toml {name}/Manifest.toml {ANALYSIS_ROOT}/{name}/"
        for name in ENVIRONMENTS
    )
    # Lazy artifacts (MKL's OpenMP runtime, among others) are fetched on first
    # use, which a network-off image can never do; install every one now.
    return f"""FROM {base}
USER 0:0
{copies}
COPY artifacts.jl /tmp/carbon-artifacts.jl
RUN export JULIA_DEPOT_PATH={ANALYSIS_ROOT}/depot JULIA_PKG_PRECOMPILE_AUTO=0 \\
      HOME=/tmp TMPDIR=/tmp \\
    && {instantiate} \\
    && {JULIA_ROOT}/bin/julia --startup-file=no --history-file=no \\
      /tmp/carbon-artifacts.jl \\
    && rm /tmp/carbon-artifacts.jl
"""


def precompile_recipe(base, packages, fingerprint):
    """Compile the fetched packages with network off, for the portable CPU
    target and the flags the runtime uses, then make the whole environment
    read-only."""
    precompile = " && ".join(
        f"JULIA_PROJECT={ANALYSIS_ROOT}/{name} {JULIA_ROOT}/bin/julia "
        "--startup-file=no --history-file=no --threads=1 "
        "-e 'using Pkg; Pkg.precompile(; strict=true)'"
        for name in ENVIRONMENTS
    )
    return f"""FROM {packages} AS packages
FROM {base}
USER 0:0
COPY --from=packages {ANALYSIS_ROOT} {ANALYSIS_ROOT}
RUN export JULIA_DEPOT_PATH={ANALYSIS_ROOT}/depot JULIA_PKG_OFFLINE=true \\
      JULIA_CPU_TARGET='{CPU_TARGET}' HOME=/tmp TMPDIR=/tmp \\
    && rm -rf {ANALYSIS_ROOT}/depot/compiled \\
    && {precompile} \\
    && rm -rf {ANALYSIS_ROOT}/depot/logs {ANALYSIS_ROOT}/depot/scratchspaces \\
    && chmod -R a+rX,a-w {ANALYSIS_ROOT}
LABEL {DEPOT_LABEL}="{fingerprint}" \\
      {VERSION_LABEL}="{VERSION}" \\
      {ARCHIVE_LABEL}="{ARCHIVE}"
"""
