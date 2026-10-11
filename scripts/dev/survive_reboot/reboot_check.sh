#!/usr/bin/env bash
# After a reboot: are this machine's test signers, validator tunnel and
# Control Centers back (SURVIVE-REBOOT-01)? Prints only what this user runs.
# Read-only.
set -uo pipefail

echo "== $(hostname) / $(id -un)  linger=$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null)"

units() {
  systemctl --user list-units "$1" --all --no-pager --plain --no-legend 2>/dev/null \
    | awk '{printf "  %-55s %s %s\n", $1, $3, $4}'
}

signers="$(units 'carbon-test-signer@*')"
if [[ -n "${signers}" ]]; then
  echo "signers:"; echo "${signers}"
fi

tunnel="$(units 'carbon-validator-tunnel.service')"
if [[ -n "${tunnel}" ]]; then
  echo "tunnel:"; echo "${tunnel}"
fi
if [[ -n "${tunnel}" || -n "${signers}" ]]; then
  for port in 18467 18468 18469; do
    if (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
      echo "  port ${port}: open"
    else
      echo "  port ${port}: CLOSED"
    fi
  done
fi

centers="$(units 'carbon-control-center*')"
if [[ -n "${centers}" ]]; then
  echo "control centers:"; echo "${centers}"
fi
