# MINER-SURVIVE-REBOOT-01 working contract

**Status:** DEVELOPMENT, authorized by the owner on 2026-10-10. Base: main at
branch start. One PR. Follows SURVIVE-REBOOT-01
(`scripts/dev/survive_reboot/`), which covered the operator's own test
machines; this ticket covers every miner's install.

**Owner, 2026-10-10:** a miner's setup comes back after a reboot by default:
"I just want easy and efficient and reliable". No new choice for the miner,
and no security trade-off.

## Scope

1. `scripts/install_miner.sh --service`: after it writes, enables and starts
   the Control Center's user unit, it makes sure the user lingers, so the
   unit starts at boot without a login. Linger already on is left alone; off
   is turned on with `loginctl enable-linger <user>` (no sudo needed on many
   systems, WSL included). When that is refused, it prints the exact
   `sudo loginctl enable-linger <user>` command and that the Control Center
   will not start after a reboot until it runs. It prints the final state,
   and on WSL a one-line note that Windows does not start WSL at boot. Never
   fatal. An `--update` of a service install passes the same lines (it
   rewrites and restarts the same unit); otherwise it behaves as before.
2. Setup: `carbon_setup_status` and Review return an additive warning
   `reboot_recovery_off` on Linux when this install's unit is not enabled
   (`systemctl --user is-enabled`) or linger is off (`loginctl`), with the
   exact command in `next_step`. Read only, short timeouts; anything unknown,
   unreadable or off Linux warns of nothing. Status gains a `warnings` list;
   no existing field or code changes, and the recorded profile's warnings
   never hold this live one.
3. Docs: "After a reboot" in `docs/development/FRESH_MINER_JOURNEY.md`, with a
   one-time PowerShell logon task for a single WSL distro and user.

## Non-goals

- No signer service: the miner starts `carbon-miner-signer` themselves.
- No mainnet or other auto-confirm; how commitments are confirmed is
  unchanged.
- No change to how campaigns resume after a restart in this slice.
- Nothing touches keys, wallets or the signer; sudo is only ever printed.

## Definition of done

- Installer tests with stand-in `systemctl`/`loginctl`: linger already on,
  turned on, and refused (prints the sudo line, install succeeds); a plain
  install asks loginctl nothing; setup's unit name matches the installer's.
- Warning tests with stubbed subprocess calls: present for a unit not found,
  disabled, and linger off; absent when on, unknown, failing, off Linux, or
  with checks lacking the probe; Review's own warnings unchanged and first.
- Existing installer, setup and invariant tests pass unchanged; the installer
  fixture gains a loginctl stand-in so no test runs the real one.
