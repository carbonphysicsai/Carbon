#!/usr/bin/env bash
# One command from a clean Linux machine to the Carbon Control Center (C-MLP-04),
# and the same command to update it (LP-PROD-E).
#
#   git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
#   ~/carbon/scripts/install_miner.sh            # add --gpu for GPU practice
#   ~/carbon/scripts/install_miner.sh --update   # later: the latest main
#   ~/carbon/scripts/install_miner.sh --release worker-images-vN
#                                                # Carbon's released images
#   CARBON_STATE_DIR=~/.carbon/s5-candidate ~/carbon/scripts/install_miner.sh \
#     --development-candidate "$(git -C ~/carbon rev-parse HEAD)" \
#     "$(git -C ~/carbon rev-parse 'HEAD^{tree}')" \
#     "sha256:$(git -C ~/carbon archive --format=tar HEAD | sha256sum | cut -d' ' -f1)" \
#     --no-start                                # local DEVELOPMENT only
#
# What it does, in order, and nothing else:
#   1. checks this machine: Linux x86-64, git, curl, a running Docker (for
#      the service, reachable from the systemd user manager that runs it too),
#      the free disk the environment and images need, and that no Control
#      Center is running from the state directory this install changes;
#   2. brings the checkout to the requested ref (the latest main by default).
#      The checkout must be clean, because an image's identity is the exact
#      source tree, and the ordinary ref must be in Carbon's main. An explicit
#      DEVELOPMENT candidate instead verifies exact local revision/tree/archive
#      identities in its own owner state directory. When the installer itself
#      changed at an ordinary ref, the new installer carries on from here;
#   3. installs the pinned uv if missing and syncs Carbon's locked
#      environment (scripts/dev/bootstrap.sh) with the groups the documented
#      commands use: science, chain, archive and MCP;
#   4. builds the pinned worker and analysis images on this machine, and the
#      GPU worker with --gpu or whenever one was built here before (every
#      install moves the checkout, so an old GPU worker would no longer match
#      it). A worker already built here from this exact source tree, which
#      Docker still holds, is used again rather than rebuilt, so installs
#      sharing one checkout keep the same images (LA-F16).
#      A DEVELOPMENT C-03 candidate can also reuse a separately verified
#      already loaded C-03/analysis pair without reserving new CPU build space.
#      With --release
#      TAG it builds none: step 2 moves the checkout to
#      that release tag, cut from main, and this step pulls each image the
#      release's records name from ghcr.io/carbonphysicsai, by digest, and
#      checks it (scripts/dev/worker_image_release.py pull). A failed pull
#      stops the install and names the command that builds them instead
#      (OWNER-WORKER-IMAGES-V2-01);
#   5. records where those images are, owner-only, for setup to fill in, and
#      checks setup against them: a compute check made at another revision or
#      with other images is set aside and checked again where it can be, and
#      a runner profile written before is written again. It prints what
#      changed;
#   6. starts the Control Center on 127.0.0.1, in this terminal or, with
#      --service, as this state directory's own systemd user service, and
#      prints how to start, stop and follow it (LA-F15). With the service it
#      also turns on linger, or prints the sudo command that does, so the
#      service starts again after a reboot (MINER-SURVIVE-REBOOT-01).
#
# It never asks for, reads or stores a key, seed phrase or password. Your
# hotkey stays in your own wallet and `carbon-miner-signer`; registration on
# subnet 567 is a transaction you sign in your own tooling. Testnet only;
# DEVELOPMENT: nothing here is qualified, paid or on chain.
set -euo pipefail

UV_VERSION="0.12.7"
REF="${CARBON_REF:-main}"
DEFAULT_STATE_DIR="${HOME}/.carbon/development-launchpad"
STATE_DIR="${CARBON_STATE_DIR:-${DEFAULT_STATE_DIR}}"
PORT="${CARBON_PORT:-8788}"
PORT_GIVEN=$([[ -n "${CARBON_PORT:-}" ]] && echo 1 || echo 0)
GPU=0
PYTORCH=0
START=1
UPDATE=0
SERVICE=0
REMOVE_OLD_IMAGES=0
PRUNE_BUILD_CACHE=0
REF_GIVEN=0
RELEASE=""
DEVELOPMENT_REVISION=""
DEVELOPMENT_TREE=""
DEVELOPMENT_SOURCE_TREE_DIGEST=""
#: Where each release's records are published: the assets of its GitHub
#: release (.github/workflows/release-worker-images.yml). Public; no login.
RELEASE_URL="${CARBON_RELEASE_URL:-https://github.com/carbonphysicsai/Carbon/releases/download}"
#: The release records this install fetches: the worker, the analysis image
#: and the GPU worker, whose reference remote setup names even when this
#: machine does not pull it.
RELEASE_KINDS=(c03 analysis accelerator)
#: The free space an install needs, in GiB. Measured on 2026-10-03: the
#: locked environment is about 0.75 GiB, with uv's cache beside it; the
#: worker image about 1 GiB, the analysis image up to 4.4 GiB, and the GPU
#: worker about 6 GiB, each with Docker's build cache. Each figure is about
#: twice what was measured.
CHECKOUT_GIB=5
IMAGES_GIB=12
GPU_GIB=12
#: The user service of the default state directory. Every other state
#: directory has its own (LA-F15, below).
DEFAULT_SERVICE="carbon-control-center.service"
UNITS="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"

usage() {
  cat <<'EOF'
usage: scripts/install_miner.sh [--update] [--gpu] [--pytorch] [--ref REF | --release TAG]
                                [--no-start] [--service] [--port PORT]
       scripts/install_miner.sh --development-candidate REVISION TREE SOURCE_DIGEST
                                [--gpu] [--pytorch] [--no-start] [--port PORT]

  --update     update an installed checkout: move it to REF (default: the
               latest main), build its images again (or use the ones already
               built from that exact source tree), check setup's compute again
               and rewrite your runner profile, then say what changed
  --gpu        also build the GPU worker of each installed backend: the JAX
               GPU worker, and with --pytorch the PyTorch GPU worker too.
               Practice on this machine's GPU needs an NVIDIA GPU and the
               NVIDIA Container Toolkit; without them the workers are built
               for your own remote GPU
  --pytorch    select the CPU Torch worker and its matching analysis image
               for JAX/PyTorch practice; repeat this option on updates.
               With --release, the release must publish torch-analysis
               (and torch-gpu with --gpu)
  --ref REF    the Carbon ref to install, a branch, tag or commit in main
               (default: main, or $CARBON_REF)
  --release TAG
               install a release of Carbon's worker images instead of
               building them: move the checkout to the release tag TAG
               (worker-images-vN, cut from main) and pull each image its
               release records name, by digest. With --update, TAG must be
               this install's revision or newer
  --development-candidate REVISION TREE SOURCE_DIGEST
               use verified cached images or build this exact clean local
               DEVELOPMENT checkout's images;
               all three identities must match the local commit, tree and
               Git archive SHA-256. Requires its own state directory and
               cannot be combined with --ref, --release or --update.
  --no-start   build everything, but do not start the Control Center
  --remove-old-images
               when space is short, remove Carbon's own images from earlier
               installs that this install no longer records without asking
               (otherwise it lists them and asks first). No other image is
               touched, and one a container still uses is kept
  --prune-build-cache
               when space is short, also prune Docker's unused build cache
               without asking (otherwise it asks first, separately). That
               cache is shared by EVERY Docker build on this machine, not only
               Carbon's, so other projects' builds will be slower the next
               time. Never done by default or by --remove-old-images
  --service    run the Control Center as a systemd user service, so this
               terminal stays free: carbon-control-center for the default
               state directory, and carbon-control-center-NAME-HASH for any
               other CARBON_STATE_DIR. An install never writes, starts or
               stops another state directory's service
  --port PORT  the Control Center's local port (default 8788)
EOF
}

original_args=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) UPDATE=1 ;;
    --gpu) GPU=1 ;;
    --pytorch) PYTORCH=1 ;;
    --ref) REF="${2:?--ref needs a value}"; REF_GIVEN=1; shift ;;
    --release) RELEASE="${2:?--release needs a value}"; shift ;;
    --development-candidate)
      DEVELOPMENT_REVISION="${2:?--development-candidate needs a revision}"
      DEVELOPMENT_TREE="${3:?--development-candidate needs a tree}"
      DEVELOPMENT_SOURCE_TREE_DIGEST="${4:?--development-candidate needs a source digest}"
      shift 3 ;;
    --no-start) START=0 ;;
    --service) SERVICE=1 ;;
    --remove-old-images) REMOVE_OLD_IMAGES=1 ;;
    --prune-build-cache) PRUNE_BUILD_CACHE=1 ;;
    --port) PORT="${2:?--port needs a value}"; PORT_GIVEN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

# Keep the existing primary/analysis fields: choose a complete matched pair.
worker_kind=c03
analysis_kind=analysis
if [[ "${PYTORCH}" == 1 ]]; then
  worker_kind=torch
  analysis_kind=torch-analysis
  # c03 too: the Torch image is built FROM it, and the derived CPU parent a jNO (JAX) catalog entry
  # builds on is that image, so a release install must hold it or answer jNO with backend_not_served.
  RELEASE_KINDS=(torch torch-analysis c03 accelerator)
fi

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'Carbon install stopped: %s\n' "$*" >&2; exit 2; }

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
self="${repo_root}/scripts/install_miner.sh"
self_digest="$(sha256sum < "${self}" | cut -d' ' -f1)"
artifacts="${repo_root}/.carbon-artifacts"

# Each state directory has its own user service (LA-F15). Two installs can
# share one checkout, each with its own CARBON_STATE_DIR; with one shared
# unit, the second install rewrote the first one's service to run its own
# state directory. The default state directory keeps carbon-control-center,
# so existing installs and the docs' commands stay as they were; any other
# is named after its directory, with a hash of its full path. Made absolute
# before step 2 changes directory, so a relative CARBON_STATE_DIR names the
# same directory throughout.
STATE_DIR="$(realpath -ms -- "${STATE_DIR}")"
state_real="$(realpath -m -- "${STATE_DIR}")"
if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
  [[ "${REF_GIVEN}" == 0 && "${REF}" == main && -z "${RELEASE}" && "${UPDATE}" == 0 ]] \
    || fail "--development-candidate cannot be combined with --ref, --release or --update."
  [[ "${state_real}" != "$(realpath -m -- "${DEFAULT_STATE_DIR}")" ]] \
    || fail "--development-candidate requires its own CARBON_STATE_DIR."
  case "${state_real}/" in
    "${repo_root}/"*) fail "DEVELOPMENT state must be outside the source checkout." ;;
  esac
fi
if [[ "${state_real}" == "$(realpath -m -- "${DEFAULT_STATE_DIR}")" ]]; then
  SERVICE_NAME="${DEFAULT_SERVICE}"
else
  state_label="$(printf '%s' "$(basename -- "${state_real}")" | tr -c 'A-Za-z0-9_-' '_' | cut -c1-32)"
  state_hash="$(printf '%s' "${state_real}" | sha256sum | cut -c1-12)"
  SERVICE_NAME="carbon-control-center-${state_label}-${state_hash}.service"
fi
UNIT="${UNITS}/${SERVICE_NAME}"

#: The state directory a unit file runs (its ExecStart's --state-dir), as a
#: full path, or nothing.
unit_state_dir() {
  local dir
  dir="$(sed -n 's/^ExecStart=.* --state-dir \([^ ]*\) .*$/\1/p' -- "$1" 2>/dev/null | head -n 1)"
  [[ -n "${dir}" ]] && realpath -m -- "${dir}"
}

# This install runs as a service when the miner says --service, or when its
# own unit, written by an earlier --service install, runs this very state
# directory. A unit file is written only then, and only this install's own.
own_unit=0
if [[ -f "${UNIT}" && "$(unit_state_dir "${UNIT}" || true)" == "${state_real}" ]]; then
  own_unit=1
fi
service_mode=0
if [[ "${SERVICE}" == 1 || "${own_unit}" == 1 ]]; then
  service_mode=1
fi

if [[ -n "${RELEASE}" ]]; then
  # A release names its own revision: its tag.
  [[ "${REF_GIVEN}" == 0 ]] \
    || fail "name one of --ref and --release: a release installs its own tag."
  [[ "${RELEASE}" =~ ^worker-images-v[0-9]+(\.[0-9]+)*$ ]] \
    || fail "--release ${RELEASE} is not a release of Carbon's worker images; they are tagged worker-images-vN (for example worker-images-v2). Nothing was changed."
  REF="${RELEASE}"
fi
release_dir="${artifacts}/releases/${RELEASE}"

#: fetch_release_records COMMIT: download each of ${RELEASE}'s records into
#: ${release_dir} and refuse any that is not that kind's record for that tag
#: at COMMIT. The release workflow publishes them as canonical JSON; the pull
#: (worker_image_release.py) checks every field again before it trusts one.
fetch_release_records() {
  local commit="$1" kind file field rebuild="${self} --ref ${RELEASE}"
  [[ "${PYTORCH}" == 0 ]] || rebuild+=" --pytorch"
  mkdir -p "${release_dir}"
  for kind in "${RELEASE_KINDS[@]}"; do
    file="${release_dir}/${kind}-worker-image.release.json"
    rm -f "${file}.part"
    curl --fail --silent --show-error --location --proto '=https' \
      --output "${file}.part" "${RELEASE_URL}/${RELEASE}/${kind}-worker-image.release.json" \
      || fail "could not download the ${kind} release record of ${RELEASE} from ${RELEASE_URL}/${RELEASE}/ (above): its images are not published there. Nothing was pulled or built. To build the images on this machine instead, run without --release: ${rebuild}"
    for field in "\"kind\":\"${kind}\"" "\"release_tag\":\"${RELEASE}\"" \
      "\"source_commit\":\"${commit}\""; do
      grep -qF -- "${field}" "${file}.part" \
        || fail "the ${kind} release record of ${RELEASE} is not for ${RELEASE} at ${commit:0:12} (it lacks ${field}). Nothing was pulled or built."
    done
    mv -f "${file}.part" "${file}"
  done
}

#: How the miner stops the Control Center this install would replace.
stop_hint() {
  if [[ -f "${UNIT}" ]]; then
    echo "systemctl --user stop ${SERVICE_NAME%.service}"
  else
    echo "Ctrl-C in its terminal"
  fi
}

#: The free GiB on the filesystem holding $1, or nothing when unreadable.
free_gib() {
  df -Pk -- "$1" 2>/dev/null | awk 'NR == 2 { print int($4 / 1048576) }'
}

#: Where the filesystem holding $1 is mounted, or nothing when unreadable.
mount_of() {
  df -Pk -- "$1" 2>/dev/null | awk 'NR == 2 { print $6 }'
}

#: need_space PATH GIB WHAT: refuse unless GIB are free where PATH is. When
#: df cannot say (it failed, under set -e and pipefail), it says so and goes
#: on rather than ending the install without a word.
need_space() {
  local free
  free="$(free_gib "$1" || true)"
  if [[ -z "${free}" ]]; then
    echo "Could not read the free space at $1; make sure $2 GiB are free there for $3."
    return 0
  fi
  (( free >= $2 )) \
    || fail "$3 need $2 GiB free on the filesystem holding $1, and ${free} GiB are free. See what Docker keeps with: docker system df"
}

step "1/6 Checking this machine"
[[ "$(uname -s)" == "Linux" ]] || fail "Linux is required (Windows: use WSL2)."
[[ "$(uname -m)" == "x86_64" ]] || fail "x86-64 is required."
for tool in git curl docker; do
  command -v "${tool}" >/dev/null 2>&1 || fail "${tool} is not installed."
done
docker info >/dev/null 2>&1 \
  || fail "Docker is installed but not reachable; start it, or add yourself to the docker group."
# The service, and every unit Carbon's runs start, run under the systemd user
# manager, not this shell (LA-F6). A docker group added after the manager
# started is in a new shell's groups but not the manager's, so Docker answers
# here while the service is refused, and the worker doctor then fails as
# "accepted numerical host unavailable". Checked before anything changes.
# A machine without the user manager is refused at step 6, as before.
if [[ "${service_mode}" == 1 ]] && command -v systemctl >/dev/null 2>&1 \
  && systemctl --user show-environment >/dev/null 2>&1; then
  command -v systemd-run >/dev/null 2>&1 \
    || fail "--service needs systemd-run (part of systemd) to check that the service can reach Docker."
  if ! systemd-run --user --wait --quiet --collect --pipe \
    "$(command -v docker)" info --format '{{.ServerVersion}}' </dev/null >/dev/null 2>&1; then
    if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
      restart="From Windows, run: wsl --terminate ${WSL_DISTRO_NAME}, then open the distro again. That stops everything running in it, Docker's containers and any Carbon campaign included."
    else
      restart="Run: sudo systemctl restart user@$(id -u).service (that stops all of your user services, a running Control Center service included), or log out of every session and back in."
    fi
    fail "Docker answers this shell but not your systemd user manager, which runs the Control Center service and everything it starts. Most often the manager started before you joined the docker group, so it does not have the group. Nothing was changed. Restart the manager so it picks the group up. ${restart} Then run this again."
  fi
fi
if [[ "${GPU}" == 1 ]]; then
  # Building the GPU workers needs Docker only. Without the NVIDIA driver
  # here they are built and recorded for the miner's own remote GPU, which
  # setup's remote route sends them to; this machine's GPU practice stays
  # refused by setup's own driver check (M1 E2E S4: a CPU-only controller
  # driving a rented GPU).
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "No NVIDIA driver here (nvidia-smi was not found): the GPU worker(s) are built for your own remote GPU and will not run on this machine."
  fi
fi
if [[ "${UPDATE}" == 1 && ! -d "${STATE_DIR}" ]]; then
  fail "--update found no install at ${STATE_DIR}; run this without --update first."
fi
# The Control Center holds this lock while it runs. An install moves the
# checkout it runs from, so it waits until the miner has stopped it.
if [[ -f "${STATE_DIR}/owner.lock" ]] && command -v flock >/dev/null 2>&1 \
  && ! flock -n "${STATE_DIR}/owner.lock" true 2>/dev/null; then
  fail "a Control Center is running from ${STATE_DIR}. Stop it first ($(stop_hint)); this install moves the checkout it runs from. Then run this again."
fi
# A GPU worker built here before is rebuilt by every install (step 4): the
# JAX GPU worker, and with --pytorch the PyTorch GPU worker beside it.
gpu_space=0
if [[ "${GPU}" == 1 ]] \
  || grep -qs '"gpu_image_manifest"' "${STATE_DIR}/installed-images.json" \
  || [[ -f "${repo_root}/.carbon-artifacts/accelerator-worker-image.json" ]]; then
  gpu_space=$(( 1 + PYTORCH ))
fi
# The PyTorch GPU worker's release record, only where a GPU worker is
# wanted: a --pytorch release install without one needs no torch-gpu.
if [[ "${PYTORCH}" == 1 && "${gpu_space}" -gt 0 ]]; then
  RELEASE_KINDS+=(torch-gpu)
  # Building the PyTorch GPU worker needs Docker BuildKit: its identity is
  # stamped in steps the legacy builder skips silently (M1 12g, Docker 29
  # without buildx). Checked before any image is built; a release install
  # pulls the image instead, and a CPU-only or JAX-only install needs none.
  if [[ -z "${RELEASE}" ]] && ! docker buildx version >/dev/null 2>&1; then
    fail "building the PyTorch GPU worker needs Docker buildx, which this Docker lacks. Install Docker buildx (Ubuntu or Debian: sudo apt-get install docker-buildx-plugin, or docker-buildx with your distribution's Docker), then run the installer again."
  fi
fi
docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
#: offer_old_images: Carbon's own images from earlier installs, which this
#: install's records no longer name, listed and removed only on the miner's
#: yes, or with --remove-old-images (M1 E2E R6-1: earlier rounds' images
#: filled the disk until an update stopped here). Only Carbon's own
#: repositories are listed (scripts/dev/miner_launchpad/superseded_images.py);
#: Docker keeps any image a container still uses. A first install, with no
#: environment yet, has none.
#: offer_build_cache: Docker's unused build cache, on its own flag (--prune-build-cache) and its own yes. It is shared by
#: every Docker build on this machine, so it is never done with Carbon's images and never by default.
build_cache_offered=0
offer_build_cache() {
  local py="${repo_root}/.venv/bin/python" listing answer=""
  [[ "${build_cache_offered}" == 0 ]] || return 0
  build_cache_offered=1
  [[ -x "${py}" ]] || return 0
  listing="$(cd "${repo_root}" && PYTHONDONTWRITEBYTECODE=1 "${py}" -B -m scripts.dev.miner_launchpad.superseded_images \
    cache-list --state-dir "${STATE_DIR}" --repo "${repo_root}" 2>/dev/null)" || return 0
  [[ -n "${listing}" ]] || return 0
  echo "Space is still short. Docker keeps unused build cache:"
  echo "${listing}"
  if [[ "${PRUNE_BUILD_CACHE}" == 0 ]]; then
    if [[ -t 0 ]]; then
      read -r -p "Prune it? This affects EVERY Docker build on this machine, not only Carbon's: other projects' builds will be slower the next time. [y/N] " answer || answer=""
    fi
    if [[ "${answer}" != [yY]* ]]; then
      echo "Kept it. To prune it, answer y, or run this again with --prune-build-cache."
      return 0
    fi
  fi
  (cd "${repo_root}" && PYTHONDONTWRITEBYTECODE=1 "${py}" -B -m scripts.dev.miner_launchpad.superseded_images \
    cache-remove --state-dir "${STATE_DIR}" --repo "${repo_root}") \
    || echo "Docker kept the build cache an active build uses."
}
old_images_offered=0
offer_old_images() {
  local py="${repo_root}/.venv/bin/python" listing answer=""
  # Asked once per install: a second short check re-checks, never re-asks.
  [[ "${old_images_offered}" == 0 ]] || return 0
  old_images_offered=1
  [[ -x "${py}" ]] || return 0
  # -B and PYTHONDONTWRITEBYTECODE: this runs before the development
  # candidate's ignored-source check, which refuses any __pycache__ it
  # leaves (M1 E2E R8b-1).
  listing="$(cd "${repo_root}" && PYTHONDONTWRITEBYTECODE=1 "${py}" -B -m scripts.dev.miner_launchpad.superseded_images \
    list --state-dir "${STATE_DIR}" --repo "${repo_root}" 2>/dev/null)" || return 0
  [[ -n "${listing}" ]] || return 0
  echo "Space is short. These are Carbon's own images and finished practice-job containers from earlier installs, which this install does not use (the catalog images are built again over the new worker):"
  echo "${listing}"
  if [[ "${REMOVE_OLD_IMAGES}" == 0 ]]; then
    if [[ -t 0 ]]; then
      read -r -p "Remove them? No other image or container is touched. [y/N] " answer || answer=""
    fi
    if [[ "${answer}" != [yY]* ]]; then
      echo "Kept them. To remove them, answer y, or run this again with --remove-old-images."
      return 0
    fi
  fi
  (cd "${repo_root}" && PYTHONDONTWRITEBYTECODE=1 "${py}" -B -m scripts.dev.miner_launchpad.superseded_images \
    remove --state-dir "${STATE_DIR}" --repo "${repo_root}") \
    || echo "Docker kept the images above that a container still uses."
}
#: short_of PATH GIB: whether fewer than GIB GiB are free at PATH (no when
#: the free space cannot be read).
short_of() {
  local free
  free="$(free_gib "$1" || true)"
  [[ -n "${free}" ]] && (( free < $2 ))
}
# Carbon's own old images go first, when space is short (gate round 1,
# R11-2 order): the checkout's own free-space check below ran before the
# cleanup was offered, so a disk those images filled was refused by the very
# check their removal would have passed. Offered (or, with
# --remove-old-images, done) now, then every check reads the space again.
if short_of "${repo_root}" "${CHECKOUT_GIB}"   || { [[ -n "${docker_root}" && -d "${docker_root}" ]]     && short_of "${docker_root}" "$(( IMAGES_GIB + gpu_space * GPU_GIB ))"; }; then
  offer_old_images
  offer_build_cache
fi
need_space "${repo_root}" "${CHECKOUT_GIB}" "Carbon's locked environment and its cache"
check_image_space() {
  local images_gib="$1" checkout_mount docker_mount
  if [[ -n "${docker_root}" && -d "${docker_root}" ]]; then
    checkout_mount="$(mount_of "${repo_root}" || true)"
    docker_mount="$(mount_of "${docker_root}" || true)"
    local needed="${images_gib}"
    if [[ -n "${checkout_mount}" && "${checkout_mount}" == "${docker_mount}" ]]; then
      needed="$(( CHECKOUT_GIB + images_gib ))"
    fi
    if short_of "${docker_root}" "${needed}"; then
      offer_old_images
    fi
    if [[ -n "${checkout_mount}" && "${checkout_mount}" == "${docker_mount}" ]]; then
      # One filesystem holds both (WSL's default): it needs room for both.
      need_space "${docker_root}" "$(( CHECKOUT_GIB + images_gib ))" \
        "Carbon's locked environment and images (one filesystem holds both)"
    else
      need_space "${docker_root}" "${images_gib}" "Carbon's images"
    fi
  else
    echo "Docker keeps its images outside this filesystem (${docker_root:-not reported}); make sure ${images_gib} GiB are free there."
  fi
}
# Only an explicit DEVELOPMENT candidate can use a verified, already loaded
# C-03/analysis pair to avoid reserving space for a new CPU image build. Its
# exact-source verification and pure-read pair check happen after bootstrap.
if [[ -z "${DEVELOPMENT_REVISION}" || "${PYTORCH}" == 1 ]]; then
  check_image_space "$(( IMAGES_GIB + gpu_space * GPU_GIB ))"
fi
echo "Linux x86-64, git, curl, Docker and free disk: ready."

step "2/6 Bringing Carbon to ${REF}"
git -C "${repo_root}" rev-parse --show-toplevel >/dev/null 2>&1 \
  || fail "run this script from a Carbon checkout (git clone first)."
cd "${repo_root}"
if [[ -n "${CARBON_INSTALL_AT:-}" && "${CARBON_INSTALL_AT}" == "$(git rev-parse HEAD)" ]]; then
  # Re-run by the installer of the revision step 2 moved to.
  echo "Carbon at ${CARBON_INSTALL_AT:0:12}, with that revision's installer."
else
  dirty="$(git status --porcelain=v1 --untracked-files=all)"
  if [[ -n "${dirty}" ]]; then
    # A here-string, not a pipe: with thousands of paths, printf into a head
    # that has stopped reading dies of SIGPIPE, and set -e would end the
    # install before it says what to do.
    head -n 10 <<<"${dirty}" >&2
    changed="$(wc -l <<<"${dirty}")"
    if (( changed > 10 )); then
      echo "... and $(( changed - 10 )) more." >&2
    fi
    fail "this checkout has local changes (above), and the image build needs it clean: an image's identity is the exact source tree. Set them aside with
  git -C ${repo_root} stash push --include-untracked -m 'set aside by install_miner.sh'
then run this again. git -C ${repo_root} stash pop brings them back."
  fi
  previous="$(git rev-parse HEAD)"
  if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
    target="${previous}"
    [[ "${target}" == "${DEVELOPMENT_REVISION}" ]] \
      || fail "--development-candidate revision differs from this checkout. Nothing was changed."
  else
  git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main" \
    || fail "could not fetch Carbon's main from origin."
  if [[ -n "${RELEASE}" ]]; then
    # Origin's tag itself, never a branch or a local tag of that name.
    git fetch --quiet origin "+refs/tags/${RELEASE}:refs/tags/${RELEASE}" 2>/dev/null \
      || fail "--release ${RELEASE}: origin has no such release tag. Nothing was changed."
    target="$(git rev-parse --verify "refs/tags/${RELEASE}^{commit}")"
  elif [[ "${REF}" == "main" || "${REF}" == "origin/main" ]]; then
    target="$(git rev-parse --verify 'refs/remotes/origin/main^{commit}')"
  elif git fetch --quiet origin "${REF}" 2>/dev/null; then
    target="$(git rev-parse --verify 'FETCH_HEAD^{commit}')"
  else
    target="$(git rev-parse --verify --quiet "${REF}^{commit}")" \
      || fail "--ref ${REF}: origin has no such branch, tag or commit."
  fi
  if [[ -n "${RELEASE}" ]]; then
    git merge-base --is-ancestor "${target}" refs/remotes/origin/main \
      || fail "--release ${RELEASE} (${target:0:12}) is not in Carbon's main, so it is not a release: releases are cut from main (clean_accepted_checkout_required). Nothing was changed."
  fi
  git merge-base --is-ancestor "${target}" refs/remotes/origin/main \
    || fail "--ref ${REF} (${target:0:12}) is not in Carbon's main, and setup accepts only a revision in main (clean_accepted_checkout_required). Use --ref main, or a commit or tag on main."
  fi
  if [[ "${PYTORCH}" == 1 ]]; then
    target_installer="$(git show "${target}:scripts/install_miner.sh" 2>/dev/null || true)"
    pytorch_label="--pytorch"
    [[ "${target_installer}" == *"${pytorch_label})"* ]] \
      || fail "the installer at ${target:0:12} has no --pytorch selection. Nothing was changed. Choose a newer revision with a matching Torch analysis image."
  fi
  if [[ "${UPDATE}" == 1 ]]; then
    # The installer at the target carries on with these options; one from
    # before --update existed would refuse it after the checkout had moved.
    # It knows --update when its option parser has that case label (built
    # here from parts, so this test does not match its own text).
    target_installer="$(git show "${target}:scripts/install_miner.sh" 2>/dev/null || true)"
    update_label="--update"
    [[ "${target_installer}" == *"${update_label})"* ]] \
      || fail "the installer at ${target:0:12} has no --update. Run it without --update: ${self} --ref ${REF}"
  fi
  if [[ -n "${RELEASE}" ]]; then
    # The release's own installer carries on (below), so it must know
    # --release, as with --update above. Releases before this option cannot
    # be installed this way; they can be built.
    target_installer="$(git show "${target}:scripts/install_miner.sh" 2>/dev/null || true)"
    release_label="--release"
    [[ "${target_installer}" == *"${release_label})"* ]] \
      || fail "the installer at ${RELEASE} (${target:0:12}) has no --release, so this release cannot be pulled by it. Nothing was changed. Build its images on this machine instead: ${self} --ref ${RELEASE}"
    # --update moves forward only: to this install's revision or a newer
    # release, never back. Going back is a plain install, named on purpose.
    if [[ "${UPDATE}" == 1 && "${target}" != "${previous}" ]] \
      && git merge-base --is-ancestor "${target}" "${previous}"; then
      fail "--update moves forward only, and ${RELEASE} (${target:0:12}) is older than this install (${previous:0:12}). Nothing was changed. Name a newer release, or install this one without --update: ${self} --release ${RELEASE}"
    fi
    # Every record is fetched and checked before the checkout moves.
    fetch_release_records "${target}"
    echo "Release ${RELEASE}: its records name ${#RELEASE_KINDS[@]} images, each by digest."
  fi
  if [[ "${target}" != "${previous}" ]]; then
    git checkout --quiet --detach "${target}"
    echo "Carbon moved from ${previous:0:12} to ${target:0:12}."
  else
    echo "Carbon at ${target:0:12}, unchanged."
  fi
  if [[ "$(sha256sum < "${self}" | cut -d' ' -f1)" != "${self_digest}" ]]; then
    echo "The installer changed at ${target:0:12}; that version carries on."
    CARBON_INSTALL_AT="${target}" exec bash "${self}" \
      ${original_args[@]+"${original_args[@]}"}
  fi
fi

# Editable uv sync can create ignored egg-info/build metadata in this checkout.
# Refuse every pre-existing ignored source before that happens, including a
# pre-existing output directory: only this install's newly created metadata
# may be removed after bootstrap. The installed Python verifier below still
# checks the full revision, tree and archive identity before any image build.
if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
  [[ "$(git rev-parse HEAD)" == "${DEVELOPMENT_REVISION}" ]] \
    || fail "local DEVELOPMENT source revision differs before bootstrap."
  [[ "$(git rev-parse 'HEAD^{tree}')" == "${DEVELOPMENT_TREE}" ]] \
    || fail "local DEVELOPMENT source tree differs before bootstrap."
  source_digest="sha256:$(git archive --format=tar HEAD | sha256sum | cut -d' ' -f1)"
  [[ "${source_digest}" == "${DEVELOPMENT_SOURCE_TREE_DIGEST}" ]] \
    || fail "local DEVELOPMENT source archive differs before bootstrap."
  [[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "local DEVELOPMENT source has changes before bootstrap."
  ignored="$(git ls-files --others --ignored --exclude-standard --directory)" \
    || fail "could not check ignored DEVELOPMENT source before bootstrap."
  while IFS= read -r path; do
    case "${path}" in
      ""|.venv/|.venv-jax-macos/|.carbon-local/|.pytest_cache/|.ruff_cache/|\
      .carbon-artifacts/|.agent/runtime/|website/ask-carbon/.wrangler/) ;;
      *) fail "development candidate has ignored runtime source before bootstrap: ${path}" ;;
    esac
  done <<< "${ignored}"
  for output in carbon.egg-info build; do
    [[ ! -e "${repo_root}/${output}" && ! -L "${repo_root}/${output}" ]] \
      || fail "development candidate has pre-existing bootstrap output: ${output}"
  done
  # Python imports during bootstrap/verification must not make ignored source
  # caches outside the isolated .venv. This does not change editable install.
  export PYTHONDONTWRITEBYTECODE=1
fi

step "3/6 Installing Carbon's locked environment"
export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1 || [[ "$(uv --version | awk '{print $2}')" != "${UV_VERSION}" ]]; then
  echo "Installing uv ${UV_VERSION} (Astral's installer) into ~/.local/bin."
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
fi
# Every group a documented command runs with (`uv run --group ...`), so none
# of them re-syncs this environment.
CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/bootstrap.sh
if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
  # These exact root directories were absent at the verified pre-bootstrap
  # boundary. Refuse links/files and unknown paths rather than deleting them.
  for output in carbon.egg-info build; do
    path="${repo_root}/${output}"
    if [[ -e "${path}" || -L "${path}" ]]; then
      [[ -d "${path}" && ! -L "${path}" ]] \
        || fail "bootstrap output is not an owned directory: ${output}"
      if [[ "${output}" == carbon.egg-info ]]; then
        while IFS= read -r -d '' entry; do
          [[ -f "${entry}" && ! -L "${entry}" ]] \
            || fail "bootstrap created non-file metadata; no output was removed."
          case "${entry##*/}" in
            PKG-INFO|SOURCES.txt|dependency_links.txt|entry_points.txt|\
            requires.txt|top_level.txt|not-zip-safe) ;;
            *) fail "bootstrap created unexpected metadata; no output was removed." ;;
          esac
        done < <(find "${path}" -mindepth 1 -maxdepth 1 -print0)
        rm -f -- "${path}/PKG-INFO" "${path}/SOURCES.txt" \
          "${path}/dependency_links.txt" "${path}/entry_points.txt" \
          "${path}/requires.txt" "${path}/top_level.txt" \
          "${path}/not-zip-safe"
      fi
      rmdir -- "${path}" \
        || fail "bootstrap output was not empty after owned metadata removal."
    fi
  done
fi
python="${repo_root}/.venv/bin/python"
setup_cli=("${python}" -m scripts.dev.miner_launchpad.environment_setup)
if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
  "${python}" -m scripts.dev.miner_launchpad.installed verify-development-source \
    --revision "${DEVELOPMENT_REVISION}" \
    --tree "${DEVELOPMENT_TREE}" \
    --source-tree-digest "${DEVELOPMENT_SOURCE_TREE_DIGEST}" \
    || fail "local DEVELOPMENT source identity differs. No image was built."
fi

#: current_image MANIFEST: whether MANIFEST names a worker built from this
#: checkout's exact source tree that Docker still holds (installed.current).
current_image() {
  if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
    [[ "$("${python}" -m scripts.dev.miner_launchpad.installed current --manifest "$1" \
      --candidate-revision "${DEVELOPMENT_REVISION}" \
      --candidate-tree "${DEVELOPMENT_TREE}" \
      --candidate-source-tree-digest "${DEVELOPMENT_SOURCE_TREE_DIGEST}" 2>/dev/null)" == "yes" ]]
  else
    [[ "$("${python}" -m scripts.dev.miner_launchpad.installed current --manifest "$1" 2>/dev/null)" == "yes" ]]
  fi
}

# Every install, not only --update: a plain run moves the checkout to the
# latest main too, and an old GPU worker would then be checked again, and
# written into the profile, beside images of the new revision.
gpu_build="${GPU}"
if [[ "${GPU}" == 0 ]] \
  && [[ "$("${setup_cli[@]}" gpu-installed --state-dir "${STATE_DIR}")" == "yes" ]]; then
  if [[ -n "${RELEASE}" ]]; then
    echo "A GPU worker was built here before; this install pulls it too."
  else
    echo "A GPU worker was built here before; this install rebuilds it too."
  fi
  gpu_build=1
fi

if [[ -n "${DEVELOPMENT_REVISION}" && "${PYTORCH}" == 0 ]]; then
  dev_pair_args=(
    --artifacts-root "${artifacts}"
    --revision "${DEVELOPMENT_REVISION}"
    --tree "${DEVELOPMENT_TREE}"
    --source-tree-digest "${DEVELOPMENT_SOURCE_TREE_DIGEST}"
  )
  # The artifact verifier reads the two normal manifest paths and inspects
  # Docker. It never loads or builds an image. An invalid cache is a refusal,
  # not permission to silently rebuild from a different identity.
  if pair_status="$("${python}" -m scripts.dev.development_image_artifact verify-installed \
    "${dev_pair_args[@]}")"; then
    case "${pair_status}" in
      VERIFIED) cpu_build_gib=0 ;;
      ABSENT) cpu_build_gib="${IMAGES_GIB}" ;;
      *) fail "DEVELOPMENT image cache verifier returned an unknown status. No image was built." ;;
    esac
  else
    fail "DEVELOPMENT image cache is invalid or could not be verified. No image was built."
  fi
  check_image_space "$(( cpu_build_gib + gpu_build * (1 + PYTORCH) * GPU_GIB ))"
fi

worker_manifest="${artifacts}/${worker_kind}-worker-image.json"
gpu_manifest=""
gpu_release_record=""
#: The PyTorch GPU worker (`scripts/dev/torch_gpu_worker_image.sh`), built
#: with --gpu when the PyTorch backend is installed (Validator ruling: --gpu
#: selects the GPU worker of each installed backend).
torch_gpu_manifest=""
if [[ -n "${RELEASE}" ]]; then
  step "4/6 Pulling the released images of ${RELEASE} by digest"
  # Fetched again at the revision this installer runs at: a carried-on
  # installer did not run step 2 itself.
  fetch_release_records "$(git rev-parse HEAD)"
  kinds=("${worker_kind}" "${analysis_kind}")
  rebuild="${self} --ref ${RELEASE}"
  if [[ "${PYTORCH}" == 1 ]]; then
    rebuild+=" --pytorch"
    kinds+=(c03)
  fi
  if [[ "${gpu_build}" == 1 ]]; then
    kinds+=(accelerator)
    rebuild+=" --gpu"
    if [[ "${PYTORCH}" == 1 ]]; then
      kinds+=(torch-gpu)
    fi
  fi
  for kind in "${kinds[@]}"; do
    "${python}" -m scripts.dev.worker_image_release pull \
      --record "${release_dir}/${kind}-worker-image.release.json" \
      --out "${release_dir}/${kind}-worker-image.json" \
      || fail "could not pull or verify the released ${kind} image of ${RELEASE} (above). Nothing was built, and nothing was recorded for setup. To build the images on this machine instead, run without --release: ${rebuild}"
  done
  echo "Pulled and verified ${kinds[*]} of ${RELEASE}; nothing was built."
  worker_manifest="${release_dir}/${worker_kind}-worker-image.json"
  analysis="${release_dir}/${analysis_kind}-worker-image.json"
  if [[ "${gpu_build}" == 1 ]]; then
    gpu_manifest="${release_dir}/accelerator-worker-image.json"
    if [[ "${PYTORCH}" == 1 ]]; then
      torch_gpu_manifest="${release_dir}/torch-gpu-worker-image.json"
    fi
  fi
  gpu_release_record="${release_dir}/accelerator-worker-image.release.json"
else
  step "4/6 Building the pinned images on this machine"
  if [[ "${pair_status:-}" == VERIFIED ]]; then
    # The build-space reserve was waived only for this exact installed pair.
    # Recheck it now and select its manifest directly: either builder could
    # otherwise start a new image if a cache member vanished between steps.
    current_image "${worker_manifest}" \
      || fail "verified DEVELOPMENT worker cache changed. No image was built."
    analysis="$("${python}" -m scripts.dev.development_image_artifact verify-installed \
      "${dev_pair_args[@]}" --print-analysis-manifest)" \
      || fail "verified DEVELOPMENT image pair changed. No image was built."
    [[ -f "${analysis}" ]] \
      || fail "verified DEVELOPMENT analysis manifest vanished. No image was built."
    echo "The exact DEVELOPMENT worker and analysis pair is present; using it without a build."
  else
    # Another install sharing this checkout may have built them at this very
    # source tree already (LA-F16). A rebuild would be a new image with a new
    # id, written over the manifest that install recorded, and its analysis
    # image and compute check would no longer match. So a worker whose
    # manifest names this exact source tree, and whose image Docker still
    # holds, is used again; the analysis image built on it then is too.
    if current_image "${worker_manifest}"; then
      echo "The worker image built here from this exact source tree is still present; using it again."
    else
      if [[ "${PYTORCH}" == 1 ]]; then
        ./scripts/dev/torch_worker_image.sh "${worker_manifest}"
      else
        ./scripts/dev/c03_worker_image.sh "${worker_manifest}"
      fi
    fi
    analysis="$(
      "${python}" -m carbon.development_session.research_image \
        --parent-manifest "${worker_manifest}" \
        --root "${artifacts}/research-images" \
      | "${python}" -c 'import json, sys; print(json.load(sys.stdin)["manifest"])'
    )"
  fi
  if [[ "${gpu_build}" == 1 ]]; then
    if current_image "${artifacts}/accelerator-worker-image.json"; then
      echo "The GPU worker built here from this exact source tree is still present; using it again."
    else
      ./scripts/dev/accelerator_worker_image.sh "${artifacts}/accelerator-worker-image.json"
    fi
    gpu_manifest="${artifacts}/accelerator-worker-image.json"
    if [[ "${PYTORCH}" == 1 ]]; then
      if current_image "${artifacts}/torch-gpu-worker-image.json"; then
        echo "The PyTorch GPU worker built here from this exact source tree is still present; using it again."
      else
        ./scripts/dev/torch_gpu_worker_image.sh "${artifacts}/torch-gpu-worker-image.json"
      fi
      torch_gpu_manifest="${artifacts}/torch-gpu-worker-image.json"
    fi
  fi
fi

# GPU catalog practice prepares each build's overlay with the pinned uv image
# (carbon/development_session/library_bundles.py, UV_IMAGE): pulled here by
# digest when a GPU worker is installed and Docker lacks it (gate2c: its
# absence read only as a silent CPU fallback). Never fatal: GPU practice then
# says it is missing, with this command.
if [[ "${gpu_build}" == 1 ]]; then
  uv_image="$(grep -o 'UV_IMAGE = "[^"]*"' "${repo_root}/carbon/development_session/library_bundles.py" 2>/dev/null | head -n1 | cut -d'"' -f2 || true)"
  if [[ -n "${uv_image}" ]] && ! docker image inspect "${uv_image}" >/dev/null 2>&1; then
    if docker pull "${uv_image}" >/dev/null 2>&1; then
      echo "Pulled the pinned uv image GPU builds prepare with."
    else
      echo "Could not pull the pinned uv image GPU builds prepare with; GPU catalog practice says so until it is here. Run: docker pull ${uv_image}"
    fi
  fi
fi

step "5/6 Recording the images and checking setup against them"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"
"${python}" -m scripts.dev.miner_launchpad.installed write \
  --state-dir "${STATE_DIR}" \
  --image-manifest "${worker_manifest}" \
  --analysis-image-manifest "${analysis}" \
  ${gpu_manifest:+--gpu-image-manifest "${gpu_manifest}"} \
  ${torch_gpu_manifest:+--torch-gpu-image-manifest "${torch_gpu_manifest}"} \
  $([[ -n "${DEVELOPMENT_REVISION}" ]] || echo --clear-development-candidate) \
  ${gpu_release_record:+--gpu-release-record "${gpu_release_record}"}
if [[ -n "${DEVELOPMENT_REVISION}" ]]; then
  "${python}" -m scripts.dev.miner_launchpad.installed bind-development-candidate \
    --state-dir "${STATE_DIR}" \
    --revision "${DEVELOPMENT_REVISION}" \
    --tree "${DEVELOPMENT_TREE}" \
    --source-tree-digest "${DEVELOPMENT_SOURCE_TREE_DIGEST}"
fi
"${setup_cli[@]}" after-install --state-dir "${STATE_DIR}"
# The backbone catalog is built over this install's construction parent: an
# update that rebuilt the parent leaves every entry uninstalled (M1 E2E
# R7-1), and a newcomer should never have to know to install it (E2). When
# a runner profile exists and entries are missing for the current parent,
# it starts here in the background, said first; the page shows its
# progress. A new install has no profile yet: the page starts it once
# Review writes one.
catalog_missing="$("${setup_cli[@]}" catalog-needed --state-dir "${STATE_DIR}" 2>/dev/null || true)"
if [[ "${catalog_missing}" =~ ^[0-9]+$ ]]; then
  echo
  echo "The backbone catalog needs ${catalog_missing} entries built over this install's construction parent."
  echo "Starting it in the background now (about 40 minutes for the whole catalog on Carbon's test machine); the Control Center's setup shows its progress, and each Challenge can practise a catalog backbone as soon as its entry is ready. Everything else is ready now."
  "${python}" -B -m scripts.dev.miner_launchpad.catalog_build start --state-dir "${STATE_DIR}" >/dev/null \
    || echo "The catalog install could not start; the Control Center's setup offers it again, or run: ${python} -B -m scripts.dev.catalog_install --state-dir ${STATE_DIR}"
fi

cat <<EOF

Next, in a terminal of your own (Carbon never holds your key):
  ${repo_root}/.venv/bin/carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>

Then, in the Control Center:
  - Wallet & Identity: confirm your hotkey is registered on subnet 567
    (it prepares the unsigned call and the command to run if not; you sign
    it in your own wallet).
  - Set up your environment: inference, compute and agent; the image paths
    and the evaluation endpoint are filled in for you.
  - Challenges: choose what to mine, then launch.
EOF

step "6/6 Starting the Control Center"
#: remote_line: on a rented server reached over SSH, the one command the
#: miner runs on their own computer to reach the page (M1 E2E E1).
remote_line() {
  [[ -n "${SSH_CONNECTION:-}" ]] || return 0
  local host
  host="$(printf '%s' "${SSH_CONNECTION}" | cut -d' ' -f3)"
  [[ -n "${host}" ]] || host="<this machine's address>"
  echo "This is a remote machine. On your own computer, run:"
  echo "  ssh -N -L ${PORT}:127.0.0.1:${PORT} ${USER:-$(id -un)}@${host}"
  echo "then open the link below there."
}
#: open_page_lines: the last lines: the remote line, then the page's link
#: carrying this install's session token, to this terminal only and never
#: to a log (M1 E2E E1: no token to fetch or paste). The token is kept in
#: the state directory and survives restarts and updates.
open_page_lines() {
  remote_line
  if [[ ! -t 1 ]]; then
    # Captured or piped (tee, an agent, CI): never the token itself, which
    # would then sit in that capture (Validator, E1 review).
    echo "Open the Control Center at http://127.0.0.1:${PORT}; its session token is in ${STATE_DIR}/session-token (owner-only). Run this installer in a terminal to get a link that carries it."
  elif [[ "${page_link}" == http://127.0.0.1:"${PORT}"/* ]]; then
    echo "Open the Control Center (this link holds your session token; do not share it):"
    echo "${page_link}"
  else
    echo "Open the Control Center at http://127.0.0.1:${PORT}"
  fi
}
#: page_link_for: the page's link for the port the Control Center will use.
page_link_for() {
  page_link="$("${setup_cli[@]}" session-link --state-dir "${STATE_DIR}" --port "${PORT}" 2>/dev/null || true)"
}
page_link_for
launcher=("${repo_root}/.venv/bin/carbon-control-center")
[[ -x "${launcher[0]}" ]] \
  || launcher=("${python}" "${repo_root}/scripts/dev/miner_launchpad/controller.py")
start_command="PYTHONDONTWRITEBYTECODE=1 ${launcher[*]} --state-dir ${STATE_DIR} --port ${PORT}"

# Units written before LA-F15 all had the default service's name, so one may
# run another state directory than its name's. This install never rewrites
# such a unit unless it is this install's own name and the miner says
# --service; it says what it found instead.
if [[ "${service_mode}" == 0 && -f "${UNIT}" ]]; then
  echo "Note: the user service ${SERVICE_NAME%.service} runs the Control Center of $(unit_state_dir "${UNIT}" || echo 'another state directory'), not this install's ${STATE_DIR}. This install left it alone. To run this install as that service instead, install again with --service."
fi
default_unit="${UNITS}/${DEFAULT_SERVICE}"
if [[ "${SERVICE_NAME}" != "${DEFAULT_SERVICE}" && -f "${default_unit}" ]] \
  && [[ "$(unit_state_dir "${default_unit}" || true)" == "${state_real}" ]]; then
  echo "Note: the user service ${DEFAULT_SERVICE%.service} runs this install's state directory, but that service belongs to the default state directory ${DEFAULT_STATE_DIR}: an installer from before LA-F15 rewrote it. This install left it alone; its own service is ${SERVICE_NAME%.service}. If you no longer use the default install's service, stop it with: systemctl --user disable --now ${DEFAULT_SERVICE%.service}. Otherwise run the default install again with --service, which gives it back its own state directory."
fi

if [[ "${service_mode}" == 1 ]]; then
  # The miner chose the service for this state directory, now or at an
  # earlier install: this install rewrites its own unit and starts it,
  # unless --no-start. An earlier unit's port is kept unless --port or
  # CARBON_PORT names another.
  if [[ "${own_unit}" == 1 && "${PORT_GIVEN}" == 0 ]]; then
    unit_port="$(sed -n 's/^ExecStart=.* --port \([0-9]*\)$/\1/p' -- "${UNIT}" | head -n 1)"
    if [[ -n "${unit_port}" ]]; then
      PORT="${unit_port}"
      start_command="PYTHONDONTWRITEBYTECODE=1 ${launcher[*]} --state-dir ${STATE_DIR} --port ${PORT}"
      page_link_for
    fi
  fi
  command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1 \
    || fail "--service needs systemd's user manager (systemctl --user). On WSL, turn systemd on in /etc/wsl.conf; or start it yourself with: ${start_command}"
  mkdir -p "$(dirname -- "${UNIT}")"
  "${setup_cli[@]}" service-unit --state-dir "${STATE_DIR}" --port "${PORT}" > "${UNIT}.tmp"
  mv -f "${UNIT}.tmp" "${UNIT}"
  # The log carries the session token. The unit's UMask covers a log the
  # service creates; systemd leaves an existing one's mode alone, so this
  # makes it owner-only either way.
  log="${STATE_DIR}/control-center.log"
  [[ ! -L "${log}" ]] || fail "${log} is a symbolic link; remove it, then run this again."
  ( umask 077 && : >> "${log}" )
  chmod 600 "${log}"
  systemctl --user daemon-reload
  systemctl --user enable --quiet "${SERVICE_NAME}"
  if [[ "${START}" == 1 ]]; then
    systemctl --user restart "${SERVICE_NAME}"
    echo "The Control Center runs as the user service ${SERVICE_NAME%.service}, on http://127.0.0.1:${PORT}."
  else
    echo "The Control Center is installed as the user service ${SERVICE_NAME%.service}; it was not started."
  fi
  cat <<EOF
  This install's own service: ${SERVICE_NAME%.service} (state directory ${STATE_DIR}).
  Restart it:  systemctl --user restart ${SERVICE_NAME%.service}
  Stop it:     systemctl --user stop ${SERVICE_NAME%.service}
  Its state:   systemctl --user status ${SERVICE_NAME%.service}
  Its output:  tail -f ${STATE_DIR}/control-center.log
EOF
  # MINER-SURVIVE-REBOOT-01: the unit is enabled, but the user manager that
  # starts it runs at boot only when this user lingers; otherwise it waits
  # for a login. Turned on here when loginctl allows it without sudo (many
  # systems do, WSL included); otherwise the sudo command is printed. Never
  # fatal: the service runs now either way. Nothing else is touched.
  linger_user="${USER:-$(id -un)}"
  linger_state() {
    loginctl show-user "${linger_user}" -p Linger --value 2>/dev/null || true
  }
  if ! command -v loginctl >/dev/null 2>&1; then
    echo "Could not check whether your services start at boot: loginctl was not found. If they do not, the Control Center will not start after a reboot until you run: sudo loginctl enable-linger ${linger_user}"
  else
    if [[ "$(linger_state)" != "yes" ]]; then
      loginctl enable-linger "${linger_user}" >/dev/null 2>&1 || true
      if [[ "$(linger_state)" != "yes" ]]; then
        echo "The Control Center will not start after a reboot until you run: sudo loginctl enable-linger ${linger_user}"
      fi
    fi
    linger="$(linger_state)"
    echo "Start at boot without a login (linger) for ${linger_user}: ${linger:-unknown}."
  fi
  if grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null; then
    echo "On WSL, Windows does not start WSL at boot: see \"After a reboot\" in docs/development/FRESH_MINER_JOURNEY.md for the one-time logon task that starts this distro."
  fi
  open_page_lines
  exit 0
fi

echo "Start it again later with:"
echo "  ${start_command}"
if [[ "${START}" == 0 || "${UPDATE}" == 1 ]]; then
  open_page_lines
  exit 0
fi
# Started here in the foreground: it prints the same link itself, last.
remote_line
export PYTHONDONTWRITEBYTECODE=1
exec "${launcher[@]}" --state-dir "${STATE_DIR}" --port "${PORT}"
