## 2026-10-08 — GRAPHITE-STUDY-GRANT-BINDING-01: SUBMISSION-RATE-STUDY-01's grant spends only through its study

**Authority.**
- **The grant.** OWNER-RATE-STUDY-TOKENS-01 (#852). Its third binding
  condition says the runner must bind GRAPHITE-GRANT-RATE-STUDY-TOKENS to the
  study's route, and the grant file alone spends nothing.
- **The design.** The Test Lead accepted it on 2026-10-08:
  - a `STUDY_GRANTS` registry keyed by study ID;
  - G-sealed runs launch through the existing phase-3 runner with
    `--study SUBMISSION-RATE-STUDY-01`.

  This is an engineering change. It grants nothing, and it moves no threshold.

**Decision.**
- **The registry.** `grant_binding.STUDY_GRANTS` binds
  SUBMISSION-RATE-STUDY-01 to:
  - its grant, on battery, as main's committed blob;
  - the record's limits: ceiling USD 30.00, USD 4.91 a run, 6 runs,
    39,600 s and 144 submissions;
  - the plan's arm caps: 36, 72 and 144.
- **`check_study_grant` refuses, typed:**
  - an unbound run, `grant_is_not_bound_to_study`: no study named, an
    unregistered study, or another grant;
  - another Challenge;
  - any limit that differs from the record;
  - a submission cap that is not a frozen arm cap, or that exceeds the
    grant's;
  - a grant that is not main's committed blob.
- **The study grant is refused outside its study.** `check_phase3_grant`
  refuses it as `grant_is_bound_to_a_study`, so a battery phase-3 run cannot
  spend it.
- **The runner.**
  - `phase3 run` gains `--study` and `--study-submission-cap`. The run sheet
    copies the cap from the frozen `freeze-manifest.json`.
  - The grant is tokens-only (`TOKENS_ONLY_GRANTS`), so every pod launch is
    refused `grant_allows_no_pods`.
- **Enforcement after binding.** Once bound, the campaign controller
  enforces the grant's ceiling, per-run reservation, run count and wall-clock,
  as for every grant.

**Not claimed.**
- **The cap is not checked against the manifest.** The runner validates it
  against the plan's arm caps only. The manifest's schema is not frozen yet,
  and reading it is a follow-up.
- **The controller counts submissions per ledger, not per run.** Its limit
  is the grant's 144, across every run that shares a controller root. The
  plan gives each Graphite-adversary run its own controller root (#845).
