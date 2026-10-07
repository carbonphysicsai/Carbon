## 2026-10-07 — TRAINING-BUDGET-01 slice 2a: the study harness core

**Authority.**
- **Scope.** TRAINING-BUDGET-01, scope item 3, the study harness. The Test
  Lead's build order puts it second.
- **The spec.** `docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`, under
  the frozen rules R1-R11.
- **The Test Lead's two constraints (2026-10-07).** The study seed root and its
  confirmation set live only on the producer host. The study runs on released
  `worker-images-v1` digests only.

Everything below is an engineering choice within that authority. No rule,
threshold, budget or set size is chosen.

**The split.** Slice 2 ships in three parts:
- **2a:** the Challenge-neutral harness core (this record).
- **2b:** study-set creation (nested TRAIN sets and overlap checks), which
  runs on the producer host.
- **2c:** battery's real executor and the study-only contract, which needs the
  owner's raised study ranges from the sheet.

**Decisions (2a).**

1. **One harness for every Challenge** (`carbon/training_budget/study.py`). It
   plans each phase from the sheet and the adapter's inputs and runs the plan
   through an executor. The records follow the spec's measurement table.
   Phase B's ladder is an engineering choice: from one doubling below the
   default up to the study range's top, doubling each step.
2. **Gates the harness holds itself.**
   - **Order:** Phase A first. B, C, F and G run only after R1 passes, and
     nothing runs after a failed R1. D, E and H run only after the owner's
     frozen L.
   - **Confirmation set:** opened once, after L, and used only by Phase D.
   - **The released image.** It is checked against a `worker-images-vN`
     release record's own reference.
   - **The sheet.** A phase with unset sheet values is refused.
   - **The study root.** It is owner-only and outside the repository.
3. **R1 is applied here, as written.**
   - **Pairs:** every same-seed pair matches in weight and prediction digests,
     including the largest recipe.
   - **Shared GPU:** each shared-GPU pair also matches its lone twin.
   - **Other rules:** R2-R11 belong to the analysis (slice 4).
4. **The ledger** keeps the validator work ledger's semantics in files under
   the study root.
   - **Dispatch:** a run is reserved before dispatch, and its record is written
     once. A finished run is never repeated.
   - **Crashes:** a reservation left by a crash blocks the study until it is
     reconciled to FAILED_INFRA, and the retry is a new attempt.
   - **Failure classes:** infrastructure failure is never recorded as the
     candidate's.
5. **Reconstruction seeds** come from each run's public identity, not from
   the study seed root: they are rebuild randomness, not case data. A
   same-seed pair shares its seed.
6. **The journal** (`journal.jsonl`) is append-only. It records the opening
   (sheet digest, image, release tag), each plan's digest, the R1 result, the
   frozen L and the confirmation set's single use.

**Tests.** `tests/cpu/test_training_budget_study.py` uses fake rebuilds on two
synthetic Challenges. It covers:
- an end-to-end run of Phases A and B;
- R1 pass and fail, including a shared-GPU run against its twin;
- every gate and the confirmation set's single use;
- the ledger: no repeats, crash reconciliation, and infrastructure kept apart
  from candidate failures;
- incomplete records, unreleased images and the owner-only root;
- every phase's plan.
