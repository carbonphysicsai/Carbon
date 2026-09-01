# Canonical Carbon Development Environment

## What is supported

Carbon has one ordinary development and evidence baseline:

| Property | Canonical value |
|---|---|
| Operating system | Ubuntu 24.04 LTS, GNU glibc |
| Architecture | `linux/amd64` |
| Shell | Bash |
| Python | CPython 3.11.16 |
| Dependency manager | uv 0.12.7, pinned by OCI digest/action commit |
| Dependency state | committed `uv.lock` |
| Default dependency group | `dev` only |
| Normal pre-PR command | `./scripts/dev/ci.sh` |

Windows and macOS may host the editor and Docker. Native Windows Python and
native macOS Python are not canonical Carbon evidence platforms. The first
bounded environment qualifies only `linux/amd64`; an ARM64 or multi-Python
claim requires a later explicit compatibility ticket and full acceptance
evidence.

This environment establishes engineering reproducibility only. It creates no
scientific, security, network, economic, `LIVE`, launch, or production
qualification.

## Shortest supported Windows workflow

1. Install WSL2 with Ubuntu, Docker Desktop, and an editor with WSL/Dev
   Containers support.
2. Clone Carbon inside the WSL/Linux filesystem, for example:

   ```bash
   mkdir -p ~/src
   cd ~/src
   git clone https://github.com/carbonphysicsai/Carbon.git
   cd Carbon
   ```

   A suitable Windows Explorer/editor path looks like
   `\\wsl$\Ubuntu\home\<user>\src\Carbon`.

   Do not use a clone under `C:\...` or `/mnt/c/...` for canonical
   evidence. Windows-mounted paths can change permissions, symlinks, line
   endings, path behavior, and I/O performance.
3. Open that repository in the Carbon Dev Container. The container definition
   is committed under `.devcontainer/`.
4. Synchronize the exact lock and interpreter:

   ```bash
   ./scripts/dev/bootstrap.sh
   ```

5. Verify the environment:

   ```bash
   ./scripts/dev/doctor.sh
   ```

6. Work normally. The project interpreter is `.venv/bin/python`.
7. Before a PR, run:

   ```bash
   ./scripts/dev/ci.sh
   ```

If `doctor.sh` and `ci.sh` pass, the ordinary Carbon environment and
engineering gates are valid.

## Repository commands

| Command | Role |
|---|---|
| `./scripts/dev/bootstrap.sh` | Installs the exact repository Python through pinned uv and synchronizes the locked groups. |
| `./scripts/dev/doctor.sh` | Performs non-authority-mutating checks of the host, interpreter, lock, environment, repository, tools, and installed package. |
| `./scripts/dev/test.sh` | Runs the supported default CPU suite; extra pytest arguments are forwarded. |
| `./scripts/dev/ci.sh` | Runs doctor, the quality and diff-hygiene preflight, invariants, CPU tests, package/wheel/outside-tree import checks, the code-authority boundary, and terminal diff hygiene. |
| `./scripts/dev/shell.sh` | Opens Bash with Carbon's project environment selected. |

Do not replace these commands with ticket-specific remembered sequences.
Ticket-owned checks may be added after `ci.sh`; they do not replace it.

## Pinned identities

The container uses immutable image references:

```text
ubuntu:24.04
OCI index sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ghcr.io/astral-sh/uv:0.12.7
OCI index sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945
```

The repository pins CPython `3.11.16` in `.python-version`, constrains the
package to `>=3.11,<3.12`, and requires uv `0.12.7`. The image marker is:

```text
ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64
```

The committed lock was resolved for CPython 3.11 on Linux x86-64. A lock
update is a reviewed repository change, not a bootstrap side effect.

## Dependency groups

Ordinary engineering and CI install only `dev`. It contains the pinned test,
quality, build, wheel, and package-install tooling.

Heavy or domain-specific environments are explicit:

| Group | Intended owner | Not implied by installation |
|---|---|---|
| `science-jax` | A ticket explicitly owning JAX work | Scientific correctness or qualification |
| `science-torch` | A ticket explicitly owning Torch/NeuralOperator/PhysicsNeMo work | GPU/CUDA support or scientific qualification |
| `chain` | A ticket explicitly owning Bittensor integration | Network, economic, or production authority |

Use the wrapper so interpreter and lock checks remain consistent:

```bash
CARBON_UV_GROUPS="science-jax" ./scripts/dev/bootstrap.sh
CARBON_UV_GROUPS="science-torch" ./scripts/dev/bootstrap.sh
CARBON_UV_GROUPS="chain" ./scripts/dev/bootstrap.sh
```

Multiple owned groups may be space-separated. The underlying deterministic
operations are equivalent to:

```bash
uv sync --locked --group dev
uv sync --locked --group dev --group science-jax
uv sync --locked --group dev --group science-torch
uv sync --locked --group dev --group chain
```

Julia, CUDA, and a GPU runtime are not installed by the default environment.
Julia/reference qualification remains owned by B-04/B-E2 or their authorized
successors.

The package extras `neuraloperator`, `physicsnemo`, and `chain` remain
narrow install interfaces for current lazy package seams. They are not part of
ordinary `dev` synchronization.

## What doctor verifies

`doctor.sh` fails closed unless it can establish:

- Linux and Ubuntu 24.04 userland;
- GNU glibc rather than musl;
- `linux/amd64`;
- exact repository root and Git availability;
- committed dev-container metadata and, inside Docker, the canonical image
  marker, non-root `ubuntu` user, UID/GID 1000, and `/home/ubuntu` home;
- a WSL clone is not under `/mnt/<drive>`;
- exact uv 0.12.7, delivered by the pinned image or setup action;
- exact CPython 3.11.16 in this repository's `.venv`;
- `uv.lock` agrees with `pyproject.toml`;
- selected locked groups are already installed and dependency-consistent;
- `carbon` and distribution metadata import cleanly outside the checkout.

Native Windows exits before misleading package or test diagnostics and says:

```text
Unsupported canonical environment:
Windows native Python is not a Carbon evidence platform.
Open the repository in the Carbon Dev Container / WSL2 environment.
```

## Local and GitHub parity

The GitHub workflow is intentionally orchestration-only:

```text
canonical job on an ubuntu-24.04 runner
    -> pinned uv 0.12.7
    -> ./scripts/dev/bootstrap.sh
    -> ./scripts/dev/ci.sh

clean-image job on a fresh ubuntu-24.04 runner
    -> build and load .devcontainer/Dockerfile for linux/amd64 without cache
    -> start the exact image as ubuntu (UID/GID 1000)
    -> copy a clean exact-head checkout and assign it to ubuntu
    -> prove the image marker, Ubuntu/glibc, uv, and CPython identities
    -> ./scripts/dev/bootstrap.sh
    -> ./scripts/dev/doctor.sh
    -> ./scripts/dev/ci.sh
```

The local path ends in the same repository command:

```text
Carbon Dev Container
    -> ./scripts/dev/bootstrap.sh
    -> ./scripts/dev/ci.sh
```

Test semantics live in `scripts/dev/ci.sh`, not duplicated workflow YAML.
The workflow fetches complete history so the quality comparison and immutable
archive-tag boundary can be verified at the exact candidate head. The separate
clean-image job proves the pinned dev-container definition is runnable as its
configured non-root user and can execute the same repository-controlled gates;
a successful Docker build alone is not runnable-container evidence.

## Supported troubleshooting

### Native Windows rejection

Open the WSL clone in the Carbon Dev Container. Do not try to make native
Windows output into canonical evidence.

### WSL path rejection

Move or reclone the repository under `/home/<user>/...`, then reopen it.
Do not use `/mnt/c` as the canonical repository location.

### Wrong uv or Python

Rebuild/reopen the committed Dev Container. Do not bypass the version check or
manually substitute a different Python patch.

### Missing or stale environment

Run:

```bash
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
```

If the lock and project metadata disagree, do not regenerate the lock merely
to make the check pass. The ticket changing dependencies owns the reviewed
lock update.

### Container build diagnosis

Infrastructure maintainers may reproduce the image directly:

```bash
docker build --no-cache --pull --platform linux/amd64 \
  --file .devcontainer/Dockerfile \
  --tag carbon-dev:b-01e .
QUALITY_BASE_SHA=origin/main \
  ./scripts/dev/verify_image.sh carbon-dev:b-01e
```

A failed image build, startup, identity check, or in-image gate is an
environment/infrastructure failure. It is not a scientific failure.
