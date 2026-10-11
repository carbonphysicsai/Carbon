# Survive a reboot (SURVIVE-REBOOT-01)

**Owner decision, 2026-10-10:** "Yes. Fix this system". The proposal was to
make the tunnel and the signers system services, so they restart on their own
after any reboot.

**Scope:** the operator's test machines only.
- The **six testnet-567 test signers** (canary, minerC–G) on `carbon-fresh`.
  These are the auto-confirm test hotkeys.
- The **validator tunnel** on `Ubuntu-24.04`.

**Not in scope:**
- minerA and minerB stay manual signers, because they are not on the
  auto-confirm allow-list. The installer refuses any hotkey that is not on it.
- No mainnet signer or key is involved.

## What runs where

| Distro / user | Unit | Replaces |
|---|---|---|
| `carbon-fresh` / `miner` | `carbon-test-signer@<lane>.service` (user unit, `Restart=always`, `WantedBy=default.target`) | tmux `signers` windows |
| `Ubuntu-24.04` / `carbon` | `carbon-validator-tunnel.service` (user unit, `Restart=always`) | tmux `tunnel` loop |
| Windows | a logon scheduled task that starts both distros and keeps them up | someone opening a WSL terminal |

Both users need linger, so their units start at boot with no login:
`loginctl show-user <user> -p Linger` shows `yes`.

**Keys.** The signer unit names a wallet; the signer opens the hotkey itself.
The tunnel unit names its key and known-hosts files by path. Nothing here
reads, copies or prints a key, a password or the validator host's address.
The address comes from the pinned known-hosts file at run time.

A signer run as a service has no terminal. Anything that would need a person
at the signer is refused there. Only allow-listed testnet commitments are
auto-confirmed (OWNER-SIGNER-TESTNET-AUTOCONFIRM-01).

## Install

**Signers,** on `carbon-fresh` as `miner`. The lanes file holds one public
`lane wallet hotkey` line per signer, and is kept in
`~/.config/carbon/test-signers/lanes` (mode 600):

```bash
scripts/dev/survive_reboot/install_test_signers.sh ~/.config/carbon/test-signers/lanes --receiver <valV2 ss58> --receiver <publisher ss58>
```

After LA-F17 merges, drop the publisher receiver and run it again.

**Tunnel,** on `Ubuntu-24.04` as `carbon`:

```bash
scripts/dev/survive_reboot/install_validator_tunnel.sh
```

**Windows: the owner runs this once,** in PowerShell. It is a persistent
Windows setting. It registers a logon task that starts both distros, hidden,
and keeps each up with `sleep infinity`, so their systemd units run:

```powershell
$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "Start-Process wsl.exe -WindowStyle Hidden -ArgumentList ''-d carbon-fresh -u miner --exec sleep infinity''; Start-Process wsl.exe -WindowStyle Hidden -ArgumentList ''-d Ubuntu-24.04 -u carbon --exec sleep infinity''"'; Register-ScheduledTask -TaskName 'Carbon WSL at logon' -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) -Action $a -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero))
```

To remove it:
`Unregister-ScheduledTask -TaskName 'Carbon WSL at logon' -Confirm:$false`.

## After a reboot: check

```powershell
wsl -d carbon-fresh -u miner -- ~miner/.local/bin/carbon-reboot-check; wsl -d Ubuntu-24.04 -u carbon -- ~carbon/.local/bin/carbon-reboot-check
```

It prints the signer units, the tunnel unit, the three forwarded ports and
the Control Centers. Every unit should be `active running`, and every port
`open`.

To stop one signer: `systemctl --user stop carbon-test-signer@<lane>`. To
keep it off after reboots as well, `disable --now` it.

## Incentive runners: scrapped (2026-10-11)

The owner scrapped the incentive runner timers on 2026-10-11 ("If I'm making
it harder with these timers, scrap them. Stop inhibiting testing."). They had
been added for minerH and minerI by #1037. The timers are stopped and
disabled on `carbon-fresh`, and their units and installer are removed here.
The role miners' handover cycles are now run by hand, one per tempo, with
`python -m scripts.dev.canary.runner once --config <lane config>`. Record:
`.agent/decisions/2026-10-11-INCENTIVE-RUNNER-TIMERS-SCRAPPED.md`.
