# GATE-PASS-DIAGNOSIS-01 — aggregate the recorded practice gates

**Working decision (DEVELOPMENT):** Keep the existing battery gate and score
rules. Diagnose the miner's own exported practice summaries with a read-only,
aggregate-only command. Count a reported pass only when eligibility is true,
the gate-failure map is empty, and at least one case was scored. Distinguish a
low descriptive error on scorable cases from admissibility. Match the default
MLP only to the exact published scaffold recipe.

**Why:** the existing `exam.aggregate` deliberately lets a trial have a low
descriptive error and a mandatory gate failure. The 5,711-trial headline has no
per-gate counts and cannot identify a failing gate by itself. The committed
graphite-run5 practice evidence proves that the published baseline can pass,
but it is a different campaign. Changing a gate tolerance from this headline
would invent a scientific decision.

**Privacy direction from the owner:** the miner keeps the Launchpad export,
which contains his recipes. Carbon must not request or receive it. He can run
the command himself after merge and share only the counts-only aggregate. That
output must account for all 5,711 trials and report any incomplete or
contradictory summaries. No hidden exam bank, AX42 data, new solver run, or
spend is required.

**Boundary:** no scientific threshold, official score, LIVE state, or protected
data is changed. If the export shows an implementation defect, repair it in
this ticket with a regression test. A prospective scientific gate revision is
reserved to the owner.
