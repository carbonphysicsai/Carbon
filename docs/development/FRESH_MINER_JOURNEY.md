# The fresh-miner journey (C-MLP-03 slice 6)

This runbook is the acceptance run for C-MLP-03
(`.agent/tickets/C-MLP-03_miner_environment.md`, slice 6). A person takes a
clean machine from nothing to a submitted battery candidate.

The run confirms the provisions slices 2 to 5 closed: model, compute and
agent. It closes no Gap itself, and nothing in it qualifies anything.

Carbon rents no compute (OWNER-MINER-COMPUTE-LINK-ONLY-01). Research runs on
this machine by default. Remote compute is optional and the miner's own: any
machine or container you run, which you start, stop and pay for yourself.
Carbon reaches it with your own SSH and never uses a provider key
([MINER_REMOTE_SETUP.md](MINER_REMOTE_SETUP.md)).

It needs things this repository cannot supply: a clean machine, a registered
hotkey on subnet 567, the miner's own inference key, and a validator to
submit to. Record each run under `docs/development/evidence/fresh-miner-<date>/`
with the fields in [Record](#record).

## Before you start

- **A clean machine.** Linux x86-64 (or WSL2 on Windows) with Docker. For the
  GPU paths it also needs an NVIDIA GPU with the NVIDIA Container Toolkit.
  Nothing Carbon-related may already be installed: no checkout, images, keys
  or `~/.hermes/profiles/carbon`.
- **Free disk.** 5 GiB beside the checkout, and 12 GiB where Docker keeps its
  images (24 GiB with the GPU worker). When one filesystem holds both, as on
  WSL by default, it needs the sum: 17 GiB, or 29 GiB with the GPU worker.
  The installer checks before it builds anything.
- **Never prune Docker on a machine others share** (`docker image prune`,
  `system prune` and the like). Prune deletes whatever the engine holds that
  matches, other people's images included. To free space on an engine of
  your own, remove only Carbon's images, by their tags (`carbon-c03-worker:`,
  `carbon-cw1d4-parent:`, `carbon-analysis:`, `carbon-gpu-worker:`).
- **A registered hotkey on subnet 567.** Register it in your own wallet;
  Wallet & Identity prepares the unsigned call.
- **Your inference key** for Engy (Chat Completions) or Chutes.
- **No provider key for compute.** Carbon asks for none. A machine or
  container you rent elsewhere is yours to start and stop. For the remote
  path, `ssh <destination>` must work from this machine without a prompt.
- **The validator.** Either it runs on this machine (`battery_validator` in
  the profile), or it runs elsewhere behind an intake.
  - **Carbon's evaluation endpoint.** When an operator has exposed an intake
    (OWNER-INTAKE-EXPOSURE-01), Carbon publishes it in
    `scripts/dev/miner_launchpad/published_endpoints.json`, and setup's Review
    writes it into your profile. You type nothing. The receiver hotkey listed
    beside it is binding (LAUNCHPAD-ACCEPT-03): Review pins it in your
    profile, and before your signer signs a submission, a resend or a status
    request, Carbon checks that the intake reports that receiver. An intake
    reporting another is refused `intake_receiver_mismatch`, with nothing
    signed or sent.
  - **A profile written before receivers were pinned** keeps submitting,
    unchecked; setup's Evaluation step and the prelaunch review warn
    (`intake_receiver_not_pinned`). Review again to pin it.
  - **Until one is published,** setup and the prelaunch review say so: your
    profile can practise and freeze, but cannot submit. Run the validator on
    this machine, tunnel to its loopback yourself, or give setup your own
    intake's URL under Review.
  - **A validator through a tunnel (LAUNCHPAD-ACCEPT-04).** A validator that
    binds its own loopback is reached from your machine as a loopback intake,
    for example `ssh -N -L 18467:127.0.0.1:8467 <validator host>` and then
    `http://127.0.0.1:18467`. Name it at Review as your own intake, with the
    validator's public receiver hotkey: `carbon_setup_review` with
    `intakes.<challenge>` and `receiver_hotkey`, or the browser's Review
    step under "Advanced: a validator's intake". Review reads its public facts
    first. The network must be Carbon's testnet, netuid 567, for the
    Challenge you named, or Review refuses
    `intake_serves_another_chain_or_challenge`; the receiver must be the one
    you named (`intake_receiver_mismatch`). If nothing answers, the refusal
    is `intake_unreachable`: start the tunnel or the validator, since Carbon
    cannot tell which is down. Such an address works only on a machine that
    holds the tunnel's key, so Carbon never publishes it
    (`published_endpoints.json` stays empty).

## Steps

1. **Install (C-MLP-04).** Clone Carbon and run its installer:
   `git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon && ~/carbon/scripts/install_miner.sh`,
   with `--gpu` for the GPU worker and `--service` to run the Control Center
   as a systemd user service.
   - It checks the machine, its free disk, and that the checkout is clean.
     A checkout with local changes stops it before anything changes, with
     the `git stash` command that sets them aside.
   - With `--service`, it also checks that your systemd user manager, which
     runs the service, reaches Docker. If you joined the `docker` group after
     the manager started, the install stops here (LA-F6). On WSL, run
     `wsl --terminate <distro>` from Windows and reopen it; elsewhere, run
     `sudo systemctl restart user@$(id -u).service`. Then install again.
   - It installs the locked environment, builds the worker and analysis
     images (and the GPU worker) locally, records them for setup, and checks
     setup against them.
   - It prints how to start the Control Center again, then starts it.
   - **Or install Carbon's released images (LA-F10,
     OWNER-WORKER-IMAGES-V2-01):** add `--release worker-images-vN`, for
     example `~/carbon/scripts/install_miner.sh --release worker-images-v2`.
     - The installer moves the checkout to that release tag. The tag must be
       on main.
     - It downloads the release's records from its GitHub release, then pulls
       each image they name from `ghcr.io/carbonphysicsai` by digest: the
       worker, the analysis image, and the GPU worker with `--gpu`. It checks
       each image against its record and builds nothing.
     - Setup accepts these images because the checkout is at the revision
       they were built from.
     - A tag that is not a release on main, a release without its records,
       or a failed pull stops the install before anything is recorded. The
       message names the command that builds the images locally instead
       (`--ref <tag>`, without `--release`).
     - Releases from before `--release` existed (`worker-images-v1`) cannot
       be pulled this way. Build them with `--ref`.
     - `--update --release <tag>` moves to that release only if it is at this
       install's revision or newer. To go back to an older release, run
       `--release <tag>` without `--update`.
     - Registry access is your own machine's. The public images need no
       login, and Carbon reads no credential.
   Record its output.
2. **Start your signer.** In your own terminal, run
   `~/carbon/.venv/bin/carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>`
   for your registered hotkey. With `--service`, this is your only terminal.
3. **Open the Control Center.** Use the address and token the installer
   printed. With `--service`, the token is the last `Local session token` line
   of `control-center.log` in the state directory. Confirm your registration
   under Wallet & Identity; for an unregistered hotkey it prepares the unsigned
   registration and the `btcli` command to run in your own wallet. Setup
   opens. A restart reopens your written setup without a flag.
4. **Inference.**
   - Choose Engy (the default) or Chutes, and type the model id.
   - Read the quoted maximum, tick to agree, and check.
   - Record the quote and the check's result.
5. **Compute.** Choose one of three:
   - this machine's CPU;
   - this machine's GPU (setup installs the host device record or names the
     `prepare` command);
   - your own remote machine or container, started by you
     ([MINER_REMOTE_SETUP.md](MINER_REMOTE_SETUP.md)).
     - Choose the transport: `ssh-docker` for a machine with Docker and the
       NVIDIA Container Toolkit; `ssh-container` for a container you started
       from the pinned GPU worker. After a `--release` install, setup names
       the released `repository@sha256:...` reference. Otherwise, push the
       worker with `scripts/dev/push_worker_image.sh`.
     - Give the SSH destination and port, the GPU worker manifest and the
       Challenge.
     - The check uses only your SSH and starts nothing.
     - For `ssh-docker`, if the worker is missing, tick to agree and send it.

   Record the check: the images; for this machine's GPU, the device; for a
   remote setup, the transport, what the check found and whether the worker
   was sent.
6. **Agent.** Choose Carbon's autonomous agent or Hermes. Leave the operator
   field empty: setup reads the network and its publisher from the chain, and
   records the block it read.
   - For Hermes, install it first (its installer), read the files setup will
     write, and tick to agree.
   - Record the Hermes version and the files written.
7. **Review.** Write the profile. Review writes the evaluation endpoint
   Carbon publishes for each Challenge. It warns, and setup's Evaluation step
   keeps saying, when none is published. To use an intake you run yourself,
   give its URL and its validator's public receiver hotkey (required); setup
   reads its public facts first and refuses `intake_receiver_mismatch` when
   the intake reports another receiver.
8. **Choose a Challenge and launch.** Under Challenges, read each one's
   description and research environment, and choose an implemented one. For
   Carbon's agent, launch from Campaigns with finite ceilings. For Hermes, run `hermes -p carbon chat` and ask it to launch,
   practise, freeze and submit; it asks you before each such tool.
9. **Practise on the GPU.** Every practice feedback records its backend:
   - on this machine's GPU, `ISOLATED_CARRIER_GPU`, with the device record and
     what JAX observed;
   - on your remote setup, `REMOTE_GPU`, with the transport, how the worker
     was verified (`image-id` or `build-identity`), the job transport, whether
     the cleanup was confirmed, and what JAX observed.

   Record two practices. For a remote setup, check afterwards that no
   `carbon-job-*` container or `/tmp/carbon-job-*` directory is left on it,
   then stop it yourself.

   Each practice result also says whether its recipe is inside the
   Challenge's submission compute budget, next to its training seconds
   (LAUNCHPAD-COMPUTE-BUDGET-STATUS-01). The line is admission's own rule:
   - "Within budget: X of Y <unit>" or "Over budget: X of Y <unit>", once the
     Challenge declares a budget;
   - "Budget not set for this Challenge" until then. This is every Challenge
     today. No number is shown, and the per-setting caps are the limit;
   - "Budget unit not calibrated yet" while the budget's unit needs factors
     the Challenge's study has not fitted.

   Each Challenge's budget comes from its own training budget study and the
   owner's decision on it. Practice is never refused by it. Freeze, commit
   and submit are: an over-budget recipe is refused `over_compute_budget`,
   with its cost and the ceiling, before anything is signed or sent.
   `carbon_budget_status` checks any recipe first.
10. **Freeze, commit and submit.** Record the submission and its verdict.
    When the validator runs elsewhere, also record the intake URL and the
    submission id. An intake whose validator requires an on-chain commitment
    refuses a submit `commitment_required`, before anything is sent, until
    the frozen candidate's digest is your hotkey's commitment:
    - Commit it with `carbon_commit` (or `POST /api/v1/operations/commit`).
    - Type the digest's last 8 characters in your signer's terminal when it
      asks; observe shows `confirm_commitment` meanwhile.
    - Record the digest, block and extrinsic id that observe shows read back.
    - Then submit. A `commitment_stale` refusal is answered by committing
      again with `recommit=true`.
    Observe and the campaign view show the same readback on both doors:
    - the submission id;
    - for a submit that was not a verdict, its refusal with `intake_outcome`
      (`QUEUED`, `UNAVAILABLE` or `REFUSED`);
    - a verdict's public fields: its state, exam rule, recipe and contract
      digests, and how it was rebuilt.
    Under a sealed rule (v2) a scored outcome is `sealed`: no screening,
    score, nomination or finals are shown.

## Updating

Stop the Control Center first: Ctrl-C in its terminal, or
`systemctl --user stop carbon-control-center`. A running Control Center stops
the update before anything changes. Then run:

```sh
~/carbon/scripts/install_miner.sh --update
```

An install made before 2026-10-03 has an installer without `--update`, which
refuses it. Run `~/carbon/scripts/install_miner.sh --no-start` once: that
older installer moves the checkout to the latest main, which brings the
current installer, but does not check setup against the new images. Then run
`~/carbon/scripts/install_miner.sh --update`, which does.

- It moves the checkout to the latest main, or `--ref` in main.
- It rebuilds every image built before, the GPU worker included. A plain
  `install_miner.sh` run does the same; `--update` also needs an earlier
  install and leaves the Control Center to the service or to you.
- It checks setup against the new images. A compute check made at the old
  revision or with the old images is set aside, and so is the profile written
  from it (moved to `environment/runner-profile.stale.json`, so a restarted
  Control Center does not load it). This machine's compute is checked again,
  and your profile is written again with the new accepted revision and the
  intakes you named. A remote setup needs the new worker: check Compute again,
  send or push it, and review again, naming your own intake again if you use
  one (setup shows it).
- It prints what changed, then starts the service again, or prints the
  command that starts the Control Center.

If you move the checkout yourself (`git pull`), setup shows compute as
unchecked and says to run `install_miner.sh --update`: only the installer
records a new install, so checking Compute again would not clear it.

Record its output with the run.

## Record

For every run, record:

- **When and where.** Date, the machine (OS, GPU), and the accepted revision.
- **Profile.** The runner profile's digest, never its contents.
- **Inference.** Provider, model, quote and check result.
- **Compute.** The choice. For a GPU, the device record digest. For a remote
  setup, the transport and the provider or machine kind, never its address.
- **Agent.** The choice and its version.
- **Evaluation endpoint.** For the Challenge, whether the profile's intake is
  Carbon's published one or your own, or that none was published.
- **Practice.** Each practice's backend record.
- **Submission.** The submission id and its verdict.
- **Anything that failed,** with its refusal code and the step it names.
