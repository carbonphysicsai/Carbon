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
6. **Adoption: dropped (recorded working decision, 2026-10-06).** The
   owner's cloud-VM decision superseded it. The PC pool
   (`graphite-hidden-v1`) is discarded unused (`HIDDEN_HOST_SETUP.md` §0),
   `graphite-tuning-v1` was never sealed, and the VM starts from a fresh
   root. So there is nothing to adopt. The producer draws every hidden batch
   on the VM, and `graphite-tuning-v2` is sealed and solved there by its own
   tool (runbook §B), which keeps it producer-only by construction.

## HUMAN_INPUT, fail closed

- **Each Challenge's rotation cadence:** while null, the producer prepares no
  scheduled batch.
- **Steering where new cases are drawn,** Q(x) against P(x) (item 5 of the
  parity record): uniform draws only until it is recorded.
- **The release decision for retired batches.**
- *(Settled: Carbon is the sole producer; it draws and solves.)*

## Slices

- **S1: the producer core** (`carbon/challenge_validator/producer.py`).
  - The `BatchSource` interface, and battery's source
    (`BatteryBatchSource`, which wraps the validator's own `prepare_batch`,
    seed journal and references digest).
  - `draw`, `solve` (in the pinned truth image), `seal` and `status`.
  - The owner-only producer journal, and public commitments: fingerprint,
    references digest, case count, contract, rule and seed pin. The window
    is null until S3.
  - Only served kinds (screening, finalist) are drawn. The config loads only
    under its service account.
  - **Moved to S2:** signing the commitment, done where it is published.
  - Tests on synthetic roots
    (`tests/cpu/test_challenge_validator_producer.py`).
- **S2: the answer-key service and validator import.**
  - `btauth/1` plus the validator-permit check;
  - the per-hotkey fetch log;
  - producer-only roles refused;
  - the daemon's import-only mode, with `FAILED_INFRA` on a missing or
    mismatched batch.
  - **Built** (VALIDATOR-18's two-host design):
    - `producer publish` signs packages with Carbon's producer key;
    - `answer_key.py` handles packages, verification, the validator `sync`,
      and `keygen`;
    - `distribution.py` is the public host: `btauth/1`, the permit read
      from `chain/permits.py`, the fetch log, and an inbox that serves only
      verified packages;
    - deployments get `batch_source: "answer_key"` (import-only).
  - **The validator verifies every package itself:** the signature, the
    payload digest, the re-derived fingerprint and references digest, and
    the commitment's contract and rule against its own.
  - **Left to S3:** windows, retirement removal from the distribution host,
    and the push channel's operator steps.
- **S3: rotation and retirement.** A finalized-block tick, the cadence gate,
  the release-queue hook, and the new-Challenge owner-approval argument.
  - **Built:**
    - `producer tick`: slots and windows from each Challenge's registered
      rule (battery v2: 1,080 blocks, 3 live). It fills slots ahead of
      their windows, never late; records `slot_unfilled`; and on retirement
      moves the package out of the outbox and records
      `release: HUMAN_INPUT`.
    - Each source needs an `approval` record pinned by sha256.
    - Windows are signed into the package commitment.
    - The distribution host never serves an unwindowed or retired package.
    - Import-only validators activate exactly the windows covering their
      newest finalized block, never by their own clock. Two validators
      agree whatever order they imported in, and they never stall.
    - Operator steps (tick timer, `rrsync` push, distribution, validator
      sync): `docs/development/graphite/ANSWER_KEY_OPERATIONS.md`.
  - **Gap fixed:** rule v2's rotation started each validator's clock at its
    own first admission, so validators sharing batches rotated at different
    blocks.
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
  - **Built (in process):**
    - `acceptance.parity`: held batches, references, windows and salt
      digests, and the active set at every block, across validators.
    - `acceptance.score_parity`: one submission at one block gets the same
      active batches, references and aggregate on every validator.
    - `distribution.fetchers` / `leak-narrowing`: a leaked batch narrows to
      the hotkeys served it in a block range (leak 1).
    - `acceptance.permit_exposure`: what a permit holder can fetch, counted
      from the cadence (leak 2).
    - Three import-only validators with separate roots and import orders
      agree on all of it (`test_challenge_validator_acceptance.py`).
  - **Gap found and fixed:** the reconstruction seed came from each
    validator's own private root, as did the finals' seeds. So validators
    sharing batches rebuilt a seed-sensitive construction differently, and
    scored the same submission differently.
    - The producer now ships a secret per-batch `reconstruction_salt`
      inside the signed package (`seeds.reconstruction_salt`).
    - Import-only validators derive every seed from their active batches'
      salts (`seeds.shared_seed`): the same for every validator holding
      those batches, and unpredictable to miners.
    - Deployments that draw their own batches are unchanged.
  - **Not yet measured:** leak 1's score advantage. A Level-0 miner holding a
    leaked batch can only select hyperparameters against it (a declarative
    recipe carries no data). The harness is here; the live measurement runs
    with the testnet acceptance run.
  - **The live testnet run needs the owner's choice of hotkeys.** The ticket
    names UIDs 0, 1 and 2, but:
    - UID 1's hotkey is not in the WSL wallet, and the owner asked for it
      to be left alone;
    - UID 2 is the hotkey Graphite mines with.
    Each validator also needs a validator permit on 567. Until the owner
    names the hotkeys, the run is blocked, fail closed; everything above
    runs in process.

- **Finalists** (for the dress rehearsal, OWNER-REHEARSAL-AND-RELEASE-01):
  - Each slot carries one finalist batch (`pfinal-S<slot>`) beside its
    screening batch, under the same signed window.
  - Import-only validators claim a final's set by the earliest live
    producer window, then the fingerprint, never by their own import order.
    Every validator therefore judges the same final on the same fresh cases.
  - **Gap fixed:** the claim used to follow each validator's local journal
    sequence.

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

**Built, part 1: the tuning set's quiz path** (branch
`claude/validator-19-quiz-tuning`, stacked on #702's `value/quiz.py`).
- `carbon/battery/quiz_stratum.py` draws and assembles a quiz from a private
  root. It applies Data Collection's rulings:
  - **Draws** are uniform `seeds.draw_inputs` under the reserved tuning role,
    at draw indices above any main-set draw.
  - **Q3 refusals:** a condition within both 2 °C and 0.03 soc0 of a
    protected condition is redrawn. Protected means every committed
    contract's scenario conditions plus the committed practice decision set
    (B4, `practice-decision-set-v2`, read through its pins).
  - **Q2 pool:** near-limit candidates in draw order, capped at 320.
    `q2_select` reads only the registered panel's predictions.
  - **Q3 selection:** the first 8 feasible scenarios. The quiz records its
    redraws and its panel version.
- **Tuning commands:** `quiz-jobs [--round N]`, `quiz-select` (refuses with
  `tuning_quiz_needs_more_q3:--round N` when fewer than 8 are feasible), and
  `quiz-seal` (a `quiz` seed-journal entry carrying only the digest, counts
  and panel version). Also `predict --quiz` and `score --quiz`, which write
  `quiz-scores.json` and `q3-regret.json`.
- **Not yet:** the producer's quiz (part 2) and the gate (rule v3, the
  owner's).

**Built (part 2): the quiz inside every hidden batch** (branch
`claude/validator-19-quiz-hidden`). Drawn and reported only; it gates nothing.
- **Producer:** an optional config `quiz: {"panel": PATH}`. Without it,
  batches seal exactly as before.
  - With it, each screening batch's draw also draws its quiz, from the
    producer root under the batch's own role (`BatteryBatchSource.quiz_draw`,
    quiz_stratum's reserved indices). The quiz jobs share the batch's
    `jobs.json` and `solve`.
  - `seal` selects the quiz as the tuning set does: k = 8 feasible Q3
    scenarios, protected and infeasible redraws counted, then Q2's ~320-case
    pool and 80 cases by the registered panel's predictions only.
  - The panel is rebuilt once per version and cached owner-only
    (`quiz-panel/<challenge>/v<N>`); each batch only infers.
  - A short Q3 round journals `quiz_round` and keeps the batch PENDING, so the
    next tick solves the new round (slot-unfilled logic unchanged).
  - The commitment gains `quiz_digest`, `quiz_references_digest` and
    `quiz_panel_version`, and the payload `quiz: {document, references}`. The
    quiz digest is also sealed to the producer's seed journal (kind `quiz`).
  - Finalist batches, and batches drawn without the config, carry no quiz.
- **Import:** `BatteryAdapter.import_answer_key` re-derives both digests
  (`producer.quiz_digests`), the panel version, the role and the reference
  set, and refuses a mismatch (`answer_key_quiz_mismatch` / `_malformed`). The
  quiz is stored per batch (`batch_quizzes`). A package without one imports as
  before.
- **Report:** after a score commits, the daemon infers the retained model on
  its active batches' quiz inputs. The predictions are stored under
  `quiz/<submission>`, never a scored key.
  - It stores `q2_measures` and Q3 judged outcomes and measures, per batch and
    pooled, in `quiz_reports`.
  - `BatteryAdapter.score_record` and `HiddenPool._operator_record` carry it
    as `quiz`; `hidden_score.report` adds a per-pool-version quiz table.
  - A quiz inference failure is the quiz's own `FAILED_INFRA` (retried by
    the next `quiz_report` call). The submission's state, score, nomination
    and outcome are untouched.
- **Kept off the miner closure.** The miner edition reaches the daemon and
  `challenge_validator/battery.py` through `intake_client`. `quiz_stratum` and
  `value.quiz` reach `value.panel → track_a → attack`. So:
  - The quiz's science lives only in the operator module
    `challenge_validator/battery_quiz.py`. It holds `BatteryQuizSource`, which
    `producer.source_for` builds, and `install`, which injects
    `target.quiz_measures` as `development_compiler` is injected.
  - Graphite's `HiddenPool` installs it. A validator run without it measures
    nothing until `python -m carbon.challenge_validator.battery_quiz report`.
  - The importer reads `battery/quiz_document.py` (shape, digest, inputs) and
    `challenge_validator/batch_source.py` (the neutral contract, re-exported
    by `producer`).
- **Tests:** `tests/cpu/test_challenge_validator_quiz_hidden.py`.
- **Found, not fixed:** `hidden_score.report` raises for any primary record
  on main, because `_variant_ranking` is handed the device-class map
  (#692 with commit 404559e). Six existing tests fail on main for this. The
  fix decides whether a variant ranks across device classes, so it is left
  to its owner.
