# EPS-01 — Data Collection's producer stages for the evidence campaign

- **Ticket:** EVIDENCE-PRODUCER-STAGES-01 (Test Lead relay, 2026-10-11: Data
  Collection owns the motor reference entrypoint and the reference/TRAIN
  stage interface; the optimizer owns the assembler).
- **Problem:** #1080 refuses public execution while no registered stage turns
  the merged entrypoints (#1077, #1078) into `--context`/`--output` receipts
  and sealed panel exports.
- **Working decision:** one pinned stage module,
  `carbon.development_comparison.campaign_adapters.producer`, for the battery
  v3, motor and f02 `reference` and `train` phases. It has frozen v1 artifact
  names, roles and schemas, and cgroup-v2 metering. The battery and f02
  exports seal producer-computed per-candidate settlement; the f02 export is
  new. The contract, and the f02, settlement and #965 refinement choices, are
  in `docs/development/challenge_pipeline/evidence-producer-stages.md`.
- **Test Lead decision recorded:** f02 reference = menu v2 (16 × 24). The
  nine-action registration stays as history, and the optimizer revises
  equal-budget and `adaptive_arms` prospectively.
- **Deferred:** the motor reference stage refuses until its reference-panel
  plan lands after the amendment-4 results.
- **Alternatives rejected:**
  - host paths as reuse (not reproducible on a server);
  - JSONL artifacts (the runner reads one JSON document per artifact);
  - host `RUSAGE_CHILDREN` alone (container CPU is not counted);
  - variant f02 questions (the registry refines only near 95 C).
- **Invariants:** no hidden material, and no candidate failure from a
  reference or infrastructure failure. No invented limits: requirement laws
  stay HUMAN_INPUT/UNREGISTERED. The runners are unchanged unless
  `CARBON_STAGE_CGROUP_PARENT` is set.
- **Reversibility:** new modules plus opt-in hooks; `v3_panel_export.build()`
  defaults are unchanged.
