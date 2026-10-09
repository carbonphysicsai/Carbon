## 2026-10-08 — RATE-STUDY-PROBER-01: SUBMISSION-RATE-STUDY-01's scripted prober and G-sealed brief

**Authority.**
- **The specification.** SUBMISSION-RATE-STUDY-01 plan item O5 and run sheet
  sections D.2 and D.3 make these the Test Engineer's.
- **The scheduling.** The Test Lead's overnight queue of 2026-10-08 put them
  next.
- **The scope.** This is development tooling. It grants nothing, and it
  moves no threshold.

**Decision.**
- **`carbon/agent_campaign/graphite/study_prober.py`** holds one stateless
  rule, `next_probe(mode, history)`. Both the scripted prober (`Prober`) and
  the G-sealed probe tool use it:
  - **The search:** deterministic, coordinate-wise hill climbing over battery
    MLP recipes, on fixed ladders inside the construction contract's caps,
    from battery's panel MLP.
  - **The objective:** S-sealed reads the allow-list state only. S-revealed
    reads the study bank's batch score, and a revealed view without it is
    refused.
  - **No repeats.** It never proposes a recipe it has had an informative
    answer for, because the route never rescores a repeat (plan O7c).
- **The ladders and start are engineering constants of the study tooling.**
  They are not scientific values, and the study's result does not depend on
  them being optimal. They bound what a simple adaptive search extracts.
- **The module sits in `carbon/`,** not `scripts/dev/` as the run sheet first
  said, so the probe tool can import the same search.
- **The G-sealed brief:** `docs/development/graphite/briefs/rate-study-g-sealed.md`.

**Tests.** `tests/cpu/test_rate_study_prober.py`, 9 passed:
- the search is deterministic;
- it makes 144 distinct proposals in both modes;
- S-revealed climbs a synthetic score, and S-sealed reads the state only;
- states with no information repeat the proposal;
- the tool replays the prober exactly and ignores a session's own off-ladder
  designs;
- every proposal compiles;
- the module reads nothing.

**Not claimed.**
- **The arm runner** (VALIDATOR-30) is not built here.
- **The probe tool is not offered yet.** Offering it in a study-only
  Constructor manifest is a separate PR, due before the freeze.
- **The prober is not evidence** of what any adversary can extract until
  the study runs.
