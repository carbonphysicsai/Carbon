# Fresh-miner journey, 2026-10-07 (LAUNCHPAD-ACCEPT-01 §4)

Runbook: [FRESH_MINER_JOURNEY.md](../../FRESH_MINER_JOURNEY.md). The run is
in progress; each step is recorded as it completes.

## When and where

- **Date:** 2026-10-07.
- **Machine:** WSL2 distro `carbon-fresh` on the owner's PC.
  - Ubuntu 24.04.5 LTS, x86-64, kernel 6.18 WSL2, systemd as PID 1.
  - GPU: NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB, driver 581.95.
- **Docker:** the distro's own Docker Engine 29.8.2 (server OS Ubuntu, not
  Docker Desktop), with the `nvidia` runtime present.
- **Accepted revision:** `f1dd652debdf` (main, the merge of #777), from step 1's run.

## Step 0: clean state (2026-10-07, read-only check by the agent)

- No `~/carbon` checkout, no `~/.carbon`, no `~/.hermes` or Hermes Carbon
  profile, and no Carbon testnet state.
- Docker holds 0 images.
- `uv` is not installed; the installer brings its pinned one.
- **Wallet:** `carbon-rehearsal-minerB` holds only `coldkeypub.txt` and
  `hotkeys/{default,defaultpub.txt}`, with modes 700 and 600. It has no
  coldkey.
- **Inference key files:** `engy-api-key` and `chutes-api-key` under
  `~/.config/carbon`, mode 600, non-empty. Their contents were not read.
- **Free disk:** 954 GiB in the distro, and 219 GiB on C:. Both are above the
  29 GiB the GPU install needs.

## Step 1: install (`install_miner.sh --gpu --service`)

**Run 1 (2026-10-07): FAIL, exit 126.**
- The C-03 worker built: `sha256:d31bfbb1…`.
- Step 4 then stopped on
  `./scripts/dev/accelerator_worker_image.sh: Permission denied`.
- That script was mode 100644 in the index. This is finding LA-F1, fixed
  by #775.
- The owner keeps the log as `f01a-install-permission-denied.log`.

**Run 2 (2026-10-07, after #775): PASS, exit 0.** Each of the six steps
reported success:
1. Machine check: Linux x86-64, git, curl, Docker and free disk all ready.
2. Carbon at `f1dd652debdf`, a clean checkout.
3. The locked environment was installed.
4. Images built on this machine:
   - worker: `9d7004a31e57`. It is a new identity, not run 1's `d31bfbb1`,
     because the script's mode is part of the source tree;
   - analysis image: `2872bb294218`;
   - GPU worker: `8776a915560b`.
5. The images were recorded in `installed-images.json` (mode 600). Setup
   reports "Compute: not set up yet".
6. The Control Center runs as the user service `carbon-control-center`
   (active, enabled) on `127.0.0.1:8788`.

- **State directory:** mode 700; every file in it is mode 600.
- **Session token:** it is in `control-center.log` only. It was filtered out
  of everything read here.
- **Finding LA-F2:** the analysis image and the GPU worker are untagged.
  Docker lists both as dangling, so a `docker image prune` would delete them
  (see FINDINGS.md).
