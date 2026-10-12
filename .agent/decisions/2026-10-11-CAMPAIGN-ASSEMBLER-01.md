# CAMPAIGN-ASSEMBLER-01 — producer custody before comparison assembly

- **Ticket:** CAMPAIGN-ASSEMBLER-01, development only.
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
- **Unresolved assembly input:** #1114 does not emit a model-prediction receipt,
  comparator calibration material, per-candidate measured solver cost and
  proposal history, replay bindings, fold registration or an adaptive policy.
  These cannot be inferred from a sealed reference value without inventing a
  model, competitor or cost. The affected comparison assembly stays fail closed
  until its source route is registered. Synthetic fixtures exercise the
  boundary without creating public evidence.
- **Integration seam:** #1114 currently rejects `vcpus` in its closed context
  and reads `OMP_NUM_THREADS` instead. Data Collection must accept the explicit
  field and verify it equals the environment allotment before the producer
  stage can run under the revised runner.
- **Invariants:** no hidden material, no TRAIN access to held-out reference,
  byte-pinned source identity, reference/infra failure separation, no fixture
  qualification, no spend or solver execution by this ticket.
