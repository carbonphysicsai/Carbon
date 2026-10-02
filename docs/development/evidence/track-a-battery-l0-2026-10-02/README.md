# Battery Track A, Level 0: first harness run (2026-10-02)

**Class:** DEVELOPMENT engineering evidence for CI-BATTERY-L0-01. This is not
a security audit, not a Track A acceptance and not a qualification.

Produced by `python -m carbon.battery.track_a run --out <this directory>`. The
command exits 1 because conditions fire; none is suppressed.

## Files

- `attempts.jsonl`: every attempt, unsuccessful ones included, with the digest
  of each result. There are 37 attacks, 37 specimen runs and 4 controls.
- `coverage.json`: family states, findings, coverage per Track A check (here,
  reused, untested), the reserved values (HUMAN_INPUT), and claims (none).
- `conditions.json`: the conditions `carbon.battery.value.divergence` emits on
  the retained EV2 and EV4 results.

## Results

**Registered families (all in-process):**

| Family | Track A check | Attacks | Held | Specimen fired | Control |
|---|---|---|---|---|---|
| `recipe_surface` | artifact_and_dependency_attacks | 21 | 21 | 21 | passed |
| `recipe_forgery` | artifact_and_dependency_attacks | 2 | 2 | 2 | passed |
| `mandatory_failure` | score_exploitation_and_tail_failures | 9 | 9 | 9 | passed |
| `rebuild_identity` | reconstruction_and_recipient_rebuild | 5 | 5 | 5 | passed |

- No attack breached its real boundary, and no control was wrongly refused.
- Every recipe attack was refused by a typed compiler issue, not a crash.
- In `mandatory_failure`, one damaged case among 200 otherwise exact
  predictions makes the model ineligible. Under the averaging specimen the
  same predictions would have scored 0.0, as well as the references
  themselves.

**Findings emitted from retained results (existing detector, unchanged):**

| Results | Conditions | SCORE_VALUE_DIVERGENCE | GATE_ANOMALY |
|---|---|---|---|
| EV2 (2026-10-01) | 12 | 11 | 1 |
| EV4 (2026-10-01) | 42 | 41 | 1 |

- The EV4 conditions are new evidence. The admission pressure test's
  retained evidence (`admission-pressure-2026-10-01/`) holds EV1's and EV2's
  only.
- On both, the boundary-optimist control fires. Several real members fire
  too; those are findings to investigate, not verdicts.
- Under §3.3, these findings escalate to review. They are not entered in a
  readiness record here, because the v3 wiring (#477) is held. They should be
  entered when it lands.

## Limits

- In-process checks prove the boundary they call, nothing more.
- Worker isolation and resource accounting are reused evidence from the
  pinned C-03 service lane and the battery container tests, mapped in
  `coverage.json`. They were not rerun here, because the pinned worker image
  cannot be built in this environment (TLS interception of the image build's
  downloads).
- Executable-code families are NOT_RUN at Level 0, never passed.
- Fresh-attack confirmation is NOT_RUN: there is no frozen study sheet.
- Nothing here bounds the absence of exploits.
