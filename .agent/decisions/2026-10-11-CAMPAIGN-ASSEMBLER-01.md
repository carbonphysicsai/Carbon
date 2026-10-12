# CAMPAIGN-ASSEMBLER-01 — producer custody before comparison assembly

- **Ticket:** CAMPAIGN-ASSEMBLER-01, development only.
- **Primary hub map_ref:** `WAVE-C/EVIDENCE-CAMPAIGN-RUNNER-01`. This bounded
  assembly slice does not change the hub's purpose, placement, maturity or
  authority ceiling; the merged producer contract and remaining gaps are
  recorded here and in the runner specification.
- **Authority:** EVIDENCE-CAMPAIGN-RUNNER-01 (#1080), Data Collection's
  EVIDENCE-PRODUCER-STAGES-01 frozen draft (#1114), #975 comparison and #1056
  adaptive arm contracts. Data Collection owns reference solves and TRAIN;
  this ticket owns the trusted comparison assembly and runner context.
- **Working decision:** accept a sealed solved-panel export only through a
  byte-pinned `HELDOUT_REFERENCE` stage receipt and kit rows only through a
  byte-pinned `PUBLIC_TRAIN` stage receipt. Require their exact plan, family,
  stage, role, entrypoint and summary identities before any comparison output.
  Pass the registered `vcpus` allotment in every runner stage context. On a
  timeout or cap, send SIGTERM and allow a short grace before SIGKILL of the
  process group, including surviving children.
- **Ticket-start state, superseded below:** #1114 did not emit a model-prediction receipt,
  comparator calibration material, per-candidate measured solver cost and
  proposal history, replay bindings, fold registration or an adaptive policy.
  These cannot be inferred from a sealed reference value without inventing a
  model, competitor or cost. The affected comparison assembly stays fail closed
  until its source route is registered. Synthetic fixtures exercise the
  boundary without creating public evidence.
- **Ticket-start integration seam, superseded below:** #1114 rejected `vcpus` in its closed context
  and reads `OMP_NUM_THREADS` instead. Data Collection must accept the explicit
  field and verify it equals the environment allotment before the producer
  stage can run under the revised runner.
- **Invariants:** no hidden material, no TRAIN access to held-out reference,
  byte-pinned source identity, reference/infra failure separation, no fixture
  qualification, no spend or solver execution by this ticket.

## 2026-10-12 producer-contract update

#1114 has merged with registered `vcpus`, candidate view, cost ledger, model
predictions and receipt, plain bindings, motor/f02 comparator material, and
f02's separately pinned fine peak witness. Assembly now validates these names,
roles, receipt hashes, identities and inventories; it builds a replay design
and value context from them on synthetic fixtures. The fine 0.02 s witness
checks the peak while the 0.5 s material remains the FIR fit grid (128 lags).

**Remaining real-run gaps:** #1056 requires an adaptive policy calibrated on
independent PUBLIC_TRAIN jobs with a receipt proved to predate held-out
execution. The #1114 TRAIN stage follows reference and cannot itself establish
that chronology. Data Collection confirmed on 2026-10-12 that the per-Challenge
`adaptive-policy.v1` registrations do not exist yet. Its future pre-experiment
receipt is the policy PR's merge-commit SHA on main; GitHub's server-side merge
time supplies the independent chronology. The assembler must check the pinned
policy bytes, the separate calibration identity, and that independent receipt
against held-out execution before enabling a real adaptive panel. It does not
accept a locally asserted timestamp or the post-reference TRAIN receipt as a
substitute. Battery's per-physical-row CPU time is unmetered (one-core
wall time is a conservative upper bound), so public equal-budget replay cannot
call it measured. The Carbon receipt times one batched inference, not a full
per-question query, so item-3 speed remains unmeasured. These sub-scopes remain
explicit and fail closed; no comparator or model claim is promoted by a
synthetic fixture.
