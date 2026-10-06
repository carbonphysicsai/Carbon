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

## Slices

- **S1: producer core and adoption.**
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

## Slice Q: the near-limit quiz (the owner, 2026-10-06)

**Authority.** The owner approved the Test Lead's proposal:

> Yes make the quiz questions maximally effective.

**What.** Every hidden batch carries a hidden, rotating quiz, and the gate
runs in screening.

**The quiz type is open** (the Test Lead, 2026-10-06). Data Collection is
comparing two registered types:
- **Q2, per case:** near-limit cases scored by G-FEAS and G-PLATE.
- **Q3, decision level:** hidden design scenarios. The validator runs a fixed,
  registered optimizer and checks its pick against each scenario's pre-solved
  reference grid, which every validator shares. This would catch EV5's
  Track A constructions, which fail only at the decision level (#686).

The producer is built to emit both near-limit cases and pre-solved scenario
grids. The type is chosen from that comparison, and the text below names Q2
only as one instance.

1. **The quiz stratum** (producer, after S1; Q2 shown, and Q3's
   scenario grids are produced the same way: drawn, solved once, sealed,
   shared).
   - The producer oversamples from the registered population and solves once.
   - It keeps the cases whose reference lies within a margin of a
     feasibility or plating limit, on both sides, so false-feasible and
     false-infeasible are both measurable.
   - "Near the limit" uses the one definition in `score_tuning`: the decision
     contract's constraint measure and its bands. Data Collection adds a
     public `near_limit` selector and `false_infeasible_rate` there.
   - **The margin is HUMAN_INPUT,** registered as a sweep.
   - Quiz membership is private, inside the sealed batch document, and
     committed with its fingerprint. The quiz rotates, retires and publishes
     with its batch.
2. **Kept apart from accuracy** (invariant 7.2).
   - Quiz cases are excluded from the accuracy score, so the population P(x)
     that score claims is unchanged.
   - The gates are computed on the quiz only.
   - In screening, a gate failure ranks last and never reaches the finals.
   - **This is an exam rule change:** a new battery rule version (v3), which
     the owner adopts once the margin and threshold are picked from the
     curves. Until then the quiz is drawn and reported, and gates nothing
     (fail closed).
3. **Tuning set.** `graphite-tuning-v1` is not sealed yet. It is superseded,
   before any seal, by `graphite-tuning-v2`, which adds a near-limit quiz
   stratum sized with Data Collection (VALIDATOR-17, prospective). v1 is
   never sealed.
4. **Over-caution is measured.** Every quiz report gives false-infeasible
   beside false-feasible, so a model that calls everything near the limit
   unsafe shows up as a value loss.

**HUMAN_INPUT, fail closed:**
- the quiz margin (swept);
- each gate threshold (swept; the owner picks);
- the quiz share of a batch;
- adopting rule v3.

**Build order:** S0 (#683), then S1 (the producer core), then Q.

**The agreed quiz** (Data Collection, approved by the Test Lead under the
owner's "maximally effective", 2026-10-06; evidence on #686). Both types
apply to every hidden batch and to `graphite-tuning-v2`.
- **Q2:**
  - 80 cases selected by panel disagreement, from a pool of about 320
    near-limit cases (`score_tuning.near_limit`, within 4 bands).
  - The disagreement panel is versioned:
    `docs/development/evidence/battery-quiz-designs/disagreement-panel-v1.json`,
    80 EV4 first-seed recipes. Later versions add retired top submissions.
  - Each batch records the panel version it used.
- **Q3:**
  - k = 8 decision scenarios, each a pre-solved 35-candidate grid, judged by
    EV4's fixed decision rules.
  - All-infeasible scenarios are excluded (quiz-registry-v5).
- **Producer cost per batch:**
  - Q3: about 0.8 CPU-h per scenario, about 6.4 CPU-h in all (accepted for
    the VM).
  - Q2: its 320-case pool needs about 1,280 draws solved at the ~25%
    near-limit rate. That is to be measured on the VM, unless the producer
    oversamples near the limit at draw time.
- **Still open:** these sizes come from the public stand-in, and the tuning
  set confirms them before any rule v3 adoption (the owner's). The margin
  stays HUMAN_INPUT and swept.

**Tuning output for Q3** (Data Collection, 2026-10-06): `tuning score` also
writes `q3-regret.json` in the tuning work directory. It holds, for each
member, the mean Q3 decision regret over the quiz's feasible scenarios.
- It is owner-only and aggregates only, with no scenario or case.
- Ryan passes it to `tuning_rescore --q3-regret` (leg `q` of
  `score_tuning.LEGS`, registry v3, #686).
- `score_tuning.near_limit_cautious` (the constructed over-caution control
  on #686) joins the known-bad-for-value set.
- It is built with slice Q, once #686 merges.
