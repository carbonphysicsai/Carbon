# Graphite wave-end retrospective: template (one per challenge)

**Status:** DRAFT for the Test Lead's approval. **Owner:** Test Lead session;
the Graphite Testing Manager fills the data parts. **Source rules:**
`LESSONS_REGISTER.md` (how the register works, section 8 metrics) and
`GRAPHITE_READINESS_GATE.md` (the gate). Nothing here grants authority to run,
and none of it is scientific, security or production qualification.

Copy this file to `docs/development/graphite/retrospectives/<challenge_id>-<wave>.md`
at the end of that challenge's wave and fill every field. A field with no data
says why; none stays blank.

## 1. Header

| Field | Value |
|---|---|
| Challenge | `<challenge_id>` |
| Wave / level range | `<e.g. wave 1, levels 0 to 0>` |
| Period | `<first Level 0 contract date>` to `<end date>` |
| Gate reports used | digests of the first and last `readiness` run, from `readiness/<challenge>/history.jsonl` |
| Author, reviewer, date | |

## 2. Metrics (register section 8)

Take the gate numbers from the history file, never from memory:
`python -c "from carbon.challenge_pipeline.readiness import runner; print(runner.history_metrics('<challenge_id>'))"`.

| Metric | Value | Source | Target | Better than the previous challenge? |
|---|---|---|---|---|
| Gate green: date of the first full green run | | `history.jsonl` (`first_green_utc`) | reached before any live run | |
| Items not passing on the first full gate run | | `history.jsonl` (`first_run_not_passing`) | falling each challenge | |
| Gate runs until green | | `history.jsonl` | | |
| Harness-lost live runs | | run logs, lessons entries | 0 | |
| Post-start defects (after the first live Graphite run) | | list each with its lessons entry | falling each challenge | |
| Days from the Level 0 contract to the first valid Graphite run | | git and run records | | |
| Oracle false findings per Attacker session | | Attacker reports | 0 after lesson A1 | |
| New cross-cutting lessons added to the register | | register diff | shrinking | |
| Owner interruptions (decision batches, not single questions) | | decision files | shrinking | |

State for each row what it was for the previous challenge, so "better" is read
off a comparison, not asserted.

## 3. Gate item review

One row per item (O1 to V3). The status is the last full `readiness` run.

| Item | Status at first run | Status at last run | Did the item catch something real? | Did a live-run defect arise that this item should have caught? | Action |
|---|---|---|---|---|---|
| | | | | | keep / tighten / new item (propose) |

Gate items only get stricter (gate document, "How the gate stays current"): an
item is not removed here. A proposal to remove one needs a recorded Test Lead
decision naming the enforcement that replaces it.

## 4. Disposition review of the register

Re-check every DOCUMENTED and OPEN row (register rule: the end-of-wave
retrospective). List every row whose disposition is DOCUMENTED, OPEN or IN PR.

| Lesson | Disposition at wave start | Disposition now | Evidence (PR on origin/main, test id) | Owner | Next step |
|---|---|---|---|---|---|
| | | | | | |

- Flip IN PR to ENFORCED only for a PR confirmed merged on origin/main.
- A lesson that can only be documented says why.
- No lesson stays OPEN without an owner.

## 5. What was messy

The owner's goal is that each wave is the messiest we run, so the next is
cleaner. List, in order of cost:

1. each live run or day lost, with its cause and the lesson id (existing or new);
2. each defect found after the first live run that a pre-live check could have
   found, with the gate item that would have caught it (existing or proposed);
3. each owner interruption that a decision file could have answered earlier.

## 6. Proposals

| Proposal | Kind (gate item / register lesson / policy / tooling) | Owner | Needs the Test Lead's approval |
|---|---|---|---|
| | | | yes |

## 7. Sign-off

The Test Lead approves or amends this retrospective in a normal PR. Approval
confirms the review is complete; it confers no scientific qualification, launch
readiness or authority to run (the per-run launch checklist, OWNER-GRAPHITE-
TEST-WAVE-05 section 3, still applies).
