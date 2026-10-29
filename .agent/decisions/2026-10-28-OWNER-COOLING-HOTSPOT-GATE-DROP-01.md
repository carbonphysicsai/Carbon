# OWNER-COOLING-HOTSPOT-GATE-DROP-01 (2026-10-28)

- **Owner, in chat:** "Yes on A". This approves option A of codex-queue/reports/COOLING_HOTSPOT_GATE_DECISION_20261028.md: drop the rise~hotspot_ratio sign gate and its exponent from the next Cooling version.
- **Evidence:** on solver truth (12 Cooling 1.4 probe rows, truth-sign12.json sha256:644976355e1cf69f8fee4dd10436b14e1cf7d98ac48eb45b78816e3b051c8488) the mean slope is +0.089, but 2 of 4 groups are negative. Each |d_rise| is 5-7 times the reference uncertainty, so the relation is not monotone across the box.
- **Scope:** the next Cooling version only, with no silent rescoring of earlier versions. Option A+ (the solver's local slope, F02 route) remains a later candidate. Re-run the Cooling TRAIN selection under the corrected gates. Apply the same truth check to every other sign gate on every Challenge.
