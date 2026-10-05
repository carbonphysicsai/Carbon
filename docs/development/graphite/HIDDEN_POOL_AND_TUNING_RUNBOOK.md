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

The tuning set is sealed in the **testnet** deployment, which holds EV5 and
`graphite-confirmation-v1`. That lets the seal check both by regeneration. It
is checked against the rotating pool and the practice decision set as private
priors.

6. **Export the rotating pool's case inputs**, as an owner-only prior file:

   ```bash
   python -m carbon.challenge_validator.tuning export-pool --config graphite-hidden-battery-v1.json --out <PRIVATE>/hidden-pool.json
   ```
7. **The practice decision set's inputs** go in an owner-only file of the
   same shape (`{"cases": [{"inputs": {...}}]}`). Its source is pending the
   Test Lead's answer; until that file exists the seal refuses (fail closed).
8. **Seal.** This prints only the public commitment: save it as
   `<PRIVATE>/tuning-commitment.json`, with keys `fingerprint` and
   `journal_sequence`.

   ```bash
   python -m carbon.challenge_validator.confirmation seal --role graphite-tuning-v1 \
     --config <TESTNET_DEPLOYMENT>.json \
     --prior graphite-hidden-battery-v1-pool=<PRIVATE>/hidden-pool.json \
     --prior practice-decision-set=<PRIVATE>/practice-decision-set.json
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
