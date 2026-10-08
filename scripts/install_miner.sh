#!/usr/bin/env bash
# One command from a clean Linux machine to the Carbon Control Center (C-MLP-04),
# and the same command to update it (LP-PROD-E).
#
#   git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
#   ~/carbon/scripts/install_miner.sh            # add --gpu for GPU practice
#   ~/carbon/scripts/install_miner.sh --update   # later: the latest main
#   ~/carbon/scripts/install_miner.sh --release worker-images-vN
#                                                # Carbon's released images
#
# What it does, in order, and nothing else:
#   1. checks this machine: Linux x86-64, git, curl, a running Docker (for
#      the service, reachable from the systemd user manager that runs it too),
#      the free disk the environment and images need, and that no Control
#      Center is running from the state directory this install changes;
#   2. brings the checkout to the requested ref (the latest main by default).
#      The checkout must be clean, because an image's identity is the exact
#      source tree, and the ref must be in Carbon's main, because setup
#      accepts only a revision in main. When the installer itself changed at
#      that ref, the new installer carries on from here;
#   3. installs the pinned uv if missing and syncs Carbon's locked
#      environment (scripts/dev/bootstrap.sh) with the groups the documented
#      commands use: science, chain, archive and MCP;
#   4. builds the pinned worker and analysis images on this machine, and the
#      GPU worker with --gpu or whenever one was built here before (every
#      install moves the checkout, so an old GPU worker would no longer match
#      it). With --release TAG it builds none: step 2 moves the checkout to
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
#      --service, as a systemd user service, and prints how to start it again.
#
# It never asks for, reads or stores a key, seed phrase or password. Your
# hotkey stays in your own wallet and `carbon-miner-signer`; registration on
# subnet 567 is a transaction you sign in your own tooling. Testnet only;
# DEVELOPMENT: nothing here is qualified, paid or on chain.
set -euo pipefail

UV_VERSION="0.12.7"
REF="${CARBON_REF:-main}"
STATE_DIR="${CARBON_STATE_DIR:-${HOME}/.carbon/development-launchpad}"
PORT="${CARBON_PORT:-8788}"
GPU=0
START=1
UPDATE=0
SERVICE=0
REF_GIVEN=0
RELEASE=""
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
SERVICE_NAME="carbon-control-center.service"
UNIT="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user/${SERVICE_NAME}"

usage() {
  cat <<'EOF'
usage: scripts/install_miner.sh [--update] [--gpu] [--ref REF | --release TAG]
                                [--no-start] [--service] [--port PORT]

  --update     update an installed checkout: move it to REF (default: the
               latest main), rebuild its images, check setup's compute again
               and rewrite your runner profile, then say what changed
  --gpu        also build the GPU worker (needs an NVIDIA GPU and the
               NVIDIA Container Toolkit)
  --ref REF    the Carbon ref to install, a branch, tag or commit in main
               (default: main, or $CARBON_REF)
  --release TAG
               install a release of Carbon's worker images instead of
               building them: move the checkout to the release tag TAG
               (worker-images-vN, cut from main) and pull each image its
               release records name, by digest. With --update, TAG must be
               this install's revision or newer
  --no-start   build everything, but do not start the Control Center
  --service    run the Control Center as a systemd user service
               (carbon-control-center), so this terminal stays free
  --port PORT  the Control Center's local port (default 8788)
EOF
}

original_args=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) UPDATE=1 ;;
    --gpu) GPU=1 ;;
    --ref) REF="${2:?--ref needs a value}"; REF_GIVEN=1; shift ;;
    --release) RELEASE="${2:?--release needs a value}"; shift ;;
    --no-start) START=0 ;;
    --service) SERVICE=1 ;;
    --port) PORT="${2:?--port needs a value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'Carbon install stopped: %s\n' "$*" >&2; exit 2; }

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
self="${repo_root}/scripts/install_miner.sh"
self_digest="$(sha256sum < "${self}" | cut -d' ' -f1)"
artifacts="${repo_root}/.carbon-artifacts"

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
  local commit="$1" kind file field
  mkdir -p "${release_dir}"
  for kind in "${RELEASE_KINDS[@]}"; do
    file="${release_dir}/${kind}-worker-image.release.json"
    rm -f "${file}.part"
    curl --fail --silent --show-error --location --proto '=https' \
      --output "${file}.part" "${RELEASE_URL}/${RELEASE}/${kind}-worker-image.release.json" \
      || fail "could not download the ${kind} release record of ${RELEASE} from ${RELEASE_URL}/${RELEASE}/ (above): its images are not published there. Nothing was pulled or built. To build the images on this machine instead, run without --release: ${self} --ref ${RELEASE}"
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
if [[ "${SERVICE}" == 1 || -f "${UNIT}" ]] && command -v systemctl >/dev/null 2>&1 \
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
  command -v nvidia-smi >/dev/null 2>&1 \
    || fail "--gpu needs the NVIDIA driver (nvidia-smi was not found)."
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
# A GPU worker built here before is rebuilt by every install (step 4).
gpu_space=0
if [[ "${GPU}" == 1 ]] \
  || grep -qs '"gpu_image_manifest"' "${STATE_DIR}/installed-images.json" \
  || [[ -f "${repo_root}/.carbon-artifacts/accelerator-worker-image.json" ]]; then
  gpu_space=1
fi
need_space "${repo_root}" "${CHECKOUT_GIB}" "Carbon's locked environment and its cache"
docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
images_gib=$(( IMAGES_GIB + gpu_space * GPU_GIB ))
if [[ -n "${docker_root}" && -d "${docker_root}" ]]; then
  checkout_mount="$(mount_of "${repo_root}" || true)"
  docker_mount="$(mount_of "${docker_root}" || true)"
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

step "3/6 Installing Carbon's locked environment"
export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1 || [[ "$(uv --version | awk '{print $2}')" != "${UV_VERSION}" ]]; then
  echo "Installing uv ${UV_VERSION} (Astral's installer) into ~/.local/bin."
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
fi
# Every group a documented command runs with (`uv run --group ...`), so none
# of them re-syncs this environment.
CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/bootstrap.sh
python="${repo_root}/.venv/bin/python"
setup_cli=("${python}" -m scripts.dev.miner_launchpad.environment_setup)

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

worker_manifest="${artifacts}/c03-worker-image.json"
gpu_manifest=""
gpu_release_record=""
if [[ -n "${RELEASE}" ]]; then
  step "4/6 Pulling the released images of ${RELEASE} by digest"
  # Fetched again at the revision this installer runs at: a carried-on
  # installer did not run step 2 itself.
  fetch_release_records "$(git rev-parse HEAD)"
  kinds=(c03 analysis)
  rebuild="${self} --ref ${RELEASE}"
  if [[ "${gpu_build}" == 1 ]]; then
    kinds+=(accelerator)
    rebuild+=" --gpu"
  fi
  for kind in "${kinds[@]}"; do
    "${python}" -m scripts.dev.worker_image_release pull \
      --record "${release_dir}/${kind}-worker-image.release.json" \
      --out "${release_dir}/${kind}-worker-image.json" \
      || fail "could not pull or verify the released ${kind} image of ${RELEASE} (above). Nothing was built, and nothing was recorded for setup. To build the images on this machine instead, run without --release: ${rebuild}"
  done
  echo "Pulled and verified ${kinds[*]} of ${RELEASE}; nothing was built."
  worker_manifest="${release_dir}/c03-worker-image.json"
  analysis="${release_dir}/analysis-worker-image.json"
  if [[ "${gpu_build}" == 1 ]]; then
    gpu_manifest="${release_dir}/accelerator-worker-image.json"
  fi
  gpu_release_record="${release_dir}/accelerator-worker-image.release.json"
else
  step "4/6 Building the pinned images on this machine"
  ./scripts/dev/c03_worker_image.sh "${artifacts}/c03-worker-image.json"
  analysis="$(
    "${python}" -m carbon.development_session.research_image \
      --parent-manifest "${artifacts}/c03-worker-image.json" \
      --root "${artifacts}/research-images" \
    | "${python}" -c 'import json, sys; print(json.load(sys.stdin)["manifest"])'
  )"
  if [[ "${gpu_build}" == 1 ]]; then
    ./scripts/dev/accelerator_worker_image.sh "${artifacts}/accelerator-worker-image.json"
    gpu_manifest="${artifacts}/accelerator-worker-image.json"
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
  ${gpu_release_record:+--gpu-release-record "${gpu_release_record}"}
"${setup_cli[@]}" after-install --state-dir "${STATE_DIR}"

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
launcher=("${repo_root}/.venv/bin/carbon-control-center")
[[ -x "${launcher[0]}" ]] \
  || launcher=("${python}" "${repo_root}/scripts/dev/miner_launchpad/controller.py")
start_command="${launcher[*]} --state-dir ${STATE_DIR} --port ${PORT}"

if [[ "${SERVICE}" == 1 || -f "${UNIT}" ]]; then
  # The miner chose the service (now or at an earlier install): this
  # install rewrites its unit and starts it, unless --no-start.
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
  Your session token (paste it into the page):
    grep 'Local session token' ${STATE_DIR}/control-center.log | tail -n 1
  Restart it:  systemctl --user restart ${SERVICE_NAME%.service}
  Stop it:     systemctl --user stop ${SERVICE_NAME%.service}
  Its output:  ${STATE_DIR}/control-center.log
EOF
  exit 0
fi

echo "Start it again later with:"
echo "  ${start_command}"
if [[ "${START}" == 0 || "${UPDATE}" == 1 ]]; then
  exit 0
fi
exec "${launcher[@]}" --state-dir "${STATE_DIR}" --port "${PORT}"
