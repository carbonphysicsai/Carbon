#!/usr/bin/env bash
# Disposable C0 integration. No public RPC, valuable network or treasury.
set -euo pipefail
cd "$(dirname "$0")/../.."
evidence="${1:-.carbon-artifacts/localnet}"
mkdir -p "$evidence"
evidence="$(cd "$evidence" && pwd)"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  echo 'Requires linux/amd64 with Docker and the locked Carbon development environment.' >&2
  exit 2
}
./scripts/dev/doctor.sh
docker info >/dev/null
image="$(.venv/bin/python -c 'import json; p=json.load(open("scripts/dev/localnet-runtime.json")); print(p["image"]+"@"+p["image_digest"])')"
name="carbon-localnet-${GITHUB_RUN_ID:-local}-$$"
network="$name-network"
cleanup() {
  docker logs "$name" >"$evidence/node.log" 2>&1 || true
  docker stop --time 35 "$name" >/dev/null 2>&1 || true
  docker rm "$name" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
docker pull --platform linux/amd64 "$image"
docker network create --internal --label carbon.scope=disposable-localnet "$network" >/dev/null
docker run --detach --name "$name" --platform linux/amd64 --network "$network" \
  --label carbon.scope=disposable-localnet --memory 5g --cpus 3 \
  -p 127.0.0.1::9944 -p 127.0.0.1::9945 "$image" True >"$evidence/container-id.txt"
export CARBON_LOCALNET_CONTAINER="$name" CARBON_LOCALNET_EVIDENCE="$evidence"
# The probe validates Docker isolation itself before constructing any key.
.venv/bin/python -m carbon.chain.localnet probe
# CPU fixture integration is a separate, explicit runtime invocation.
CARBON_REQUIRE_LOCALNET=1 .venv/bin/python -m pytest tests/cpu/test_net5_integration.py -q -s
