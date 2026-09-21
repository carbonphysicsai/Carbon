# GPU validator admission through the host record (work package P)

Ticket: C-CORE-19. Branch `agent/core-platform-19-gpu-lane-split`.
Authority: `docs/development/GPU_VALIDATOR_ADMISSION_DECISION.md` on
`agent/gpu-execution-lane-design` (PR #248), recorded 2026-09-21, programme #209.

`VALIDATOR_DEPLOYMENT_PATH.md` (work package N, item N4) classified GPU
`VALIDATOR_RECONSTRUCTION` as `NEW_OWNER_DECISION_REQUIRED` and stated the
smallest decision. The owner decided it. This records what changed.

---

## 1. The decision, and what it rests on

> GPU `VALIDATOR_RECONSTRUCTION` admits through the host record and `doctor`, the
> same path the miner lane uses. It does not require an owner-signed grant or an
> exclusive lease.

The engineering-relevant part of the reasoning is that **exclusivity was never
the mechanism delivering reproducibility**. D3 measured that pinning the
execution configuration is: three sessions, nine runs, one digest, against four
unpinned sessions producing four digests. A validator holding a device
exclusively without applying the pinned configuration still gets four digests.

N2 is the first direct evidence on contention and points the same way - eighteen
runs across nine configurations, including two simultaneous runs on disjoint core
sets, produced one weight digest. That is CPU, and GPU contention remains
untested; it points away from exclusivity rather than establishing that
contention is harmless.

---

## 2. P1: the dispatch change

`controller.execute()` routed `MINER_RESEARCH` to self-service admission and
everything else to `AcceleratorHostAdmission.load()` and `exclusive_lease()`.
Both GPU roles now take the self-service path.

**The strict apparatus was neither removed nor extended.** It stays in the tree
and is no longer reached by either role. `STRICT_HOST_GRANT` and
`LOCAL_DEVELOPMENT_APPROVAL` remain the two never-interchangeable authorities
they were, and no third "validator self-service" authority was invented - that
would have been precisely the relaxed variant of the strict grant the decision
forbids. The existing self-service authority string is reused unchanged, so every
record written before the decision keeps its exact previous meaning and digest.

### Two things the dispatch change forced, which the decision did not spell out

**The lane had to stop being a literal.** The worker profile hardcoded
`lane: MINER_CONTAINED`, which was indistinguishable from the rule while only a
miner could reach that branch. It now comes from `lane_for_role()`.

**The validator body had to be its own schema version.** `v5` has only ever
meant a miner-lane run, and every `v5` record already written is one. Widening it
in place would have silently changed what those records assert to a consumer
reading the version, so the validator body is
`carbon.c03.development-worker-profile.v6`. A miner run stays byte-identical.

**And the assurance label had to change.** The miner label carries
`verification: DOWNSTREAM_VALIDATOR_RECONSTRUCTION`, which is nonsense on a
validator's own run - there is no downstream validator to verify it. The
validator label carries `BACKEND_QUALIFICATION_REQUIRED_MQ008` instead. Its
`established` and `not_established` facts are *identical* to the miner label's,
because the admission is identical; claiming more would assert the guarantee the
decision declined to require.

`official_eligible`, `validator_grade` and `strict_equivalent` are all `False`,
so `assurance_permits_official_use()` returns `False`. **Admission is not
qualification.** `compare_r1` still returns `BACKEND_UNSUPPORTED` while the
backend profile is not `SUPPORTED`, and MQ-008 at G4 owns that.

---

## 3. P2: contention recorded, not required away

The decision declines to require exclusivity. It does not claim contention is
harmless, so the numerics record makes it checkable later:
`carbon.reconstruction.numerics-environment.v2` adds device memory in use and
limit, a compute-process count, and the state that governs both.

| `device_process_enumeration` | Means |
| --- | --- |
| `OBSERVED` | The query succeeded. A count of zero here does mean zero. |
| `UNAVAILABLE` | The host could not be asked. WDDM cannot enumerate at all. |
| `NOT_APPLICABLE` | No device; the question does not arise. |

**`UNAVAILABLE` is never collapsed into "nothing else was running."** Under
anything but `OBSERVED` the count is absent rather than zero. An absence of
evidence is not evidence of absence, and only the second would license a
conclusion about contention. A successful query returning no rows *is* an
observation of zero, which is exactly why the states must stay distinct; an
unparseable response leaves the whole fact unavailable rather than producing a
count nobody can defend.

This is provenance, not attestation - the same standing Amendment 3 C4
established for the rest of the numerics record.
`ESTABLISHED_OBSERVATION_CONTRACTS` stays empty. v1 remains readable and
unchanged in meaning: a v1 record does not assert the device was idle, it
predates anyone asking.

---

## 4. P3: the deployment path, and one honest gap

The `NEW_OWNER_DECISION_REQUIRED` block is removed and §7 now records the
decision, its reasoning, and what it does not do.
`VALIDATOR_GPU_DETERMINISM_POLICY.md` §3 and §7 are reconciled with it.

**The gap, stated rather than papered over:** `carbon_accelerator.py run` is the
miner-lane launcher and deliberately only that - its role is fixed to
`MINER_RESEARCH` and is not a parameter, because a caller that could choose the
role could choose the lane. **No shipped caller constructs
`VALIDATOR_RECONSTRUCTION` at all.** The decision unblocked admission for it; the
orchestration that would drive it is separate work and is not in this tree.

So for a validator host today, §1-§3 and §6 of the deployment path apply and §4's
command does not. That is written into the document at the point an operator
would otherwise run it and get a miner-lane record back.

---

## 5. P4: tests

`tests/cpu/test_validator_self_service_admission.py`, 18 cases, including the two
the decision named by name:

- **`test_the_validator_role_does_not_require_a_grant`** reads the dispatch
  itself and fails if the validator role returns to the strict branch.
- **`test_unobservable_contention_is_never_recorded_as_an_observed_absence`**
  fails if a fact that could not be observed is recorded as an observed absence.

Two existing tests in `test_gpu_execution_lanes.py` encoded the *previous*
decision and were rewritten rather than deleted, because the invariants beneath
them survive:

- `test_the_miner_authority_is_the_miner_role_only` asserted a validator could
  never carry self-service authority. It now asserts what was always
  load-bearing: neither role can select the *other's* lane by choosing an
  authority value.
- `test_a_refused_strict_admission_does_not_become_a_miner_run` asserted a
  grantless validator fails `UNAVAILABLE`. It now asserts the opposite for the
  same reason - `UNAVAILABLE` is what loading an absent grant produces, so its
  *absence* is the evidence the strict path was not entered.

---

## 6. P5: the integration

`origin/main` at `0e10555e` merged into the branch. All six conflicts were Hub
files; none touched source, evidence or measured values. `change_events.json` was
resolved structurally rather than textually - the append-only log is the union by
`event_id` over the common base of 207.

Verified across the merge: both sides are **pure appends**, neither edited an
existing event payload, so taking either side's list for shared ids lost nothing.
`GOAL-WORKBENCH-12-D1` is retained byte-identical from main with its
impact-policy owner; `C-CORE-19-ALLOCATION-01` and `C-CORE-19-SNAPSHOT-03` are
retained byte-identical. The two genuinely #251-only events -
`C-MLP-02-EXAM-DISCLOSURE-01` and `C-MLP-02-MINER-LANE-01` - are **absent**, as
they must be until that work lands.

All 15 C-CORE-19 source, evidence and document files were verified byte-identical
through the merge. The snapshot repin touched only links already at the previous
current snapshot; all 232 links frozen at `4f84329c` were left alone.

---

## 7. Maturity

| Item | State |
| --- | --- |
| P1 admission dispatch | IMPLEMENTED, TESTED |
| P2 contention observations | IMPLEMENTED, TESTED |
| P3 deployment path | SPECIFIED, reconciled |
| P4 tests | TESTED |
| P5 integration | delivered |

Nothing here is SCIENTIFICALLY_QUALIFIED, SECURITY_QUALIFIED or
PRODUCTION_QUALIFIED. No hardware is qualified, no tolerance is set, no threshold
changed, no GPU attempt was spent, and the observation registry stays empty.
Admitting a validator is not qualifying a backend.
