#!/usr/bin/env bash
# One command from a clean Linux machine to the Carbon Control Center (C-MLP-04).
#
#   git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
#   ~/carbon/scripts/install_miner.sh            # add --gpu for GPU practice
#
# What it does, in order, and nothing else:
#   1. checks this machine: Linux x86-64, git, curl and a running Docker;
#   2. brings the checkout to the requested ref (main by default);
#   3. installs the pinned uv if missing and syncs Carbon's locked
#      environment (scripts/dev/bootstrap.sh) with the science, chain and MCP
#      groups;
#   4. builds the pinned worker and analysis images on this machine, and with
#      --gpu the GPU worker; Carbon publishes no image registry;
#   5. records where those images are, owner-only, for setup to fill in;
#   6. starts the Control Center on 127.0.0.1 and prints its address and
#      session token.
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

usage() {
  cat <<'EOF'
usage: scripts/install_miner.sh [--gpu] [--ref REF] [--no-start] [--port PORT]

  --gpu        also build the GPU worker (needs an NVIDIA GPU and the
               NVIDIA Container Toolkit)
  --ref REF    the Carbon ref to install (default: main, or $CARBON_REF)
  --no-start   build everything, but do not start the Control Center
  --port PORT  the Control Center's local port (default 8788)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpu) GPU=1 ;;
    --ref) REF="${2:?--ref needs a value}"; shift ;;
    --no-start) START=0 ;;
    --port) PORT="${2:?--port needs a value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'Carbon install stopped: %s\n' "$*" >&2; exit 2; }

step "1/6 Checking this machine"
[[ "$(uname -s)" == "Linux" ]] || fail "Linux is required (Windows: use WSL2)."
[[ "$(uname -m)" == "x86_64" ]] || fail "x86-64 is required."
for tool in git curl docker; do
  command -v "${tool}" >/dev/null 2>&1 || fail "${tool} is not installed."
done
docker info >/dev/null 2>&1 \
  || fail "Docker is installed but not reachable; start it, or add yourself to the docker group."
if [[ "${GPU}" == 1 ]]; then
  command -v nvidia-smi >/dev/null 2>&1 \
    || fail "--gpu needs the NVIDIA driver (nvidia-smi was not found)."
fi
echo "Linux x86-64, git, curl and Docker: ready."

step "2/6 Bringing Carbon to ${REF}"
repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
git -C "${repo_root}" rev-parse --show-toplevel >/dev/null 2>&1 \
  || fail "run this script from a Carbon checkout (git clone first)."
cd "${repo_root}"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Local changes found: keeping the checkout as it is."
else
  git fetch --quiet origin "${REF}"
  git checkout --quiet --detach FETCH_HEAD
fi
echo "Carbon at $(git rev-parse --short HEAD)."

step "3/6 Installing Carbon's locked environment"
export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1 || [[ "$(uv --version | awk '{print $2}')" != "${UV_VERSION}" ]]; then
  echo "Installing uv ${UV_VERSION} (Astral's installer) into ~/.local/bin."
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
fi
CARBON_UV_GROUPS="science-jax chain mcp" ./scripts/dev/bootstrap.sh
python="${repo_root}/.venv/bin/python"

step "4/6 Building the pinned images on this machine"
artifacts="${repo_root}/.carbon-artifacts"
./scripts/dev/c03_worker_image.sh "${artifacts}/c03-worker-image.json"
analysis="$(
  "${python}" -m carbon.development_session.research_image \
    --parent-manifest "${artifacts}/c03-worker-image.json" \
    --root "${artifacts}/research-images" \
  | "${python}" -c 'import json, sys; print(json.load(sys.stdin)["manifest"])'
)"
gpu_manifest=""
if [[ "${GPU}" == 1 ]]; then
  ./scripts/dev/accelerator_worker_image.sh "${artifacts}/accelerator-worker-image.json"
  gpu_manifest="${artifacts}/accelerator-worker-image.json"
fi

step "5/6 Recording the images for setup"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"
"${python}" -m scripts.dev.miner_launchpad.installed write \
  --state-dir "${STATE_DIR}" \
  --image-manifest "${artifacts}/c03-worker-image.json" \
  --analysis-image-manifest "${analysis}" \
  ${gpu_manifest:+--gpu-image-manifest "${gpu_manifest}"}

cat <<EOF

Next, in a terminal of your own (Carbon never holds your key):
  ${repo_root}/.venv/bin/carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>

Then, in the Control Center:
  - Wallet & Identity: confirm your hotkey is registered on subnet 567
    (it prepares the unsigned call if not; you sign it in your own wallet).
  - Set up your environment: inference, compute and agent; the image paths
    are filled in for you.
  - Challenges: choose what to mine, then launch.
EOF

if [[ "${START}" == 0 ]]; then
  echo
  echo "Start it later with:"
  echo "  ${python} ${repo_root}/scripts/dev/miner_launchpad/controller.py --state-dir ${STATE_DIR} --port ${PORT}"
  exit 0
fi

step "6/6 Starting the Control Center"
exec "${python}" "${repo_root}/scripts/dev/miner_launchpad/controller.py" \
  --state-dir "${STATE_DIR}" --port "${PORT}"
