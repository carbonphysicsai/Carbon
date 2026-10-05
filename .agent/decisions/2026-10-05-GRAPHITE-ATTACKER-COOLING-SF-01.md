## 2026-10-05 — GRAPHITE-ATTACKER-COOLING-SF-01: cooling's selective-crash probe

**Amends:** GRAPHITE-ATTACKER-COOLING-L0
(`.agent/decisions/2026-10-04-GRAPHITE-ATTACKER-COOLING-L0.md`, merged in
#587). That record is not edited; this one adds to it.

**Authority:** OWNER-GRAPHITE-ATTACKER-01 and the owner's approval of the
cooling adapter as part of full Graphite testing (OWNER-GRAPHITE-TEST-WAVE-01..03).
The probe was specified by the Test Lead: #586 types a candidate's numerical
fault as FAILED_INFRA (`adapter_failure`), never a score; can a construction
fault only on the cases where it would score badly and so dodge them?
Engineering decisions inside that scope. No scientific value, threshold,
tolerance, weighting, attribution policy or validator behaviour is chosen or
changed here.

**Files:** `carbon/agent_campaign/attack/adapters/cooling.py`,
`tests/cpu/test_attack_cooling_adapter.py`,
`carbon/challenge_pipeline/lessons/2026-10-05-attacker-cooling-selective-fault.json`.
Read only: the validator (`carbon/challenge_validator/`), `pod_outcome.py`,
`attribution_policies/`, `experiment.py`, `pods.py`, `carbon/cold_plate/`.

### COOL-SF-D1 — The family

A sixteenth family, `selective_fault`, under `resource_and_failure_accounting`.
Its construction is Carbon's own Level 0 kernel-ridge fit of the recipe on the
pinned public TRAIN bytes, faulting at its predict step on cases chosen from
its own error on the public PRACTICE references (which a miner sees):

| Attack | Fault | Cases |
|---|---|---|
| `fault_on_the_hot_group_only` | raise | the hot group (reference peak at least `T_IMPORTANT_C`) |
| `fault_on_the_worst_k_cases` (example) | raise | its worst tenth |
| `nonfinite_only_on_the_hard_cases` | NaN peak | every case worse than its own mean |
| `raise_at_predict_for_a_subset` | raise | its worse half |
| `infinite_pressure_on_the_worst_k_cases` | infinite pressure drop | its worst tenth |

Every attack is run through both real paths:

- **Interface v1** (#586): a private temporary store holding the pinned public
  PRACTICE references, then `Validator.evaluate` (strict parse, dispatch,
  `CoolingAdapter.evaluate`, outcome contract) with the construction faulting
  (the model `cold_plate.compile.rebuild` builds, through the `build` name it
  reads), then the same submission again, to see whether a FAILED_INFRA
  re-rolls.
- **Graphite's pod path** (#584): `experiment.Experiment.run` at Level 0 with
  the registered attribution policy and cooling's `ChallengeScoring`, on a
  scripted pod account that runs no pod and spends nothing. The pod's exports
  come from Carbon's own practice program (`practice.PROGRAM`) from its model
  onward, run on the construction exactly as written, exported as
  `pod_phase.run` exports it (`failure.json` at stage `program` on a non-zero
  exit). The session's honest baseline runs first, as on every run.

The vulnerable specimen (`dropping_accounting`) drops every faulted case from
the aggregate and scores the rest. A path *dodged* when it scored the attempt,
eligible, over fewer cases than it was given. Controls: trained, the
legitimate construction (scored over every case on both paths); held out, the
legitimate `length_4` construction, and a construction that faults on every
case uniformly, by raising (failed as a whole on both paths) or with a NaN
peak (failed as a whole on Interface v1, ineligible on Graphite).

### COOL-SF-D2 — Verdict: HELD on both paths

No attack dodges a case. The faulted cases would improve the construction's
score by being dropped (honest score 0.098762; without the hot group 0.083246,
without its worst tenth 0.076850, without its above-mean cases 0.060581,
without its worse half 0.051390), and instead:

| Path | A raise on the chosen cases | A non-finite output on them |
|---|---|---|
| Interface v1 | `FAILED_INFRA` / `adapter_failure`: the dict comprehension in `CoolingAdapter.evaluate` raises, nothing is scored or stored | `FAILED_INFRA` / `adapter_failure`: the score record's NaN or infinity is not JSON, so `record_submission` raises; nothing is scored or stored |
| Graphite pod path | `CANDIDATE_FAILED` / `program` (the pod program dies before writing predictions; Level 0 is a trusted writer), never retried | `SCORED`, ineligible: every faulted case is a `schema_finite` gate failure; the comparison reads REGRESSION |

Evidence digests (oracle `evidence_digest`, binding the faulted cases, the
score with and without them and each path's outcome):
`fault_on_the_hot_group_only` sha256:88a0ffd0…,
`fault_on_the_worst_k_cases` sha256:7773872b…,
`nonfinite_only_on_the_hard_cases` sha256:53219145…,
`raise_at_predict_for_a_subset` sha256:3f6ea754…,
`infinite_pressure_on_the_worst_k_cases` sha256:fba4aa76…
(recomputed by `test_the_selective_fault_evidence_is_digest_bound`).

**Re-roll.** An Interface v1 FAILED_INFRA leaves no submission row, so the same
submission is evaluated afresh; the rebuild is deterministic, so it fails the
same way (the ledger holds two FAILED_INFRA rows). Graphite never reruns a
proposal's program crash; only a timeout is retried, once, under the
attribution policy, with the same seed.

### COOL-SF-D3 — What the verdict rests on, and what it does not cover

The hold rests on Carbon's harnesses having no per-case fault handling: one
fault ends the whole attempt. Two facts are recorded for the owner, not
changed:

1. **Interface v1 does not charge a candidate's numerical fault.** A Level 0
   recipe whose fit raises or emits a non-finite value gets FAILED_INFRA
   (`adapter_failure`, invariant 7's infrastructure type), not an ineligible
   SCORED outcome, and may be resubmitted. It dodges no case and gains no
   score, so it is not a breach; whether such an attempt should be charged to
   the candidate is an owner/policy decision.
2. **A missing prediction is excluded on both paths** (new NOT_RUN seam
   `missing_prediction_attribution`). `exam.evaluate_case` types a case with
   no prediction FAILED_INFRA and `exam.aggregate` excludes it, and Graphite's
   host scores a pod's `predictions.json` with no check that it holds every
   case. A set that omits its worst tenth stays eligible with score 0.076850
   against 0.098762 on both paths (pinned by
   `test_the_missing_prediction_seam_premise_holds`). No Level 0 construction
   can omit a case, so this is not a Level 0 breach; it becomes one wherever a
   harness catches per-case faults or a participant's own inference writes the
   predictions (Levels 4-5). Reserved: whether a case without a prediction
   from the construction's side is excluded or charged, and whether Carbon's
   hosts refuse an incomplete prediction set.

Also observed: Graphite's record of an ineligible proposal reports the soft
score over its scorable cases only (0.060581 for the above-mean NaN attack),
better than the honest score; it is ineligible and compared as a REGRESSION,
so nothing is gained.

### COOL-SF-D4 — Mutations

Each makes an accounting drop faulted cases and turns `selective_fault` red,
patching the name the path reads:

| Mutation | Patched | Breaches |
|---|---|---|
| `faulted_case_typed_failed_infra` | `carbon.cold_plate.exam.evaluate_case` (a non-finite prediction typed FAILED_INFRA) | the two non-finite attacks, on Graphite (Interface v1 still fails on the record) |
| `validator_harness_drops_a_faulted_case` | `carbon.challenge_validator.cooling.rebuild` (a predict fault becomes no prediction) | the three raise attacks, on Interface v1 |
| `practice_program_drops_a_faulted_case` | `carbon.cold_plate.practice.PROGRAM` (a per-case try/except) | the three raise attacks, on Graphite |

### COOL-SF-D5 — Versions and cost

`ADAPTER_VERSION` and `CONTROLS_VERSION` move to `cooling-l0.v2` (a family,
four controls and a seam were added). The probe opens only temporary files and
the public TRAIN and PRACTICE material (the audit-hook test still passes). It
fits each recipe once per process (`_FITTED`, cleared by `clear_caches`); a
family run takes about ten seconds.

### COOL-SF-D6 — Battery

Battery's Level 0 adapter has no equivalent probe: its `resource_accounting`
judges only a partial prediction set's typing and explicitly does not judge
whether such a set may stay eligible
(`carbon/agent_campaign/attack/adapters/battery.py:885-898`, `resource_breached`;
the family at `:1388`), and the omission surface is left to its Level 5 seam
(`:1626`). Battery is not changed here.
