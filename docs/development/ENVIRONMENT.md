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
| Normal pre-PR command | `./scripts/dev/canonical.sh --full` |

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
7. Before a PR, return to a WSL host shell at the same checkout and run the
   canonical wrapper so it can create the read-only-source validation
   container:

   ```bash
   ./scripts/dev/canonical.sh --full
   ```

   A live read/write Dev Container remains suitable for interactive work, but
   noninteractive wrapper validation there fails closed unless it is already
   the wrapper-created isolated checkout.

Validation executes directly only in the exact image's wrapper-created,
isolated checkout, where Git metadata is read-only. On another host it uses
the pinned `linux/amd64` image. Interactive mode is the explicit exception
that uses a guarded read/write live checkout. If bootstrap, doctor, and
`ci.sh` pass there, the ordinary Carbon environment and engineering gates are
valid.

## Repository commands

| Command | Role |
|---|---|
| `./scripts/dev/bootstrap.sh` | Installs the exact repository Python through pinned uv and synchronizes the locked groups. |
| `./scripts/dev/doctor.sh` | Performs non-authority-mutating checks of the host, interpreter, lock, environment, repository, tools, and installed package. |
| `./scripts/dev/test.sh` | Runs the supported default CPU suite; extra pytest arguments are forwarded. |
| `./scripts/dev/ci.sh` | Runs delivery scope and repository hygiene, doctor, the quality and diff-hygiene preflight, invariants, CPU tests, package/wheel/outside-tree import checks, the code-authority boundary, and terminal diff hygiene. |
| `./scripts/dev/canonical.sh --focused <target>` | Runs focused pytest targets in the exact canonical environment. |
| `./scripts/dev/canonical.sh --full` | Runs the complete canonical `ci.sh` acceptance. |
| `./scripts/dev/canonical.sh --interactive` | Opens a profile-free interactive shell in the exact canonical environment, preserving the locked project/tool path. |
| `./scripts/dev/canonical.sh --dry-run ...` | Prints the direct or Docker command without executing it. |
| `./scripts/dev/shell.sh` | Opens Bash with Carbon's project environment selected. |

Do not replace these commands with ticket-specific remembered sequences.
Ticket-owned checks may be added after `ci.sh`; they do not replace it.

## Canonical wrapper behavior

`canonical.sh` is the single supported bridge from macOS, Windows/WSL2, or a
noncanonical Linux host. Direct execution requires container provenance
(`/.dockerenv`), the root-owned image marker, trusted absolute system/tool
executables, the complete pinned Ubuntu and architecture identity, and the
non-root `ubuntu` user. Validation also requires the wrapper-created isolation
marker and read-only Git metadata.
Otherwise the wrapper unconditionally performs a cache-enabled build of the
digest-pinned Carbon image for `linux/amd64`, verifies the built image
contract, and runs the resulting immutable image ID as `ubuntu` (`1000:1000`).

Focused, full, and arbitrary noninteractive commands bind the host worktree
read-only at `/carbon-source`, copy its tracked and untracked content except
`.git` and `.venv` into the image-owned writable checkout, and mount the host
checkout's `.git` plus any linked-worktree common Git directory read-only.
Uncommitted files remain visible to validation without container writes
changing host files or shared refs. The wrapper runs `bootstrap.sh` and
`doctor.sh` before every requested command. `--interactive` is deliberately
different: it mounts the live checkout and shared Git metadata read/write, and
fails before startup unless UID/GID 1000 can write both. Bootstrap and doctor
run with the exact trusted system path; requested commands receive exactly the
fresh project `.venv/bin` followed by that path.

For linked Git worktrees, the common Git metadata remains available at its
exact location. Noninteractive validation never reuses executable virtual-
environment state: each ephemeral writable checkout creates a fresh `.venv`.
Interactive mode alone uses a named `.venv` volume isolated by worktree
identity. The uv download cache is safely reused in every mode; neither cache
nor virtual environment creates files in the host checkout.

Docker execution fails closed when the client or daemon is unavailable. A
`--dry-run` is intentionally available without Docker so command construction
can be reviewed and tested; dry-run output is not canonical validation
evidence.

## Delivery and Git identity hygiene

Delivery preflight runs `scripts/dev/check_delivery_hygiene.py` before costly
acceptance jobs. It scans changed tracked text, introduced author/committer
identities, and introduced commit intent. `--all-tree` adds a complete tracked
text scan. Actual workstation paths, standalone `.local` identities/hostnames,
empty or evidence-only commits, and completion/retrigger-only commit messages
fail.
Placeholders such as `/home/<user>/...`, `/Users/<username>/...`, and
`C:\Users\<username>\...` remain valid.

Intentional fixtures require an exact, reason-bearing entry in
`scripts/dev/delivery_hygiene_allowlist.txt`. Entries cannot use globs or
regular expressions; text exceptions bind one path and exact matched value,
and commit exceptions bind one full SHA and one rule.

Configure a durable public Git identity before committing. GitHub's private
noreply address is recommended:

```bash
git config user.name "<github-username>"
git config user.email "<github-id>+<github-username>@users.noreply.github.com"
```

Do not rewrite historical commits merely to repair old workstation identity.

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

The GitHub workflow is path aware and keeps acceptance semantics in repository
scripts. Delivery preflight classifies the exact current PR head (or exact
current `main` push) before any expensive lane:

```text
RUNTIME_FULL
    -> canonical job on an ubuntu-24.04 runner
    -> pinned uv 0.12.7
    -> ./scripts/dev/bootstrap.sh
    -> ./scripts/dev/ci.sh
    -> require Docker-backed normal-checkout and linked-worktree wrapper tests
    -> clean-image job on a fresh ubuntu-24.04 runner
    -> build and load .devcontainer/Dockerfile for linux/amd64 without cache
    -> start the exact image as ubuntu (UID/GID 1000)
    -> copy a clean exact-head checkout and assign it to ubuntu
    -> prove the image marker, Ubuntu/glibc, uv, and CPython identities
    -> ./scripts/dev/bootstrap.sh
    -> ./scripts/dev/doctor.sh
    -> ./scripts/dev/ci.sh

CONTRACT_AUTHORITY
    -> invariants plus code/repository authority acceptance
    -> Development Hub authority, link, route, and browser validation

DERIVED_DOCUMENTATION (explicit allow-list only)
    -> deterministic Hub generation/drift, links, routes, and browser checks

unknown path
    -> fail closed to RUNTIME_FULL

every scope
    -> PR opened/synchronize/reopened/edited/ready-for-review events use the
       current live head, base, and PR body (never only the historical event)
    -> always-present final job named "Merge gate"
```

The Merge gate checks out the exact candidate with full history, reclassifies
it with the exact protected base's classifier, requires equality with the
preflight scope, and executes the protected base's gate. The exact pre-B-01F
base has a one-SHA candidate-classifier/gate bootstrap fallback because those
files do not yet exist there. This is repository-local hardening, not a claim
that candidate workflow tampering is eliminated: the workflow YAML and job
results remain candidate-controlled until an external or default-branch
required-workflow mechanism owns them.

The noncanonical local path ends in the same repository command:

```text
./scripts/dev/canonical.sh --full
    -> cached pinned-image build -> verify immutable image ID
    -> read-only source + writable validation copy + read-only Git metadata
    -> bootstrap -> doctor -> ./scripts/dev/ci.sh
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
