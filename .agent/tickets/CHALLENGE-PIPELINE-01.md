# CHALLENGE-PIPELINE-01 — the Challenge Roadmap as Carbon's standing pipeline

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Affects:** `SYSTEM/GOVERNANCE` (the decision record).
**Authority:** OWNER-CHALLENGE-ROADMAP-01 (2026-10-02), OWNER-DX-03.
**Spec:** `Design_Specs/Challenge_Roadmap.md` (rev 2.0).

## Outcome

The roadmap the owner approved on 2026-10-02 becomes versioned repository
state that the rest of the work runs against:
- the roadmap's text as a design spec;
- its 26 families, labels, estimates and briefs, transcribed exactly;
- its queue, false-feasible bound and leaderboard as tested code;
- the protocol (Phase 1's eight steps), the rubric and one record per family,
  validated against the roadmap's rules;
- a generated view, `docs/development/CHALLENGE_PIPELINE.md`.

## Working decisions

- **PIPE-D1. Port the page, do not reinterpret it.**
  - `rank_all`, `ff_upper` and `board_rows` follow the roadmap page's
    `rankAll`, `ffUpper` and `boardRows` line for line, and the records keep
    the page's field names (`p50s`, `attC`, `rho`, `k`, ...). So a record
    moves between the page's shared store and the repository unchanged.
  - The one difference is the log-gamma. The page uses a Lanczos series;
    Python's `math.lgamma` is used here. The bound differs by round-off only,
    and a test checks it against SciPy's exact beta quantile to 1e-9.
  - Alternative rejected: a Pythonic schema. It would need a translation
    layer that could drift from the page.
- **PIPE-D2. The roadmap's rules are enforced, not just documented.**
  - A family other than battery cannot be past `queued` before the protocol
    is locked.
  - A stage needs the sign-off of the gate before it, by the owner the
    roadmap names for that gate.
  - Track A and B results need a frozen evidence record and a suite name.
  - A measured p50 needs the protocol's reference hardware and its timing
    evidence.
  - Rubric thresholds need the process owner's approval.
  - Each refusal is a test.
- **PIPE-D3. Owners are held by role.** `protocol.json` maps process,
  technical and science to the people the roadmap's header names. A gate
  checks the role, so a change of person is a one-line roadmap revision.
- **PIPE-D4. Records exist only where there is something to say.**
  - Battery's record holds the protocol stage.
  - Six queued families carry links to the prior work the existing
    challenges give them.
  - Every other family is at its default and has no file.
- **PIPE-D5. The rubric starts unset.** `minRho`, `maxFF`, `minN` and
  `maxReg` are null, which is the fail-closed `HUMAN_INPUT` state. `maxC` and
  `maxH` are 0 because §05's gate is "no open critical or high attack
  findings". The leaderboard therefore lists results without eligibility, as
  the roadmap says it does until rubric v1.

## Definition of done

- `python -m carbon.challenge_pipeline validate` passes on the committed
  state, and `render --check` reports the view current.
- `tests/cpu/test_challenge_pipeline.py` passes:
  - the transcription's integrity;
  - the page's queue order;
  - the solve-time bins;
  - measured times re-ranking the queue;
  - the bound against its closed form and SciPy;
  - leaderboard gating and ordering;
  - every validation refusal.
- Black, ruff, `git diff --check` and delivery hygiene pass.
- The hub event and path rules are added, and the hub validates and renders.

## Validation

```text
python -m pytest -q tests/cpu/test_challenge_pipeline.py
python -m carbon.challenge_pipeline validate
python -m carbon.challenge_pipeline render --check
python docs/development/carbon_hub/tools/validate_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
```

## Rev 2.2: the construction ladder, one generalizable protocol, lessons (OWNER-CHALLENGE-ROADMAP-03)

Before merge, the owner found that the pipeline had dropped Challenge
Admission §3's construction ladder. The fix:
- **Ladder machinery: `ladder.py`.**
  - Levels 0-5 word for word from Admission §3, and the climb procedure.
  - Each record's `construction` block, checked as follows:
    - levels are contiguous from 0, and a level not listed is NOT_RUN;
    - each level names its expansion record and Carbon's reconstruction test;
    - every level below the current one is TESTED or FROZEN with evidence;
    - the current level names the newest expansion record, so a contract
      change the pipeline has not seen is stale;
    - Test/iterate needs a contract on the ladder;
    - a frozen run is taken at a FROZEN level.
  - Battery's record is at Level 0, OPEN, on expansion 0001. It states
    battery's recorded difference from the ladder.
- **Lessons: `lessons.py` and `lessons/`.**
  - One file per execution: what ran, expected against observed, what to keep,
    what to change, and the protocol elements it bears on.
  - A proposed revision waits for a named owner: before lock, any of the
    three; after lock, the process owner.
  - The first seven entries record today's executions, including the dropped
    ladder (ADOPTED under OWNER-CHALLENGE-ROADMAP-03).
- **The view** gains the ladder, the climb procedure, each Challenge's level
  states, and the lessons awaiting a decision.
  `python -m carbon.challenge_pipeline lessons` prints the log.
- **Generalizable.** Nothing in `ladder.py` or `lessons.py` is battery-specific.
  The tests climb a synthetic second Challenge with its own expansion records.
- **Roadmap rev 2.2:**
  - the ladder in §00 and §02, with Stage 2's exit and Stage 3's work;
  - the climb procedure;
  - how a validator knows how to build a construction;
  - Track A at every implemented level;
  - leaderboard entries by level;
  - the corrected backend wording;
  - Graphite as the testing agent;
  - Phase 1 step 4 including battery's first climb.

## Maturity ceiling

IMPLEMENTED and TESTED as engineering machinery. The pipeline grades
nothing: it is not scientific, security or production qualification, and no
challenge becomes LIVE, reward-bearing or deployed through it. Every
threshold, sign-off and deployment remains the named owners' act.

## Next

Phase 1 step 1, CHALLENGE-PROTOCOL-01: reconcile battery's current state into
a status record with commit IDs.
