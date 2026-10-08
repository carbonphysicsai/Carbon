# Launchpad acceptance findings (LAUNCHPAD-ACCEPT-01)

This register lists every defect a real acceptance cell, or Graphite as the
first heavy user, hits. Each entry gives the cell, the closed code or failure,
the cause, and the slice or PR that fixes it. The plan is
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`.

## LA-F1: `install_miner.sh --gpu` stops with "Permission denied" on a clean clone

- **Cell:** F01 (fresh-machine install, plan §4 step 1), on the `carbon-fresh`
  WSL distro, 2026-10-07.
- **Failure:** the C-03 worker image built. Then `install_miner.sh` line 269
  ran `./scripts/dev/accelerator_worker_image.sh` and failed with
  `Permission denied`; the installer exited 126.
- **Cause:** the script is mode 100644 in the git index, so no clean clone
  could ever run the `--gpu` path. `tests/cpu/test_miner_install.py` writes
  its stand-in scripts as 0755, so it could not see the checkout's mode.
- **No miner workaround:** a local `chmod` dirties the checkout, and the
  installer then refuses to run.
- **Fix:**
  - the script is now 100755;
  - `tests/cpu/test_installer_script_modes.py` reads the index and asserts
    that the installer and every script it runs directly, on every path,
    `--update` included, are 100755.
- **Checked and not affected:**
  - `julia_worker_image.sh`, `julia_worker_service.sh` and
    `workbench_science_checks.sh` are 100644, but every caller runs them
    with `bash`;
  - the accelerator script's own helpers are also run with `bash`.
- **Noted, outside the installer:** `workspace_preflight.sh`,
  `c07_development_vertical.sh` and `tpu_worker_image.sh` are 100644.
  - The first two have usage lines that say to run them directly.
  - No miner path runs them.

## LA-F4: a Graphite launch without both provider ceilings is queued, then dies untyped

- **Cell:** a Graphite launch on the fresh machine, 2026-10-07.
- **Failure:**
  - `carbon_launch` with `agent: graphite` and `budget.ceilings`
    `{epochs: 1, provider_nanodollars: 500000000}` was admitted and QUEUED.
  - The run then died in `carbon/battery/campaign.py` `graphite_plan` with a
    bare `ValueError` ("needs finite provider_attempts and
    provider_nanodollars ceilings").
  - The interruption recorded `builtins.ValueError` with code null. The
    miner saw `campaign_interrupted` and "Resume", and a resume can never
    succeed.
- **Cause:** the launch doors did not check what the plan needs. The plan
  needs both `provider_attempts` and `provider_nanodollars` as whole numbers,
  and its refusal carried no closed code.
- **Fix:**
  - `agent_plan.finite_ceilings` is now the one predicate. The plans and the
    launch doors both read it.
  - Both doors refuse such a launch `graphite_ceilings_required`, field
    `budget`, before the chain is read or anything is queued. The next step
    names both ceilings.
  - A plan that still meets one raises the typed `CeilingsRequired`, so its
    interruption records the code.
  - Decision: `.agent/decisions/2026-10-07-LAUNCHPAD-FINDINGS-F4-F6.md`.

## LA-F5: resuming a campaign interrupted before its manifest froze is refused the key

- **Cell:** the resume after LA-F4's interruption, 2026-10-07.
- **Failure:** `carbon_resume` was refused
  `model_provider_credential_not_configured`. The runner profile has
  `provider_credentials.engy-chat`, and the launch named
  `model_provider: engy-chat`.
- **Cause:**
  - `_frozen_credential` reads the provider from the frozen manifest, and
    there was none yet.
  - It fell back to the pinned default provider. `foreign_default_key`
    refused it, because the default key slot names engy-chat's key.
- **Fix:**
  - Before a manifest exists, the resume check now uses the provider the
    admitted launch recorded (`runner.launch_provider`, read with
    admission's own rule).
  - Its key is checked for that provider only.
  - With nothing recorded, the pinned default's rule stands, and it still
    fails closed.

## LA-F6: the Control Center service cannot reach Docker on a fresh WSL distro

- **Cell:** F01 (fresh-machine install) with `--service`, on the
  `carbon-fresh` WSL distro, 2026-10-07.
- **Failure:**
  - The owner added the user to the `docker` group after the user's systemd
    manager had started.
  - `install_miner.sh --service` checked Docker from the interactive shell,
    which has the group, and passed.
  - The service ran without the group. `systemd-run --user --wait id -Gn`
    lacks `docker`, and `docker info` there is "permission denied".
  - The worker doctor then failed in the service and every user unit:
    `accepted numerical host unavailable`.
- **Cause:** the installer asked the shell, not the manager that runs the
  service.
- **Fix:**
  - With the service, step 1 asks the user manager itself to run
    `docker info` (`systemd-run --user`), before anything changes.
  - If the manager cannot reach Docker, the install stops with the fix and
    what that fix stops. On WSL, `wsl --terminate <distro>` from Windows.
    Elsewhere, `sudo systemctl restart user@<uid>.service`.
  - `docs/development/FRESH_MINER_JOURNEY.md` says so at the Install step.
