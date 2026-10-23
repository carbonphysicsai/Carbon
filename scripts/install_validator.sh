#!/usr/bin/env bash
# One command from a clean Linux machine to a validator host that is ready to
# rebuild and judge miner models (DEVELOPMENT).
#
#   git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
#   ~/carbon/scripts/install_validator.sh              # add --gpu for GPU rebuilds
#   ~/carbon/scripts/install_validator.sh --check-only # only the machine checks
#   ~/carbon/scripts/install_validator.sh --setup --hotkey SS58  # the whole validator
#   ~/carbon/scripts/install_validator.sh --status     # is it working?
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
# Exit 0 means the host and its images are ready. With --setup it then sets up
# the validator (carbon.challenge_validator.validator_host): one receiver per
# Challenge (each Challenge's current version unless --challenges names others),
# received under your own validator hotkey (--hotkey, its public ss58 address),
# each a systemd user service that keeps running and starts again after a
# reboot; with --domain also the HTTPS proxy configuration and the endpoint
# entries miners' Launchpad lists. --status reports every receiver. With
# --receiver ID VERSION it prepares one receiver only (and with
# --start-receiver starts it). It does not build an evaluation pack, sync answer
# keys or run weights. It never asks for or stores a key or password.
set -euo pipefail

# Draft requirement values (VALIDATOR_REQUIREMENTS_DRAFT_20261019.md); a published
# sheet replaces them. Override only for tests.
# Free disk: V1 measured about 6 GB used by a CPU install (three images); the default is that
# plus headroom (the GPU worker adds about 12 GiB by the installer's own estimate, unmeasured here).
MIN_FREE_GIB_CPU=20
MIN_FREE_GIB_GPU=32
MIN_CPUS="${CARBON_VALIDATOR_MIN_CPUS:-2}"
MIN_RAM_GIB="${CARBON_VALIDATOR_MIN_RAM_GIB:-4}"
MIN_NVIDIA_DRIVER_MAJOR="${CARBON_VALIDATOR_MIN_NVIDIA_DRIVER_MAJOR:-580}"
STATE_DIR="${CARBON_STATE_DIR:-${HOME}/.carbon/development-launchpad}"
# The one registered validator host class (OWNER-VALIDATOR-HOST-CLASS-01): every validator runs the
# same hardware. The two overrides below, and CARBON_VALIDATOR_ASSUME_MACHINE, are test knobs: with
# any of them set the script only runs the checks (--check-only) and never installs.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST_CLASS_FILE="${CARBON_VALIDATOR_HOST_CLASS_FILE:-${SCRIPT_DIR}/../carbon/challenge_validator/validator-host-class.json}"
MEMINFO_FILE="${CARBON_VALIDATOR_MEMINFO_FILE:-/proc/meminfo}"

usage() {
  cat <<'EOF'
usage: scripts/install_validator.sh [--check-only] [--gpu]
                                    [--setup [--hotkey SS58] [--challenges LIST]
                                     [--exam-source FILE | --packs DIR] [--domain NAME]]
                                    [--receiver ID VERSION --hotkey SS58
                                     [--pack DIR] [--start-receiver]]
                                    [install_miner.sh options]
       scripts/install_validator.sh --status

  --check-only  run the machine checks and stop
  --setup       after the install, set up the validator: one receiver service
                per Challenge, under your validator hotkey
  --hotkey SS58 your validator hotkey's public ss58 address (asked for when
                missing and this is a terminal); it must hold a validator
                permit on the subnet
  --challenges LIST
                with --setup: current (each Challenge's newest version, the
                default), all, or ID@VERSION,ID@VERSION,...
  --exam-source FILE
                with --setup: where Carbon's signed exams come from (its
                distribution URL and receiver hotkey); each receiver gets this
                hotkey's own copy, verified against the producer key pinned in
                this Carbon release
  --packs DIR   with --setup, on a --development-candidate install only: a
                directory of built evaluation packs, one per ID-VERSION
  --domain NAME with --setup: the public DNS name of this host; writes the
                HTTPS proxy (Caddy) configuration and the endpoint entries
  --status      report every receiver: service, intake, exam, last graded
  --receiver ID VERSION
                after the install, write the receiver's profile and configuration
                for that registered Challenge
                (carbon.challenge_validator.receiver_setup)
  --pack DIR    with --receiver: the built evaluation pack directory to select
  --start-receiver
                with --receiver: start the receiver as a user systemd unit
  --gpu         also require and build the GPU worker (NVIDIA driver 580 or
                later and the NVIDIA Container Toolkit)

Other options (--release TAG, --ref REF, --development-candidate ..., --port)
are passed to scripts/install_miner.sh, which always runs with --pytorch
--no-start here.
EOF
}

check_only=0
gpu=0
receiver_id=""
receiver_version=""
receiver_pack=""
receiver_start=0
setup=0
status=0
hotkey=""
challenges="current"
packs=""
exam_source=""
domain=""
pass=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) check_only=1 ;;
    --gpu) gpu=1; pass+=("$1") ;;
    -h|--help) usage; exit 0 ;;
    --development-candidate) pass+=("$1" "${2:-}" "${3:-}" "${4:-}"); shift 3 ;;
    --ref|--release|--port) pass+=("$1" "${2:-}"); shift ;;
    --receiver) receiver_id="${2:?--receiver needs ID VERSION}"; receiver_version="${3:?--receiver needs ID VERSION}"; shift 2 ;;
    --pack) receiver_pack="${2:?--pack needs a directory}"; shift ;;
    --start-receiver) receiver_start=1 ;;
    --setup) setup=1 ;;
    --status) status=1 ;;
    --hotkey) hotkey="${2:?--hotkey needs an ss58 address}"; shift ;;
    --challenges) challenges="${2:?--challenges needs a list}"; shift ;;
    --packs) packs="${2:?--packs needs a directory}"; shift ;;
    --exam-source) exam_source="${2:?--exam-source needs a file}"; shift ;;
    --domain) domain="${2:?--domain needs a DNS name}"; shift ;;
    --pytorch|--no-start) ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${status}" == 1 ]]; then
  # Read-only: no machine check and no install.
  cd "${repo_root}"
  exec .venv/bin/python -B -m carbon.challenge_validator.validator_host status \
    --installed-state "$(realpath -m -- "${STATE_DIR}")"
fi
if [[ "${setup}" == 1 && -n "${receiver_id}" ]]; then
  printf 'Carbon validator install stopped: use --setup (every Challenge) or --receiver ID VERSION (one), not both.\n' >&2
  exit 2
fi
if [[ "${setup}" == 0 && ( -n "${packs}" || -n "${exam_source}" || -n "${domain}" || "${challenges}" != current ) ]]; then
  printf 'Carbon validator install stopped: --challenges, --exam-source, --packs and --domain go with --setup.\n' >&2
  exit 2
fi
if [[ ( "${setup}" == 1 || -n "${receiver_id}" ) && -z "${hotkey}" && "${check_only}" == 0 ]]; then
  if [[ -t 0 ]]; then
    read -r -p "Your validator hotkey's ss58 address (public, not a key): " hotkey
  fi
  if [[ -z "${hotkey}" ]]; then
    printf 'Carbon validator install stopped: --hotkey SS58 is required (your validator hotkey'"'"'s public address; it must hold a validator permit on the subnet).\n' >&2
    exit 2
  fi
fi
if [[ -z "${receiver_id}" && ( "${receiver_start}" == 1 || -n "${receiver_pack}" ) ]]; then
  printf 'Carbon validator install stopped: --start-receiver and --pack need --receiver ID VERSION (the receiver is prepared first, then started).\n' >&2
  exit 2
fi

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
# Test knob only: fixes the machine type so the checks do not depend on where they run.
case "${CARBON_VALIDATOR_ASSUME_MACHINE:-}" in
  host) in_container=0 ;;
  container) in_container=1 ;;
esac
if [[ -n "${CARBON_VALIDATOR_ASSUME_MACHINE:-}" ]]; then
  # Never silent: a stale variable would otherwise skip the machine-type refusal unseen.
  printf 'Note: CARBON_VALIDATOR_ASSUME_MACHINE=%s overrides the machine-type check (tests only).\n' "${CARBON_VALIDATOR_ASSUME_MACHINE}" >&2
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

# One host class (OWNER-VALIDATOR-HOST-CLASS-01): the CPU model name and ISA flags and the vCPU
# count must equal the registered class and the memory must reach its minimum, or nothing is
# installed. The class is measured on the calibration host and registered in
# carbon/challenge_validator/validator-host-class.json; an unmeasured file refuses everything.
if command -v python3 >/dev/null 2>&1; then
  while IFS=$'\t' read -r code message next; do
    if [[ -n "${code}" ]]; then refuse "${code}" "${message}" "${next}"; fi
  done < <(python3 - "${HOST_CLASS_FILE}" "${MEMINFO_FILE}" <<'PY'
import json
import os
import re
import subprocess
import sys

FLAGS = ("avx2", "fma", "avx512f", "avx512_bf16", "amx")
SCHEMA = "carbon.validator.host-class.v1"
path, meminfo = sys.argv[1], sys.argv[2]


def refuse(code, message, nxt):
    print("\t".join((code, message, nxt)))


def run(*command):
    done = subprocess.run(command, capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"}, check=False)
    return done.stdout


try:
    with open(path, encoding="utf-8") as stream:
        registered = json.load(stream)
    flags = registered["isa_flags_present"]
    if (
        registered["schema"] != SCHEMA
        or registered["scope"] not in ("DEVELOPMENT", "MAINNET")
        or type(registered["cpu_model_name"]) is not str
        or not registered["cpu_model_name"]
        or set(flags) != set(FLAGS)
        or any(type(flags[name]) is not bool for name in FLAGS)
        or type(registered["nproc"]) is not int
        or registered["nproc"] < 1
        or type(registered["mem_total_min_gib"]) is not int
        or registered["mem_total_min_gib"] < 1
    ):
        raise ValueError("malformed")
except (OSError, ValueError, KeyError, TypeError):
    refuse(
        "V_HOST_CLASS_UNREGISTERED",
        "no measured validator host class is registered (" + path + ").",
        "register carbon/challenge_validator/validator-host-class.json from the calibration host before installing.",
    )
    sys.exit(0)

lscpu = run("lscpu")
model = next(
    (m.group(1).strip() for m in re.finditer(r"^Model name:\s*(.*)$", lscpu, re.M)), ""
)
present = set(
    next((m.group(1).split() for m in re.finditer(r"^Flags:\s*(.*)$", lscpu, re.M)), [])
)
seen = {name: name in present for name in FLAGS if name != "amx"}
seen["amx"] = any(flag.startswith("amx_") for flag in present)
try:
    cpus = int(run("nproc").strip())
except ValueError:
    cpus = 0
try:
    with open(meminfo, encoding="ascii") as stream:
        kib = int(re.search(r"^MemTotal:\s+(\d+) kB", stream.read(), re.M).group(1))
except (OSError, AttributeError, ValueError):
    kib = 0
mem_gib = kib // 1048576

if model != registered["cpu_model_name"]:
    refuse(
        "V_HOST_CLASS_MODEL",
        "this CPU is '" + (model or "unknown") + "'; the validator host class is '" + registered["cpu_model_name"] + "'.",
        "use the registered validator hardware.",
    )
if seen != flags:
    refuse(
        "V_HOST_CLASS_ISA",
        "CPU flags " + json.dumps(seen, sort_keys=True) + " differ from the host class " + json.dumps(flags, sort_keys=True) + ".",
        "use the registered validator hardware.",
    )
if cpus != registered["nproc"]:
    refuse(
        "V_HOST_CLASS_VCPU",
        str(cpus) + " vCPUs; the validator host class has exactly " + str(registered["nproc"]) + ".",
        "use a machine with exactly the registered vCPU count.",
    )
if mem_gib < registered["mem_total_min_gib"]:
    refuse(
        "V_HOST_CLASS_MEMORY",
        str(mem_gib) + " GiB of memory; the validator host class needs at least " + str(registered["mem_total_min_gib"]) + " GiB.",
        "use a machine with the registered memory.",
    )
PY
)
else
  refuse V_TOOL "python3 is not installed." "install python3 from your OS packages."
fi

# The test knobs can only produce a check result, never an install: a validator cannot use them to
# pass as another host class.
overrides=()
for knob in CARBON_VALIDATOR_ASSUME_MACHINE CARBON_VALIDATOR_HOST_CLASS_FILE CARBON_VALIDATOR_MEMINFO_FILE; do
  if [[ -n "${!knob:-}" ]]; then overrides+=("${knob}"); fi
done
if (( ${#overrides[@]} > 0 && check_only == 0 )); then
  refuse V_TEST_OVERRIDE "${overrides[*]} set; these are test knobs and never allowed for an install." "unset them and run again on the registered validator host."
fi

MIN_FREE_GIB="${CARBON_VALIDATOR_MIN_FREE_GIB:-$(( gpu == 1 ? MIN_FREE_GIB_GPU : MIN_FREE_GIB_CPU ))}"
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
if [[ -n "${receiver_id}" ]]; then
  step "Receiver profile and configuration"
  receiver_state="${STATE_DIR}/receiver-${receiver_id}"
  setup_args=(prepare --installed-state "$(realpath -- "${STATE_DIR}")"
              --receiver-state "$(realpath -m -- "${receiver_state}")"
              --hotkey "${hotkey}" --challenge "${receiver_id}" "${receiver_version}")
  [[ -z "${receiver_pack}" ]] || setup_args+=(--pack "$(realpath -- "${receiver_pack}")")
  .venv/bin/python -B -m carbon.challenge_validator.receiver_setup "${setup_args[@]}" \
    || { printf 'Carbon validator install stopped: the receiver setup was refused (see above).\n' >&2; exit 4; }
  if [[ "${receiver_start}" == 1 ]]; then
    .venv/bin/python -B -m carbon.challenge_validator.receiver_setup start \
      --receiver-state "$(realpath -m -- "${receiver_state}")" --detach \
      || { printf 'Carbon validator install stopped: the receiver did not start.\n' >&2; exit 4; }
  else
    printf 'Receiver prepared, not started. Start it: .venv/bin/python -B -m carbon.challenge_validator.receiver_setup start --receiver-state %s --detach\n' "${receiver_state}"
  fi
elif [[ "${setup}" == 1 ]]; then
  step "Validator receivers (one service per Challenge)"
  host_args=(setup --installed-state "$(realpath -- "${STATE_DIR}")"
             --hotkey "${hotkey}" --challenges "${challenges}")
  [[ -z "${packs}" ]] || host_args+=(--packs "$(realpath -- "${packs}")")
  [[ -z "${exam_source}" ]] || host_args+=(--exam-source "$(realpath -- "${exam_source}")")
  [[ -z "${domain}" ]] || host_args+=(--domain "${domain}")
  .venv/bin/python -B -m carbon.challenge_validator.validator_host "${host_args[@]}" \
    || { printf 'Carbon validator install stopped: the validator setup was refused (see above).\n' >&2; exit 4; }
  printf 'Check it is working: %s/scripts/install_validator.sh --status\n' "${repo_root}"
else
  printf 'Not done here: the validator receivers (pass --setup --hotkey SS58), answer-key sync and weights.\n'
fi
