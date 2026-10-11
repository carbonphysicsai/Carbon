#!/usr/bin/env bash
# Run INCENTIVE-CANARY-01 role miners' runner cycles as systemd user timers
# that come back after a reboot. The owner approved this on 2026-10-10.
#
#   install_incentive_runners.sh LANE [LANE ...]
#
# Each lane needs an owner-only runner config at
# ~/.carbon/incentive-runner/<lane>/config.json. The config is not checked
# here: the runner checks it on every cycle and refuses anything else. A
# transient `incentive-<lane>` timer from an earlier systemd-run is stopped
# first, so a lane never has two schedules.
#
# Before moving the shared checkout, stop these timers:
#   systemctl --user stop 'incentive-runner@*.timer'
# A cycle frozen under the old revision is refused campaign_frozen_on_old_revision
# (LA-F19).
set -euo pipefail

fail() { echo "install_incentive_runners: $*" >&2; exit 1; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
(($#)) || fail "usage: $0 LANE [LANE ...]"
for lane in "$@"; do
  [[ "${lane}" =~ ^[A-Za-z0-9_-]+$ ]] || fail "bad lane name ${lane}"
  config="${HOME}/.carbon/incentive-runner/${lane}/config.json"
  [[ -f "${config}" && ! -L "${config}" ]] || fail "${lane}: no runner config at ${config}"
  [[ "$(stat -c '%a' "${config}")" == 600 ]] || fail "${lane}: ${config} must be mode 600"
done

unit_dir="${HOME}/.config/systemd/user"
mkdir -p "${unit_dir}" "${HOME}/.local/bin"
install -m 644 "${here}/incentive-runner@.service" "${here}/incentive-runner@.timer" "${unit_dir}/"
install -m 755 "${here}/reboot_check.sh" "${HOME}/.local/bin/carbon-reboot-check"
systemctl --user daemon-reload

for lane in "$@"; do
  systemctl --user stop "incentive-${lane}.timer" "incentive-${lane}.service" 2>/dev/null || true
  systemctl --user reset-failed "incentive-${lane}.timer" "incentive-${lane}.service" 2>/dev/null || true
  systemctl --user enable --now "incentive-runner@${lane}.timer"
done
systemctl --user list-timers 'incentive-runner@*' --no-pager
loginctl show-user "$(id -un)" -p Linger
