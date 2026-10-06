# VALIDATOR-19: an automated pool-batch producer, built the mainnet way

**Status:** design. Slices are built after #665 merges. Security-sensitive
(AGENTS.md §13): it needs a dedicated review.

**Authority:**
- OWNER-VALIDATOR-MAINNET-PARITY-01 §3 and §5;
- OWNER-SHARED-ANSWER-KEY-01, with its validator-GPU and standard-Bittensor
  addenda;
- the owner's request, relayed by the Test Lead on 2026-10-05: a repeatable
  automated process for pool batches, covering rotation and new Challenges.

**Builds on** VALIDATOR-18 (the shared answer key design). This ticket is its
automation.

**Executor:** the Carbon Validator session.

## Reconciled with the owner's rulings

The Test Lead's shape said "encrypted per validator" to "registered
validators". The owner's later ruling (OWNER-SHARED-ANSWER-KEY-01, the
standard-Bittensor addendum) replaces both:
- **admission** is any hotkey holding a validator permit in the finalized
  metagraph;
- **distribution** is a Carbon-hosted HTTPS service that serves a batch on a
  `btauth/1` hotkey-signed request, over TLS, with every fetch logged per
  hotkey.

Fetches are attributable through that log. A leaked key is byte-identical
across validators, so it narrows only to the set of fetchers in that window,
and per-validator encryption would not change that. It is not built.

The Test Lead accepted this, and it settles the sole-producer question:
Carbon draws and solves.

## Design

1. **The producer** (`carbon/challenge_validator/producer.py`), one
   Challenge-neutral command over each Challenge's `BatchSource` adapter.
   - **Draw** from the registered population, using the producer's root
     (`seeds.make_batch` for battery).
   - **Solve once** on the producer's compute (battery: the pinned truth
     image, host CPU).
   - **Seal:** fingerprint plus references digest, committed to the
     producer's append-only journal.
   - **Publish the public commitment:** fingerprint, references digest,
     activation window (finalized blocks), rule and contract digests. It is
     signed by Carbon's service key.
   - **Serve the batch** to validators through the answer-key service.
   - **Producer-only sets:** tuning and confirmation sets are produced and
     kept by the producer only. They are never served, and the service
     refuses them by role.
2. **Validator import** (in the daemon; it replaces drawing batches).
   - Fetch the active batch with the validator's hotkey.
   - Verify it against the public commitment, and store it owner-only.
   - Activate and rotate it by finalized block, as the manifest's window says.
   - A missing or mismatched batch makes that validator's scoring
     `FAILED_INFRA` (typed, retried, never a score). A validator never draws
     or solves a replacement.
3. **Retirement.** A retired batch moves to a release queue. The hook is
   `CARBON_COMMIT_TO_TRAINING_POOL` (OWNER-BATTERY-3B-AND-EXPOSURE-01).
   Releasing is never automatic: the release decision is HUMAN_INPUT.
4. **Rotation by finalized block** and the Challenge's registered cadence,
   with no human or agent in the loop.
   - Each tick, the producer reads the finalized block and prepares the next
     batch ahead of its window.
   - **Launching a new Challenge** needs an owner-approval argument: the
     record id plus its digest. Without it the producer refuses.
5. **Isolation.** It runs as a dedicated OS service account, with the setup
   below.
   - Agents' accounts get no read access to its state.
   - Its outputs contain only fingerprints, windows and verdicts.
6. **Adoption without re-solving.**
   - `producer adopt` takes the existing `graphite-hidden-battery-v1` batches
     and the tuning seal (runbook §B): it verifies each against its committed
     fingerprint and its ingested references digest.
   - It records them in the producer's journal as adopted, with their
     original commitments.
   - The tuning set stays producer-only.

## HUMAN_INPUT, fail closed

- **Each Challenge's rotation cadence:** while null, the producer prepares no
  scheduled batch.
- **Steering where new cases are drawn,** Q(x) against P(x) (item 5 of the
  parity record): uniform draws only until it is recorded.
- **The release decision for retired batches.**
- *(Settled: Carbon is the sole producer; it draws and solves.)*

## Slice 0 first: isolation before any seal (the owner, 2026-10-06)

> yes, move the service account to the front

**Why.** Hidden cases, references and tuning material are protected by file
ownership only.
- Today every agent session runs as the WSL `carbon` account.
- Graphite's hidden-pool scoring (#642, #665, #679) loads the validator
  deployment inside Graphite's own process, so that process, and any session
  sharing its account, can read the hidden material.

**Until S0 lands:** no hidden pool batch, tuning set or confirmation set is
sealed, and `--hidden-deployment` is never run against a sealed batch.

- **S0a: service accounts.**
  - A `carbon-producer` system user, with the setup steps below, owns the
    producer, the tuning work and every hidden deployment's state.
  - Each command that touches hidden material refuses when the effective
    user is not the deployment's configured `service_account`: `operate`,
    `confirmation seal`, `tuning`, and the daemon's `run --every`. It fails
    closed.
  - **The acceptance check:** `sudo -u carbon ls` on every hidden path
    prints "Permission denied".
- **S0b: Graphite reaches the validator over the wire.**
  - The hidden deployment runs as a service under `carbon-producer`, behind
    the existing hotkey-signed battery intake (`battery/intake.py`, NET-2).
  - `HiddenPool` submits through the intake client, with its
    `graphite-dev:` identity, and receives only the sealed miner outcome.
  - Operator records and the hidden-pool report are written by the service
    under its own account. Graphite holds only fingerprints and verdicts.
  - The in-process path (`deployment.evaluate` inside Graphite) stays for
    synthetic test fixtures only, and refuses a deployment whose
    `service_account` is not the current user.

## Slices

- **S1 (after S0): producer core and adoption.**
  - the `BatchSource` interface, battery's adapter, the producer journal and
    commitments;
  - `adopt` for the existing pool and tuning seal;
  - tests on synthetic roots.
- **S2: the answer-key service and validator import.**
  - `btauth/1` plus the validator-permit check;
  - the per-hotkey fetch log;
  - producer-only roles refused;
  - the daemon's import-only mode, with `FAILED_INFRA` on a missing or
    mismatched batch.
- **S3: rotation and retirement.** A finalized-block tick, the cadence gate,
  the release-queue hook, and the new-Challenge owner-approval argument.
- **S4: service accounts and the testnet acceptance test.**
  - Testnet UIDs 0, 1 and 2 run as three validators under separate OS
    accounts.
  - Acceptance requires identical batches and identical scores for the same
    submissions (with A40 rebuilds, per VALIDATOR-18).
  - **The leak family**, measured, with fixing either left to the owner:
    1. **A single validator leaks.** UID 2's batch is handed to a test miner.
       Measure the miner's score advantage, and how far the fetch log
       narrows the leak: to the set of fetchers in that window, never to one
       validator, because the key is identical.
    2. **A miner gets a validator permit** (by staking) and fetches the active
       key itself. Measure the expected exposure for each rotation window.

## Operator setup (Ryan; exact steps, run once per host)

```bash
# 1. The producer's service account (no login shell, no home for agents to read).
sudo useradd --system --create-home --home-dir /var/lib/carbon-producer --shell /usr/sbin/nologin carbon-producer
sudo install -d -m 0700 -o carbon-producer -g carbon-producer /var/lib/carbon-producer/{roots,journals,batches,work,service}
# 2. A pinned, read-only checkout it runs from (root-owned, world-readable code only).
sudo git clone --depth 1 https://github.com/carbonphysicsai/Carbon.git /opt/carbon-producer && sudo chown -R root:root /opt/carbon-producer
# 3. Its configuration (owner-only; paths only, no secrets inline).
sudo install -m 0600 -o carbon-producer -g carbon-producer /dev/null /etc/carbon-producer.json
# 4. Prove agents cannot read it (must print "Permission denied").
sudo -u carbon ls /var/lib/carbon-producer
```

The **systemd units** are added in S3:
- `carbon-producer.service`, with:
  - `User=carbon-producer`;
  - `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `ProtectHome=yes`;
  - `ReadWritePaths=/var/lib/carbon-producer`;
- `carbon-producer.timer`, which ticks every 5 minutes; the producer decides
  from the finalized block and cadence.

Only root can start, stop or change the timer, and agent accounts have no
sudo. For the acceptance test, repeat step 1 for `carbon-validator-0`, `-1`
and `-2`, each with its own deployment directory and hotkey path.

## Maturity

Design only.

## Protect first (the owner, 2026-10-05, relayed by the Test Lead)

> Build on protection instead of backing down.

When an attack finding hits a construction freedom, the default fix keeps the
freedom and adds a protection in the rebuild path. The kinds of protection:
- an isolation or resource profile;
- a determinism pin (A40 plus the pinned configuration, VALIDATOR-18);
- a verifier;
- a provenance check (digest-bound recipes and batch commitments).

Narrowing a freedom is the last resort. If it is needed, it is a versioned,
temporary policy that names the protection which will lift it. This applies
to this ticket's rebuild path and to the Level 4–5 isolation work.
