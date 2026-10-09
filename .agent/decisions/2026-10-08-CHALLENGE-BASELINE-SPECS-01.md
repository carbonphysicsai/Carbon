# CHALLENGE-BASELINE-SPECS-01 — strong cheap baseline comparison

**Ticket:** CHALLENGE-BASELINE-SPECS-01. **Status:** working engineering
decision, 2026-10-08.

The owner's V4 analysis needs the buyer's strongest cheap existing method,
not a deliberately weak comparator. The eight method classes are a cached
interpolated charge map (battery), magnetic response surface (motor),
thermal/hydraulic surface (cooling cell), compact transient RC network (f02),
direct 2D optimizer (f06), cached modal basis (f08), transfer/retained-mode
acoustics (f13) and CFD-trained response surface (f17). Each comes from a
source describing that method class. These are proposed challengers, not
measured strongest implementations or claims of named-buyer adoption.

The comparison uses only permitted fit material, holds out solved reference
banks by cluster, commits predictions before evaluation, charges construction
and inference/verification, and reports decision agreement at matched
admissibility. This is preferable to comparing Carbon's inference latency
against only a cold reference solve or to crediting a baseline's cached work
as free. The owner/Test Lead retains all adoption thresholds, scientific
adequacy, and V4 judgment. Data Collection can supersede a proposed baseline
with a stronger demonstrated cheap method without changing the buyer task.

Implementation is documentation under
`docs/development/challenge_pipeline/value-cost/`; no runtime interface or
historical evidence changes. Reversal is a prospective spec revision, not a
rescore. If a lead disagrees, the smallest change is to replace the affected
Challenge's baseline section and rerun its matched measurement plan. No
human-reserved numeric value is selected here.
