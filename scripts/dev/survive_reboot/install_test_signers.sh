#!/usr/bin/env bash
# Run the testnet-567 test signers as systemd user units that restart on
# their own after a reboot (SURVIVE-REBOOT-01). Owner decision 2026-10-10:
# "Yes. Fix this system".
#
#   install_test_signers.sh LANES_FILE --receiver SS58 [--receiver SS58 ...]
#
# LANES_FILE has one `lane wallet hotkey` line per signer (public values only;
# `#` starts a comment). A hotkey that is not on the owner's auto-confirm
# allow-list is refused, so a manual signer (one the owner confirms at the
# terminal) never becomes a unit. Each lane's tmux window of the same name in
# the `signers` session is closed before its unit starts, so the two never
# hold the same signer socket. No key or password is read or written here:
# the unit names a wallet, and the signer opens it.
set -euo pipefail

fail() { echo "install_test_signers: $*" >&2; exit 1; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lanes_file="${1:-}"
[[ -n "${lanes_file}" && -f "${lanes_file}" ]] || fail "usage: $0 LANES_FILE --receiver SS58 [...]"
shift
ss58='^5[1-9A-HJ-NP-Za-km-z]{47}$'
receivers=()
while (($#)); do
  case "$1" in
    --receiver)
      [[ "${2:-}" =~ ${ss58} ]] || fail "not an ss58 receiver: ${2:-}"
      receivers+=("--receiver" "$2")
      shift 2
      ;;
    *) fail "unknown argument $1" ;;
  esac
done
((${#receivers[@]})) || fail "name at least one --receiver"

allow="${HOME}/.config/carbon/autoconfirm-allowlist.json"
[[ -f "${allow}" ]] || fail "no auto-confirm allow-list at ${allow}"
allowed="$(python3 - "${allow}" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1]))
ok = (doc.get("schema") == "carbon.signer.autoconfirm-allowlist.v1"
      and doc.get("network") == "testnet" and doc.get("netuid") == 567)
print(" ".join(doc.get("hotkeys", [])) if ok else "")
PY
)"
[[ -n "${allowed}" ]] || fail "the allow-list is not a testnet-567 auto-confirm list"

env_dir="${HOME}/.config/carbon/test-signers"
unit_dir="${HOME}/.config/systemd/user"
lanes=()
while read -r lane wallet hotkey rest; do
  [[ -z "${lane}" || "${lane}" == \#* ]] && continue
  [[ -z "${rest}" ]] || fail "${lane}: expected 'lane wallet hotkey'"
  [[ "${lane}" =~ ^[A-Za-z0-9_-]+$ ]] || fail "bad lane name ${lane}"
  [[ "${wallet}" =~ ^[A-Za-z0-9._-]+$ ]] || fail "${lane}: bad wallet name"
  [[ "${hotkey}" =~ ${ss58} ]] || fail "${lane}: bad hotkey"
  [[ " ${allowed} " == *" ${hotkey} "* ]] \
    || fail "${lane}: ${hotkey} is not on the auto-confirm allow-list; it stays a manual signer"
  lanes+=("${lane}:${wallet}:${hotkey}")
done < "${lanes_file}"
((${#lanes[@]})) || fail "no lanes in ${lanes_file}"

# Everything is checked before anything is written.
mkdir -p "${unit_dir}" "${HOME}/.local/bin"
(umask 077 && mkdir -p "${env_dir}")
install -m 644 "${here}/carbon-test-signer@.service" "${unit_dir}/"
install -m 755 "${here}/reboot_check.sh" "${HOME}/.local/bin/carbon-reboot-check"
for entry in "${lanes[@]}"; do
  IFS=: read -r lane wallet hotkey <<< "${entry}"
  (umask 077 && printf 'WALLET=%s\nHOTKEY=%s\nRECEIVERS=%s\n' \
    "${wallet}" "${hotkey}" "${receivers[*]}" > "${env_dir}/${lane}.env")
done
systemctl --user daemon-reload

for entry in "${lanes[@]}"; do
  lane="${entry%%:*}"
  if tmux has-session -t signers 2>/dev/null \
      && tmux list-windows -t signers -F '#W' | grep -qx "${lane}"; then
    tmux kill-window -t "signers:${lane}"
    echo "closed tmux signers:${lane}"
  fi
done
sleep 2
for entry in "${lanes[@]}"; do
  systemctl --user enable --now "carbon-test-signer@${entry%%:*}.service"
done
sleep 5
systemctl --user list-units 'carbon-test-signer@*' --no-pager --plain --no-legend
loginctl show-user "$(id -un)" -p Linger
