#!/bin/bash
# Operator environment for the reference-solvers program (OWNER-RUNPOD-SOLVER-READINESS-01).
# Idempotent. No secret is written to the repository or printed.
#
#   export RUNPOD_API_KEY=...            # the operator's own key (never commit it)
#   bash scripts/dev/reference_packages/operator_setup.sh [--cap-usd 25] [--floor-usd 15] [--no-docker]
#
# Sets up: Python env (uv), Docker with a Docker Hub mirror (local checks only),
# ~/.runpod/{api_key,campaigns.json} (mode 600), the reference-solvers campaign,
# a clean Python for ship checks (~/.carbon-cleanpy), then runs read-only checks.
set -euo pipefail
CAP=25; FLOOR=15; DOCKER=1; PHASE_ARGS=()
while [ $# -gt 0 ]; do case "$1" in
  --cap-usd) CAP=$2; shift 2;; --floor-usd) FLOOR=$2; shift 2;; --no-docker) DOCKER=0; shift;;
  --operator-phase) PHASE_ARGS=(--operator-phase "$2"); shift 2;;
  *) echo "unknown argument $1"; exit 2;; esac; done
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); cd "$ROOT"
say() { printf '\n== %s\n' "$*"; }

say "1/6 tools"
for t in git python3 curl; do command -v $t >/dev/null || { echo "missing $t"; exit 1; }; done
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uvx >/dev/null; then
  curl --fail --location --silent --show-error https://astral.sh/uv/0.12.7/install.sh \
    | env UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh
fi

say "2/6 python environment"
uvx --from 'uv==0.12.7' uv sync --frozen --group dev --group science-jax

if [ "$DOCKER" = 1 ]; then
  say "3/6 docker (local checks only; pods do not use Docker)"
  if ! command -v docker >/dev/null; then
    if command -v apt-get >/dev/null; then sudo apt-get update -qq && sudo apt-get install -y -qq docker.io; else echo "install Docker manually"; exit 1; fi
  fi
  if [ -w /etc/docker ] || sudo -n true 2>/dev/null; then
    sudo mkdir -p /etc/docker
    [ -f /etc/docker/daemon.json ] || echo '{"registry-mirrors": ["https://mirror.gcr.io"]}' | sudo tee /etc/docker/daemon.json >/dev/null
  fi
  if ! docker info >/dev/null 2>&1; then
    (sudo systemctl start docker 2>/dev/null) || (sudo nohup dockerd >/tmp/dockerd.log 2>&1 &)
    for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
  fi
  docker info >/dev/null 2>&1 && echo "docker ok" || echo "WARNING: docker not running (only needed for local checks)"
else
  say "3/6 docker skipped"
fi

say "4/6 RunPod operator config (~/.runpod, mode 600)"
[ -n "${RUNPOD_API_KEY:-}" ] || [ -s "$HOME/.runpod/api_key" ] || { echo "set RUNPOD_API_KEY first"; exit 1; }
mkdir -p "$HOME/.runpod"; chmod 700 "$HOME/.runpod"
( umask 077
  [ -n "${RUNPOD_API_KEY:-}" ] && printf '%s' "$RUNPOD_API_KEY" > "$HOME/.runpod/api_key"
  chmod 600 "$HOME/.runpod/api_key"
  python3 - "$CAP" "$FLOOR" <<'PY'
import json, pathlib, sys
p = pathlib.Path.home() / ".runpod/campaigns.json"
d = json.loads(p.read_text()) if p.exists() else {}
d.setdefault("ceilings_usd", {})["reference-solvers"] = float(sys.argv[1])
d["balance_floor_usd"] = max(float(d.get("balance_floor_usd", 0)), float(sys.argv[2]))
p.write_text(json.dumps(d) + "\n")
p.chmod(0o600)
PY
)
if ! .venv/bin/python -m scripts.dev.exam_design.runpod.pod_control --campaign reference-solvers "${PHASE_ARGS[@]}" start --cap-usd "$CAP"; then
  # An existing phase is resumed only if its complete accounting still validates.
  .venv/bin/python -m scripts.dev.exam_design.runpod.pod_control --campaign reference-solvers "${PHASE_ARGS[@]}" status
fi

say "5/6 clean python for ship checks (~/.carbon-cleanpy)"
[ -x "$HOME/.carbon-cleanpy/bin/python" ] || { python3 -m venv "$HOME/.carbon-cleanpy" && "$HOME/.carbon-cleanpy/bin/pip" install -q numpy scipy; }

say "6/6 read-only checks"
.venv/bin/python - <<'PY'
import json, urllib.request, pathlib
key = pathlib.Path.home().joinpath(".runpod/api_key").read_text().strip()
req = urllib.request.Request("https://api.runpod.io/graphql",
    data=json.dumps({"query": "query { myself { clientBalance pods { id name } } }"}).encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
m = json.load(urllib.request.urlopen(req, timeout=30))["data"]["myself"]
print(f"RunPod reachable: balance USD {m['clientBalance']:.2f}, live pods {len(m['pods'])}")
PY
.venv/bin/python -m pytest -q tests/cpu/test_reference_solvers_pods.py tests/cpu/test_bulk_run_native.py 2>&1 | tail -1
echo; echo "Operator environment ready. Runbook: docs/development/challenge_pipeline/solver-readiness/OPERATOR.md"
