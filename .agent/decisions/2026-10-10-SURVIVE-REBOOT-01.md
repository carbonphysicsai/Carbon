# SURVIVE-REBOOT-01: test signers and validator tunnel restart on their own

**Owner decision, 2026-10-10:** "Yes. Fix this system". It was relayed by the
Test Lead, and the owner then took the building session out of auto mode for
the change. The proposal: make the tunnel and the signers system services, so
they restart on their own after any reboot.

**Decision:**
- The six testnet-567 auto-confirm test signers (canary, minerC–G) run as
  systemd user units on the operator's `carbon-fresh` distro.
- The validator tunnel runs as a systemd user unit on `Ubuntu-24.04`.
- Both have `Restart=always`, with linger on for their users.
- A Windows logon task, registered by the owner, starts both distros.

Templates, installers and the reboot check are in
`scripts/dev/survive_reboot/`.

**Bounds:**
- Only hotkeys on the owner's testnet-567 auto-confirm allow-list may become
  units. The installer refuses any other, so minerA and minerB stay manual
  signers.
- No mainnet signer or key is involved.
- No key, password or host address is read, copied, printed or committed.

**Risk accepted with this decision:** the test hotkeys are unlocked after
every boot with nobody present. That is the exposure already accepted for
unattended testnet signing in OWNER-SIGNER-TESTNET-AUTOCONFIRM-01, now
lasting across reboots.

**Reserved:** the Windows scheduled task is the owner's to register or
remove. Any change to who is on the allow-list is the owner's.
