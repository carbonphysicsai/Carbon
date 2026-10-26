# OWNER-CONFIDENCE-MIDDLE-PATH-01: Carbon-side error calibration now; miner 95 % ranges in the next version

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25 ~03:00–03:10Z; relayed to the Validator, who specified it in codex-queue/reports/EXAM_ADDITIONS_20261025.md.
- **Owner's words:** "Middle path is good for now".
- **Decided:** for the launch versions Carbon calibrates error ranges itself from the sealed pool truths (custody only; per region and output: quantiles, max, miss-rate bound; gate failures counted separately). It feeds the product Envelope Guard only. Nothing changes for miners. It is never a score input (invariant 11) and never appears on any miner or public surface. Next version: miners output 95 % ranges, scored as option 1a.
- **Open with the owner:** the Guard's TRUST/VERIFY/REFUSE band thresholds (product policy).
