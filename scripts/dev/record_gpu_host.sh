#!/usr/bin/env bash
# Record what this machine says about its GPU and Docker, for Carbon's any-GPU
# host tests (tests/fixtures/gpu_hosts/<name>/). READ-ONLY: it runs only
# `nvidia-smi` queries, `docker version/info` and `uname`; it writes no key, no
# hostname, no GPU serial, and replaces each GPU uuid with a stable token of the
# same shape. Run it on every GPU host you rent or own and send the folder:
#
#   scripts/dev/record_gpu_host.sh OUT_DIR HOST_NAME
#
# HOST_NAME is a short label such as rtx4090x4-baremetal-docker29.
set -u
out="${1:?usage: record_gpu_host.sh OUT_DIR HOST_NAME}"
name="${2:?usage: record_gpu_host.sh OUT_DIR HOST_NAME}"
case "${name}" in *[!A-Za-z0-9_.-]*) echo "HOST_NAME: letters, digits, . _ - only" >&2; exit 2 ;; esac
dir="${out}/${name}"
mkdir -p "${dir}"

# GPU-8hex-4hex-4hex-4hex-12hex from the hash of the real uuid (a MIG- prefix is kept).
redact() {
  local line prefix uuid h
  while IFS= read -r line; do
    while [[ "${line}" =~ (GPU|MIG)-[0-9a-fA-F-]{20,} ]]; do
      uuid="${BASH_REMATCH[0]}"; prefix="${uuid%%-*}"
      h="$(printf '%s' "${uuid}" | sha256sum | cut -c1-32)"
      line="${line//${uuid}/${prefix}-${h:0:8}-${h:8:4}-${h:12:4}-${h:16:4}-${h:20:12}}"
    done
    printf '%s\n' "${line}"
  done
}

query="uuid,name,driver_version,driver_model.current,compute_cap,memory.total,display_active"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu="${query}" --format=csv,noheader,nounits 2>&1 | redact > "${dir}/nvidia-smi-query.csv"
  echo "${PIPESTATUS[0]}" > "${dir}/nvidia-smi-exit.txt"
  nvidia-smi -L 2>&1 | redact > "${dir}/nvidia-smi-L.txt"
fi
if command -v docker >/dev/null 2>&1; then
  { printf '{"Version": "%s", "ApiVersion": "%s"}\n' \
      "$(docker version --format '{{.Server.Version}}' 2>/dev/null)" \
      "$(docker version --format '{{.Server.APIVersion}}' 2>/dev/null)"; } > "${dir}/docker-version.json"
  docker info --format '{{json .}}' 2>/dev/null | python3 -c '
import json, sys
try:
    info = json.load(sys.stdin)
except ValueError:
    info = {}
keep = ("ServerVersion", "OperatingSystem", "Runtimes", "SecurityOptions", "CgroupVersion", "CgroupDriver", "NCPU", "MemTotal", "Driver", "DriverStatus")
print(json.dumps({k: info[k] for k in keep if k in info}, sort_keys=True))
' > "${dir}/docker-info.json" 2>/dev/null || true
fi
vendors="$(lspci -nn 2>/dev/null | grep -Ei 'vga|3d|display' | grep -Eio '\[(10de|1002|8086):' | tr -d '[:' | sort -u | paste -sd, -)"
printf '{"nvidia_smi": %s, "rocm_smi": %s, "uname_s": "%s", "uname_m": "%s", "lspci_gpu_vendor_ids": "%s"}\n' \
  "$(command -v nvidia-smi >/dev/null 2>&1 && echo true || echo false)" \
  "$(command -v rocm-smi >/dev/null 2>&1 && echo true || echo false)" \
  "$(uname -s)" "$(uname -m)" "${vendors}" > "${dir}/vendor-probe.json"
printf '{"name": "%s", "provenance": "recorded", "recorded_at_utc": "%s"}\n' "${name}" "$(date -u +%FT%TZ)" > "${dir}/meta.json"
echo "recorded ${dir}"
