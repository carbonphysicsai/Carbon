# ev4-dev-tuning-v1: the score-tuning loop's development decision data

This is DEVELOPMENT evidence (Test Lead GO, 2026-10-05). It reuses EV4's contract and development conditions under contract `ev4-dev-tuning-v1`, with the `ev4-dev-tuning` panel.

**Panel (142 members):**
- EV4's 100 recipes: host-CPU rebuilds from SR-B1;
- Graphite run 5's 27 rebuilds (#609);
- the 10 Track A constructions, rebuilt on the host's CPU here;
- the 5 constructed controls.

**References:** EV4's committed decision references, checksum-verified, overlaid by REF-RESOLVE-01 v1's settled references.

**Not used:** EV5's files and verification split.

**What it feeds:** `results.json` gives every member's development decision losses and outcomes, which the score-tuning harness (#650) needs. `score_tuning.decision_values` derives the mask, and `predictions.sha256` lists the prediction bundles, which stay on the operator host.

**What is still missing:** the score legs. They need the members' predictions on the sealed tuning set (`graphite-tuning-v1`), scored operator-side.
