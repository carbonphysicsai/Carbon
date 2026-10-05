# VALIDATOR-07 — The agents' tool text, by version

**Status:** implemented in bounded DEVELOPMENT scope, awaiting review.
**Authority:** the Test Lead, 2026-10-05:
- a cooling Constructor reading "battery" in its tool text is a confound
  that could steer the agent and contaminate what the wave measures;
- a new session selects and records challenge-neutral v2 text, and replays
  keep v1;
- the plan-identity tests are parametrised by version;
- this must be on main before the first live cooling session.

**Executor:** the Carbon Validator session. Branch
`claude/graphite-tool-text-v2`, from main `d62fefb90`.

## Outcome

Every new Graphite session's agents read tool descriptions that name no
Challenge. Every session recorded before keeps the exact text and bytes it
ran with.

## Working decisions (delegated engineering scope)

- **VAL7-D1 — two registered texts.**
  - `roles.TOOL_TEXT_V1` is the original wording. `PROPOSAL_TOOL`,
    `NEXT_LEVEL_TOOL` and `TOOL_REGISTRY` are byte-unchanged.
  - `TOOL_TEXT_V2` changes only those two tools' descriptions: the same
    names and parameters, with no Challenge named. They were the only
    battery words in any Graphite tool. The prompts were already neutral.
- **VAL7-D2 — what records the version.**
  - The brief selects it: `SessionBrief.tool_text`, defaulting to v2 for a
    new brief, and `phase3.session_brief(tool_text=)`.
  - The session records it in its role record: `GraphiteRole.record(tool_text)`.
  - Every turn reads it (`tool_text_of(opened)`) at the base, phase-3 and
    phase-4 epochs.
  - A resume checks the recorded manifest digest under the recorded version
    (`_verify`).
  - An absent key means v1, exactly like `session_limits`, so every record
    and brief made before keeps its bytes.
- **VAL7-D3 — nothing changes where v2 changes nothing.**
  - A role whose tools v2 leaves alone resolves to v1
    (`effective_tool_text`). Its record and brief carry no key and keep
    their bytes: the Attacker, Reader, Writer and Optimizer.
  - Only the Constructor and the Planner record v2.
- **VAL7-D4 — refusals.**
  - An unknown version is refused at the brief (`tool_text_unknown`).
  - A brief naming a version that is unknown, or that doesn't apply to its
    role, is refused before a session opens (`brief_tool_text_unknown`).
  - A record whose version disagrees with its digest stops at resume
    (`session_record_mismatch/role_changed`).
- **VAL7-D5 — the pinned tests name v1.**
  `test_a_v1_plan_is_byte_identical_to_the_one_written_before_the_change`
  and `test_a_session_recorded_before_d34_replays_byte_identically` open new
  sessions whose bytes predate the versions. They pass `tool_text=TOOL_TEXT_V1`
  and their pins are unchanged.

## Changes

- `carbon/agent_campaign/graphite/roles.py`:
  - `TOOL_TEXT_V1/V2`, `PROPOSAL_TOOL_V2`, `NEXT_LEVEL_TOOL_V2`;
  - on `GraphiteRole`: `tool_schemas(tool_text)`, `effective_tool_text`,
    `manifest_digest` and `record(tool_text)`.
- `carbon/agent_campaign/graphite/provider.py`: `SessionBrief.tool_text`,
  `tool_text_of`, and `start`/`_verify`/`_epoch` reading the recorded
  version.
- `carbon/agent_campaign/graphite/phase3.py` and `phase4.py`: the epochs read
  the recorded version, and `session_brief(tool_text=)`.
- Tests: `tests/cpu/test_graphite_tool_text.py` (new), plus a version
  parameter in the phase-3 fixtures and the two pinned tests.

## Validation

- `tests/cpu/test_graphite_tool_text.py` (9 tests) covers:
  - v2 names no Challenge in any role's tools;
  - v1 is the original objects, and v2 changes descriptions only;
  - records and briefs keep their bytes where v2 changes nothing;
  - unknown versions are refused;
  - a Planner session on each version records it, writes that version's
    schemas to its plan and sends them to the model;
  - a forged record version stops the session;
  - forged brief versions are refused before opening.
- **Byte-pinned suites:** internal limits, harness, mutations, boundaries,
  phase 4, literature, level planner and phase 3.
  - Before the fixture change: 256 passed, and only the two pinned tests
    failed, as expected.
  - After it: those and the new suite gave 41 passed.
- `scripts/check_quality.py --base origin/main`: passed.
- Canonical: recorded in the PR.

## Invariants exercised

10 (historical evidence is versioned: no recorded session is reinterpreted)
and the wave's measurement integrity (no Challenge confound in agent-facing
text).

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT).

## Follow-up (not in this ticket)

The literature pipeline's battery-specific search topics and card-extraction
prompt (gap 17) are the next design.
