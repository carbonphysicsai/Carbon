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
