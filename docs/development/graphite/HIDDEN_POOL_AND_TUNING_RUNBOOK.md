# Battery's hidden pool and tuning set: operator runbook

**Authority:** OWNER-GRAPHITE-TEST-WAVE-08 (operational testing in a
mainnet-mimicked environment) and OWNER-VALIDATOR-MAINNET-PARITY-01.

**Code:**
- VALIDATOR-13 (#642): hidden-pool scoring of Graphite constructions;
- VALIDATOR-17: the tuning set.

**Who runs it:** the operator, on the operator host. Every path below is the
operator's own, outside the repository, in an owner-only (0700) directory. No
step prints a root, seed or case. Sealing and solving are operator actions;
an agent never runs them.

> **HOLD: do not run any step yet** (the owner, 2026-10-06).
>
> Hidden cases, references and tuning material are protected only by file
> ownership. Every agent session runs as the WSL `carbon` account.
> - Do not create any deployment, seal or solve below until VALIDATOR-19's
>   slice 0 lands:
>   - a separate `carbon-producer` service account that agents cannot read;
>   - every command refusing the wrong account;
>   - Graphite reaching the validator over the signed intake instead of
>     loading it in-process.
> - After that, run every step as `carbon-producer`, never as `carbon`.

## A. Create the rotating hidden pool, `graphite-hidden-battery-v1`

This is a separate deployment from the testnet deployment that holds EV5 and
`graphite-confirmation-v1`, so Graphite's adaptive submissions never rotate or
burn the testnet pool.

1. **Write the configuration**, an owner-only file
   (`chmod 600 graphite-hidden-battery-v1.json`):

   ```json
   {
     "schema": "carbon.battery.validator-deployment.v1",
     "state": "<DIR>/state.sqlite3",
     "private_root": "<DIR>/root.bin",
     "journal": "<DIR>/journal.jsonl",
     "work": "<DIR>/work",
     "backend": "carrier",
     "image_manifest": "<the pinned JAX worker image manifest>",
     "rule": "v2",
     "require_commitment": false
   }
   ```

   - Rule v2 seals hidden-batch results from the submitter, which is what
     VALIDATOR-13 requires.
   - Graphite's development identities have no chain commitment, so this
     deployment does not require one. Testnet's miner-facing deployment does.
2. **Create the root, once:**

   ```bash
   python -m carbon.battery.operate init --config graphite-hidden-battery-v1.json
   ```
3. **Prepare the batches:**
   - four screening batches: three active, one ready for the first rotation;
   - two finalist batches: the winner rerun consumes one per run (§6).

   ```bash
   python -m carbon.battery.operate prepare --config graphite-hidden-battery-v1.json --role hidden-screen-001 --kind screening
   ```

   Repeat for `hidden-screen-002` to `-004`, then
   `--role hidden-final-001 --kind finalist` and `hidden-final-002`.
   - Each command prints the batch fingerprint.
   - Count the batches a run needs before it starts. Under rule v2 a batch
     rotates every 1,080 blocks (about 3.6 h), and an overdue rotation keeps
     scoring but is reported separately, never ranked.
4. **Solve and ingest each batch's references:**

   ```bash
   python -m carbon.battery.operate jobs --config graphite-hidden-battery-v1.json --batch <FINGERPRINT> --out <WORK>/jobs-<FP>.json
   ```

   - Solve in the pinned truth image, exactly as
     `docs/development/BATTERY_VALIDATOR_SERVICE_RUNBOOK.md` describes
     (`truth-materialize` once, then the solve). This is host CPU with no
     network.
   - Then ingest:

   ```bash
   python -m carbon.battery.operate ingest --config graphite-hidden-battery-v1.json --batch <FINGERPRINT> --records <RECORDS>
   ```
5. **Open the pool:**

   ```bash
   python -m carbon.battery.operate open --config graphite-hidden-battery-v1.json
   ```

## B. Seal and solve the tuning set, `graphite-tuning-v1`

> **Superseded by B2.** `graphite-tuning-v1` is never sealed (VALIDATOR-17's
> v2 amendment). Use B2, on the hidden VM only.

The tuning set is sealed in the **testnet** deployment, which holds EV5 and
`graphite-confirmation-v1`. That lets the seal check both by regeneration. It
is also checked against:
- every published case (TRAIN and PRACTICE included);
- every committed engineering-value study's decision cases;
- the rotating pool, as an operator-supplied private prior.

6. **Export the rotating pool's case inputs**, as an owner-only prior file:

   ```bash
   python -m carbon.challenge_validator.tuning export-pool --config graphite-hidden-battery-v1.json --out <PRIVATE>/hidden-pool.json
   ```
7. **The practice decision set** (PRACTICE-SAFETY-01's B4) is public and is
   not committed yet, so it does not block the seal. Step 10 re-checks it
   once it exists.
8. **Seal.** This prints only the public commitment: save it as
   `<PRIVATE>/tuning-commitment.json`, with keys `fingerprint` and
   `journal_sequence`.

   ```bash
   python -m carbon.challenge_validator.confirmation seal --role graphite-tuning-v1 \
     --config <TESTNET_DEPLOYMENT>.json \
     --prior graphite-hidden-battery-v1-pool=<PRIVATE>/hidden-pool.json
   ```
9. **Solve, predict and score**, on the operator host only:

   ```bash
   python -m carbon.challenge_validator.tuning jobs --config <TESTNET_DEPLOYMENT>.json --commitment <PRIVATE>/tuning-commitment.json --work <TUNING_WORK>
   python -m carbon.challenge_validator.tuning solve --work <TUNING_WORK> --overlay <TRUTH_OVERLAY>
   python -m carbon.challenge_validator.tuning predict --work <TUNING_WORK> --panel <PANEL>.json
   python -m carbon.challenge_validator.tuning score --work <TUNING_WORK>
   ```

   - The panel file lists `{member, kind, strategy, seed}` for Graphite's
     constructions, EV4's 100 recipes and any constructed controls. The
     scorer adds the synthetic controls itself.
   - `scores.json` and `rows/<member>.json` stay in `<TUNING_WORK>`, owner-only.
     Weightings are re-scored from `rows/` without retraining.
10. **When B4 is committed, re-check it** against the sealed set:

    ```bash
    python -m carbon.challenge_validator.tuning recheck --config <TESTNET_DEPLOYMENT>.json --commitment <PRIVATE>/tuning-commitment.json --public <B4 FILE> --work <TUNING_WORK>
    ```

    - The command prints only a verdict and a count, never which cases.
    - On `OVERLAP_RESELECT_PUBLIC_SET`, B4 is reselected, never the tuning set.
    - Record the verdict, the B4 file's SHA-256 and the date in the tuning
      set's record (`.agent/tickets/VALIDATOR-17_battery_tuning_set.md`).

## B2. Seal and solve `graphite-tuning-v2`, with its quiz (on the hidden VM only)

The tuning set and its quiz are never sealed on the PC
(`HIDDEN_HOST_SETUP.md` §6). Run every command on the VM as `carbon-producer`,
against the hidden deployment `H`
(`/var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json`). Each
`<…>` directory is owner-only and outside the checkout.

1. **The priors** (VALIDATOR-17 v2):
   - **The rotating pool,** on the VM:
     `python -m carbon.challenge_validator.tuning export-pool --config H --out <P>/hidden-pool.json`.
   - **EV5 and `graphite-confirmation-v1`,** on the PC, by Ryan only, from
     the testnet deployment that holds them:

     ```bash
     python -m carbon.challenge_validator.confirmation export-prior --role ev5-confirmation --config <TESTNET C1> --out <file>
     python -m carbon.challenge_validator.confirmation export-prior --role graphite-confirmation-v1 --config <TESTNET C1> --out <file>
     ```

     `scp` both to `<P>/` on the VM, then `shred -u` the PC copies.
2. **Seal the main set** (200 + 4, uniform), with each prior as a `--prior
   name=FILE` (the names `graphite-tuning-v2.json` registers):

   ```bash
   python -m carbon.challenge_validator.confirmation seal --role graphite-tuning-v2 --config H --prior ...
   ```

   Save the printed commitment as `<P>/tuning-commitment.json`.
3. **Draw the quiz,** in its own work directory `<Q>`, separate from the
   tuning work directory `<W>`:

   ```bash
   python -m carbon.challenge_validator.tuning quiz-jobs --config H --work <Q>
   python -m carbon.challenge_validator.tuning solve --work <Q> --overlay <TRUTH_OVERLAY>
   python -m carbon.challenge_validator.tuning quiz-refine --work <Q>
   python -m carbon.challenge_validator.tuning solve --work <Q>/refine --overlay <TRUTH_OVERLAY>
   python -m carbon.challenge_validator.tuning quiz-select --work <Q> --panel <P>/panel.json
   ```

   - Each Q3 scenario is solved on the 117-point lattice.
   - **`quiz-refine`** (quiz-registry-v8) writes `<Q>/refine/jobs.json`: a
     refined solve for every lattice point whose standard reference is
     within one contract band of a limit. It prints the refine count per
     scenario and the total. The second `solve` runs them in the same pinned
     truth image.
   - `quiz-select` judges each scenario on its settled references: the
     refined truth where the refined solve is OK, the standard reference
     otherwise. The quiz records each scenario's `refine_points`,
     `refined_ok` and `residual` (points still UNRESOLVED), counts only.
   - **`tuning_quiz_needs_refine`:** a refine point has no refined record.
     Run `quiz-refine` and `solve --work <Q>/refine` (again), then
     `quiz-select`.
   - **If `quiz-select` refuses with `tuning_quiz_needs_more_q3`:** run
     `quiz-jobs --round <N>` with the round it names, `solve`, `quiz-refine`
     and `solve --work <Q>/refine` again, then `quiz-select`. Each round adds
     4 Q3 conditions; infeasible ones are redrawn and counted.
   - **`tuning_quiz_panel_incomplete`:** rerun `quiz-select`, which retries
     the panel members that failed to rebuild.
   - **`tuning_quiz_q2_pool_short`:** stop and tell the Test Lead. Q2 is
     never redrawn.
4. **Seal the quiz:**
   `python -m carbon.challenge_validator.tuning quiz-seal --config H --work <Q>`.
   It journals the quiz's digest, counts and panel version, and prints
   `{digest, journal_sequence}`.

   **Q3 v8 design reports (DEVELOPMENT, after the seal).** On the AX42,
   the owner runs these as `carbon-producer`. Replace every `TEST_LEAD_*`
   token with an explicit value supplied by the Test Lead. The commands
   read the owner-only quiz directory and journal without reading the
   private root or writing to the work directory. Each prints aggregate
   JSON only. Check that the `sealed_batch_digest` matches the `quiz-seal`
   digest before interpreting either output.

   ```bash
   sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m carbon.design_search diversity-report \
     --battery-work /var/lib/carbon-producer/tuning/quiz \
     --journal /var/lib/carbon-producer/hidden/journal.jsonl \
     --law /opt/carbon/carbon/battery/value/laws/battery-q3-v8.question-law.v1.json \
     --bootstrap-seed TEST_LEAD_BOOTSTRAP_SEED --replicates TEST_LEAD_REPLICATES \
     --interval-level TEST_LEAD_INTERVAL_LEVEL
   ```

   ```bash
   sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m carbon.design_search power-report \
     --battery-work /var/lib/carbon-producer/tuning/quiz \
     --journal /var/lib/carbon-producer/hidden/journal.jsonl \
     --law /opt/carbon/carbon/battery/value/laws/battery-q3-v8.question-law.v1.json \
     --bootstrap-seed TEST_LEAD_BOOTSTRAP_SEED --replicates TEST_LEAD_REPLICATES \
     --interval-level TEST_LEAD_INTERVAL_LEVEL \
     --alpha TEST_LEAD_ALPHA --power-target TEST_LEAD_POWER_TARGET \
     --severity-edge TEST_LEAD_EDGE_SEVERITY \
     --severity-caution TEST_LEAD_CAUTION_SEVERITY \
     --severity-sign TEST_LEAD_SIGN_SEVERITY \
     --severity-path TEST_LEAD_PATH_SEVERITY
   ```

   Both outputs identify `battery-q3-v8`, the single-condition EV4
   time-to-CV decision, and the seal. The exact view describes only the
   kept eight and is **not a future-batch probability**. The empirical
   view bootstraps the settled accepted draws in `draws.json`, reports
   kept and not-kept separately, and gives a predictive interval. Twelve
   draws are a small sample, so that interval can be wide; later batches
   retain separate seal identities. Protected rejected draws are not
   modeled. No #776 five-condition EV buyer-job result is implied. The
   report uses v8's pessimistic UNRESOLVED outcome rule and prints its
   unresolved count; Test Lead decides any score or power use.
5. **Solve, predict and score the main set and the quiz together:**

   ```bash
   python -m carbon.challenge_validator.tuning jobs --config H --commitment <P>/tuning-commitment.json --work <W>
   python -m carbon.challenge_validator.tuning solve --work <W> --overlay <TRUTH_OVERLAY>
   python -m carbon.challenge_validator.tuning predict --work <W> --panel <PANEL>.json --quiz <Q>
   python -m carbon.challenge_validator.tuning score --work <W> --quiz <Q>
   ```

   `score` writes these, owner-only, in `<W>`:
   - `scores.json` and `rows/`;
   - `quiz-scores.json`: each member's Q2 and Q3 measures (Q3's include
     `unresolved`), judged against the settled references;
   - `q3-regret.json`: each member's mean Q3 decision regret over the
     feasible scenarios. Ryan passes it to Data Collection's `tuning_rescore
     --q3-regret`.

   Nothing leaves the VM except aggregates.

## C. Graphite Level 0 runs through the real validator

This needs #642 (VALIDATOR-13) merged, plus its follow-up: a phase-3 option
that builds the `HiddenPool` from `graphite-hidden-battery-v1.json` with a
finalized-block clock. That follow-up is built after #642 lands. Until then,
section C is not runnable.

## Never

- Never put a root, journal, batch, jobs, records, prediction or score file
  in the repository, a pod, rented compute, the attack knowledge store or a
  Graphite session.
- Never prepare `graphite-tuning-v1`, `graphite-confirmation-v1` or
  `ev5-confirmation` as a pool batch. The validator refuses all three.
