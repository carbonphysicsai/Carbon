#!/usr/bin/env bash
# One command from a clean Linux machine to a validator host that is ready to
# rebuild and judge miner models (DEVELOPMENT).
#
#   git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
#   ~/carbon/scripts/install_validator.sh              # add --gpu for GPU rebuilds
#   ~/carbon/scripts/install_validator.sh --check-only # only the machine checks
#
# What it does, in order, and nothing else:
#   1. checks this machine against the published validator requirements
#      (reports/VALIDATOR_REQUIREMENTS_DRAFT_20261019.md) and refuses with every
#      failed requirement, its code and the next step, before anything changes;
#   2. runs scripts/install_miner.sh --pytorch --no-start with your other
#      arguments (--gpu, --release TAG, --ref REF, --development-candidate ...).
#      That installer already brings the pinned uv and CPython, the locked
#      environment, and builds or pulls the pinned worker and analysis images;
#   3. checks the result: the recorded worker and analysis images exist in
#      Docker.
#
# Exit 0 means the host and its images are ready. It does NOT start a receiver,
# write a receiver configuration, or sync answer keys or weights: that setup is
# the operator route (carbon.validator_setup, the receiver tooling) and is not
# part of this script. It never asks for or stores a key or password.
set -euo pipefail

# Draft requirement values (VALIDATOR_REQUIREMENTS_DRAFT_20261019.md); a published
# sheet replaces them. Override only for tests.
MIN_FREE_GIB="${CARBON_VALIDATOR_MIN_FREE_GIB:-60}"
MIN_CPUS="${CARBON_VALIDATOR_MIN_CPUS:-2}"
MIN_RAM_GIB="${CARBON_VALIDATOR_MIN_RAM_GIB:-4}"
MIN_NVIDIA_DRIVER_MAJOR="${CARBON_VALIDATOR_MIN_NVIDIA_DRIVER_MAJOR:-580}"
STATE_DIR="${CARBON_STATE_DIR:-${HOME}/.carbon/development-launchpad}"

usage() {
  cat <<'EOF'
usage: scripts/install_validator.sh [--check-only] [--gpu] [install_miner.sh options]

  --check-only  run the machine checks and stop
  --gpu         also require and build the GPU worker (NVIDIA driver 580 or
                later and the NVIDIA Container Toolkit)

Other options (--release TAG, --ref REF, --development-candidate ..., --port)
are passed to scripts/install_miner.sh, which always runs with --pytorch
--no-start here.
EOF
}

check_only=0
gpu=0
pass=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) check_only=1 ;;
    --gpu) gpu=1; pass+=("$1") ;;
    -h|--help) usage; exit 0 ;;
    --development-candidate) pass+=("$1" "${2:-}" "${3:-}" "${4:-}"); shift 3 ;;
    --ref|--release|--port) pass+=("$1" "${2:-}"); shift ;;
    --pytorch|--no-start) ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

step() { printf '\n== %s\n' "$*"; }
failures=()
refuse() { failures+=("$1: $2 Next: $3"); }

step "1/3 Checking this machine against the validator requirements"
[[ "$(uname -s)" == "Linux" ]] || refuse V_OS "Linux is required." "use a Linux VM or bare-metal host (Windows: not supported for validators)."
[[ "$(uname -m)" == "x86_64" ]] || refuse V_ARCH "x86-64 is required (this is $(uname -m))." "use an x86-64 machine."
for tool in git curl sha256sum; do
  command -v "${tool}" >/dev/null 2>&1 || refuse V_TOOL "${tool} is not installed." "install ${tool} from your OS packages."
done

# A container (Docker, Podman, Kubernetes; cgroup v1 or v2 hosts alike).
in_container=0
if [[ -f /.dockerenv || -f /run/.containerenv ]] \
  || grep -qsE '(docker|kubepods|containerd|libpod)' /proc/1/cgroup 2>/dev/null; then
  in_container=1
elif command -v systemd-detect-virt >/dev/null 2>&1 \
  && systemd-detect-virt --container --quiet 2>/dev/null; then
  in_container=1
fi
docker_ok=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker_ok=1
elif [[ "${in_container}" == 1 ]]; then
  refuse V_MACHINE_TYPE "this is a container (a pod) with no Docker daemon of its own; validators rebuild miner models in isolated Docker workers." "use a VM or bare-metal host you control, not a container-only pod."
elif command -v docker >/dev/null 2>&1; then
  refuse V_DOCKER "Docker is installed but its daemon is not reachable by this user." "start Docker, or add yourself to the docker group and log in again."
else
  refuse V_TOOL "docker is not installed." "install Docker Engine from your OS packages and start it."
fi
if [[ "${docker_ok}" == 1 ]]; then
  cgroup="$(docker info --format '{{.CgroupVersion}}' 2>/dev/null || true)"
  [[ "${cgroup}" == "2" ]] || refuse V_CGROUP "Docker reports cgroup version '${cgroup:-unknown}'; cgroup v2 is required." "boot the host with unified cgroup v2 (a current Ubuntu has it by default)."
fi

cpus="$(nproc 2>/dev/null || echo 0)"
(( cpus >= MIN_CPUS )) || refuse V_CPU "${cpus} CPUs; at least ${MIN_CPUS} are required for one isolated worker." "use a machine with more CPUs."
ram_gib="$(awk '/^MemTotal:/ { printf "%d", $2 / 1048576 }' /proc/meminfo 2>/dev/null || echo 0)"
(( ram_gib >= MIN_RAM_GIB )) || refuse V_RAM "${ram_gib} GiB of RAM; at least ${MIN_RAM_GIB} GiB are required for one isolated worker." "use a machine with more memory."

probe="${STATE_DIR}"
while [[ ! -d "${probe}" && "${probe}" != "/" ]]; do probe="$(dirname -- "${probe}")"; done
free_gib="$(df -Pk -- "${probe}" 2>/dev/null | awk 'NR==2 { printf "%d", $4 / 1048576 }' || echo 0)"
(( free_gib >= MIN_FREE_GIB )) || refuse V_DISK "${free_gib} GiB free where Carbon installs (${probe}); at least ${MIN_FREE_GIB} GiB are required." "free disk space or set CARBON_STATE_DIR on a larger disk."

if command -v curl >/dev/null 2>&1; then
  hosts=(https://github.com https://pypi.org https://ghcr.io)
  [[ "${gpu}" == 1 ]] && hosts+=(https://download.pytorch.org)
  for url in "${hosts[@]}"; do
    curl -sS -I --max-time 15 -o /dev/null -- "${url}" 2>/dev/null \
      || refuse V_NETWORK "cannot reach ${url} over HTTPS." "allow outbound HTTPS to GitHub, PyPI, ghcr.io (and download.pytorch.org for GPU)."
  done
fi

if [[ "${gpu}" == 1 ]]; then
  driver=""
  command -v nvidia-smi >/dev/null 2>&1 && driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n 1 || true)"
  major="${driver%%.*}"
  if [[ ! "${major}" =~ ^[0-9]+$ ]]; then
    refuse V_GPU_DRIVER "no NVIDIA driver answered nvidia-smi." "install the NVIDIA driver ${MIN_NVIDIA_DRIVER_MAJOR} or later on the host."
  elif (( major < MIN_NVIDIA_DRIVER_MAJOR )); then
    refuse V_GPU_DRIVER "NVIDIA driver ${driver} is older than ${MIN_NVIDIA_DRIVER_MAJOR} (CUDA 13)." "upgrade the NVIDIA driver."
  fi
  # Advisory only: a CDI-mode toolkit registers no runtime. The functional check
  # (the GPU visible from the installed worker image) is step 3 and decides.
  if [[ "${docker_ok}" == 1 ]] \
    && ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q nvidia \
    && ! compgen -G "/etc/cdi/*nvidia*" >/dev/null \
    && ! compgen -G "/var/run/cdi/*nvidia*" >/dev/null; then
    printf 'Note: no NVIDIA runtime or CDI spec seen; the GPU check after the install decides.\n' >&2
  fi
fi

if (( ${#failures[@]} > 0 )); then
  printf '\nCarbon validator install stopped: this machine does not meet the requirements.\n' >&2
  for line in "${failures[@]}"; do printf '  - %s\n' "${line}" >&2; done
  exit 2
fi
printf 'This machine meets the requirements.\n'
[[ "${check_only}" == 0 ]] || exit 0

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

step "2/3 Installing the environment and worker images (scripts/install_miner.sh)"
"${repo_root}/scripts/install_miner.sh" --pytorch --no-start "${pass[@]}"

step "3/3 Checking the installed images"
cd "${repo_root}"
ids="$(.venv/bin/python -B - "${STATE_DIR}" <<'PY'
import json, sys
from pathlib import Path
from carbon.development_session.research_image import load_analysis_image
from carbon.reconstruction.worker.docker_runtime import load_image_identity

recorded = json.loads((Path(sys.argv[1]) / "installed-images.json").read_bytes())
worker = load_image_identity(Path(recorded["image_manifest"]))
analysis = load_analysis_image(Path(recorded["analysis_image_manifest"]))
print(worker.image_id)
print(analysis.image_id)
PY
)" || { printf 'Carbon validator install stopped: the recorded images could not be read from %s/installed-images.json.\n' "${STATE_DIR}" >&2; exit 3; }
while IFS= read -r image; do
  docker image inspect "${image}" >/dev/null 2>&1 \
    || { printf 'Carbon validator install stopped: Docker does not hold the recorded image %s.\n' "${image}" >&2; exit 3; }
done <<< "${ids}"
if [[ "${gpu}" == 1 ]]; then
  gpu_image="$(.venv/bin/python -B - "${STATE_DIR}" <<'PY'
import json, sys
from pathlib import Path
from carbon.reconstruction.worker.docker_runtime import load_image_identity

recorded = json.loads((Path(sys.argv[1]) / "installed-images.json").read_bytes())
print(load_image_identity(Path(recorded["gpu_image_manifest"])).image_id)
PY
)" || { printf 'Carbon validator install stopped: V_GPU_IMAGE: no GPU worker image is recorded in %s/installed-images.json. Next: run this again with --gpu on this machine.\n' "${STATE_DIR}" >&2; exit 3; }
  docker run --rm --gpus all --entrypoint /bin/sh "${gpu_image}" -c 'test -e /dev/nvidiactl' >/dev/null 2>&1 \
    || { printf 'Carbon validator install stopped: V_GPU_VISIBLE: the GPU is not visible from the installed worker image. Next: install or configure the NVIDIA Container Toolkit (runtime or CDI) and restart Docker.\n' >&2; exit 3; }
fi
printf '\nValidator host ready: worker and analysis images present (state: %s).\n' "${STATE_DIR}"
printf 'Not done here: receiver configuration, start, answer-key sync and weights (the operator route).\n'
