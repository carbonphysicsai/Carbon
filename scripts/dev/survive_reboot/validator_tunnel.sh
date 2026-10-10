#!/usr/bin/env bash
# The ssh forward behind carbon-validator-tunnel.service (SURVIVE-REBOOT-01).
# Same forwards and options as the operator's tmux loop. The host is the
# first entry of the pinned known-hosts file, so no address is in the repo;
# StrictHostKeyChecking=yes and BatchMode=yes mean it never trusts a new host
# key and never prompts.
set -euo pipefail

dir="${HOME}/.config/carbon"
key="${dir}/hidden-tunnel.key"
known="${dir}/hidden-known-hosts"
host="$(awk 'NR==1{print $1}' "${known}")"
[[ -n "${host}" ]] || { echo "no host in ${known}" >&2; exit 1; }

exec ssh -N -i "${key}" \
  -o IdentitiesOnly=yes -o BatchMode=yes \
  -o UserKnownHostsFile="${known}" -o StrictHostKeyChecking=yes \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -L 127.0.0.1:18468:127.0.0.1:8468 \
  -L 127.0.0.1:18467:127.0.0.1:8467 \
  -L 127.0.0.1:18469:127.0.0.1:8469 \
  "carbon-tunnel@${host}"
