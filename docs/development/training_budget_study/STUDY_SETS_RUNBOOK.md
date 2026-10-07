# Training-budget study sets: operator runbook

The tool is `carbon.challenge_validator.study_sets` (TRAINING-BUDGET-01
slice 2b). It makes the study's three sets for one Challenge: the nested TRAIN
sets for Phase G, the study evaluation set, and the sealed confirmation set
for Phase D. The spec is `docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`.

## On the producer host only, as carbon-producer

Run every step on the producer VM, as the producer's service account (the
S11 lesson). Never run it on a pod, a laptop or rented compute. The tool
refuses a spec whose `service_account` is not the account running it.

1. **Write the spec.** It is an owner-only JSON file outside the repository
   (`chmod 600`), with the schema `carbon.training-budget.study-set-spec.v1`
   and exactly these keys:
   - `service_account`: `carbon-producer`.
   - `challenge_id`: the Challenge under study.
   - `study_dir`: a new directory outside the repository, for example
     `/var/lib/carbon/training-budget/<challenge>/study-sets`. It holds the
     study root, the journal and the work files.
   - `truth_overlay`: the materialized truth overlay the producer already
     uses for its solves.
   - `approval`: the owner's record approving the new study seed root, as
     `{"record": "OWNER-...", "file": "<decision file>.md", "sha256": "..."}`.
   - From the Challenge's study sheet: `train_size` (the current TRAIN
     size), `train_size_ladder` (its multiples, increasing) and
     `generation_ceiling`.
   - `eval_cases` and `confirm_cases`: the study evaluation and confirmation
     set sizes.
   - `private_priors`: `{name: path}` for every owner-only prior file. Name
     the live pool, the tuning and confirmation sets and EV5. Each file holds
     `{"cases": [{"inputs": {...}}, ...]}`.
     `python -m carbon.challenge_validator.confirmation export-prior` writes
     a sealed battery set in this form.

   A value left `null` or `"HUMAN_INPUT"` refuses every step that needs it.
   Never fill one in without the owner's record.
2. **Create the study root** once:
   `python -m carbon.challenge_validator.study_sets init --spec SPEC`.
   It prints only the root's public commitment. The root never leaves this
   host.
3. **Draw and commit:** `... draw --spec SPEC`. This draws all three sets
   and checks them for overlap against every published case, every private
   prior and each other. It commits each fingerprint to the study journal.
   An overlap refusal names the prior and commits nothing. Stop the study
   and report it (the spec's stop rule).
4. **References,** for each of `train`, `eval` and `confirm`:
   `... jobs --spec SPEC --set S`, then `... solve --spec SPEC --set S`,
   then `... ingest --spec SPEC --set S`. Re-run `solve` and `ingest` until
   `ingest` says `COMPLETE`, because FAILED_INFRA cases are retried. A
   reference that is not OK is withdrawn for every model and counted in the
   manifest.
5. **Manifests:** `... manifest --spec SPEC --set S` prints public values
   only. They can go into the study's evidence.
6. **Export for the pod:** `... export --spec SPEC --out DIR` writes
   `train.json` and `eval.json` owner-only. Carry them to the study pod over
   the usual key-restricted channel. The confirmation set is never in an
   export.
7. **Release the confirmation set** (runbook step 10), only after the owner
   and tech lead have frozen L and the harness has opened the confirmation
   set. Copy the harness journal from the pod, then run
   `... release-confirmation --spec SPEC --harness-journal PATH --out DIR`.
   It refuses unless that journal records `limit_frozen` and then
   `confirmation_opened` for this Challenge. It releases once. A second
   release is refused.

Every file the tool writes is owner-only. Do not copy the study directory
off the host.
