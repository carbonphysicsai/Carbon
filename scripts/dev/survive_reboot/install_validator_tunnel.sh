#!/usr/bin/env bash
# Run the operator's validator tunnel as a systemd user unit that restarts on
# its own after a reboot (SURVIVE-REBOOT-01), replacing the tmux `tunnel`
# session. Needs the pinned key and known-hosts already in
# ~/.config/carbon/ (hidden-tunnel.key, hidden-known-hosts); reads neither.
set -euo pipefail

fail() { echo "install_validator_tunnel: $*" >&2; exit 1; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${HOME}/.config/carbon"
[[ -f "${dir}/hidden-tunnel.key" && -f "${dir}/hidden-known-hosts" ]] \
  || fail "the tunnel key and known-hosts must already be in ${dir}"

unit_dir="${HOME}/.config/systemd/user"
mkdir -p "${unit_dir}" "${HOME}/.local/bin"
install -m 755 "${here}/validator_tunnel.sh" "${HOME}/.local/bin/carbon-validator-tunnel"
install -m 755 "${here}/reboot_check.sh" "${HOME}/.local/bin/carbon-reboot-check"
install -m 644 "${here}/carbon-validator-tunnel.service" "${unit_dir}/"
systemctl --user daemon-reload

# The tmux loop holds the forwarded ports; close it first.
if tmux has-session -t tunnel 2>/dev/null; then
  tmux kill-session -t tunnel
  echo "closed tmux tunnel"
  sleep 2
fi
systemctl --user enable --now carbon-validator-tunnel.service

if [[ "$(loginctl show-user "$(id -un)" -p Linger --value)" != "yes" ]]; then
  loginctl enable-linger "$(id -un)" 2>/dev/null \
    || echo "Linger is off. Turn it on once: sudo loginctl enable-linger $(id -un)"
fi
sleep 5
systemctl --user status carbon-validator-tunnel.service --no-pager --lines=0 | head -3
loginctl show-user "$(id -un)" -p Linger
