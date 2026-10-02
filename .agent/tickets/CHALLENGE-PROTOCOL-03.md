# CHALLENGE-PROTOCOL-03 — Phase 1 step 3: test suite v1

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-CHALLENGE-ROADMAP-01 (2026-10-02), OWNER-DX-03.
**Spec:** `Design_Specs/Challenge_Roadmap.md`, §01 step 3 and §03.
**Depends on:** CHALLENGE-PROTOCOL-02 (the protocol draft it fills in).

## Outcome

The roadmap's step 3 is "Build test suite v1. Track A attack vectors with
severity rules, Track B EV1–EV3, exam rotation and sealed pool." Its
output, "versioned, pinned suite", is:
- `carbon/challenge_pipeline/suite_v1.json`, DRAFT:
  - Track A's eight vectors, each citing the existing checks that exercise
    it and its known gaps;
  - the draft severity rules;
  - Track B's EV1, EV2, EV3 and baselines, with what each requires;
  - the metrics;
  - the exam rotation and sealed-pool registration.
- `carbon/challenge_pipeline/suite.py`: the suite's pin (a digest of its
  canonical JSON), and a runner that executes one challenge's cited checks
  and reports each vector's coverage against that pin and the commit.
- Battery's first coverage report, run in the canonical environment
  (`docs/development/challenge_pipeline/SUITE_V1_BATTERY_COVERAGE.json`).

## Working decisions

- **PROTO3-D1. The roadmap's vectors are the spine; admission's checks are
  cross-referenced.**
  - The admission protocol names its eight construction checks differently
    (baseline and permission ablation, artifact and dependency attacks, and
    so on).
  - Each roadmap vector lists the admission checks it covers. A test
    requires every construction-integrity check to be mapped.
  - Track B maps admission's engineering-value checks the same way. Two are
    not mapped:
    - untouched confirmation, which is the frozen run itself;
    - customer evidence, which is outside the in-house pipeline.
- **PROTO3-D2. Cite existing checks; do not rewrite them.**
  - The suite cites 77 existing tests by node id, grouped `generic`,
    `battery` and `sandbox`. A test fails if a cited function does not
    exist.
  - Each vector also lists what no check covers (its `gaps`). Those gaps
    are step 4's work list.
- **PROTO3-D3. Coverage, not grades.** The runner reports one of three
  states per vector:
  - PASS, when every cited check ran and passed;
  - FINDING_CANDIDATE, when a cited check failed: a candidate for the
    technical owner to grade;
  - NOT_RUN, when a check was skipped or could not be collected. NOT_RUN is
    never a pass.

  Container checks (`sandbox`) run only when asked for. Battery's need a
  pinned test image that no CI job builds, so by default they are NOT_RUN.
  The runner selects by name with `--continue-on-collection-errors`, so one
  unavailable check never stops the rest.
- **PROTO3-D4. Severity rules are drafted for the technical owner.**
  - **Critical:** protected evaluation material observed or influenced, an
    unearned grade, or an isolation escape.
  - **High:** a reproducible fail-open without demonstrated impact.
  - **Medium:** the defense holds but its evidence does not.
  - **Low:** hardening and hygiene.

  They follow Carbon's invariants (1, 6, 7 and 7.9) and the admission
  protocol's mandatory failures. They remain DRAFT until the technical owner
  approves them and the process owner locks the protocol.
- **PROTO3-D5. Values reserved to people stay open.**
  - Reserved: the disclosure budget, anchor set, sealed-pool size,
    selection rule and reconstruction tolerance (`HUMAN_INPUT`).
  - Also open: the backends Track A admission accepts, which is
    OWNER-CHALLENGE-ROADMAP-01's open question.
  - The suite records each where it applies; nothing is filled in.
- **PROTO3-D6. Graphite's ledger is still not wired into the controller.**
  That belongs with step 4, the first Graphite run that needs it.

## Battery's first coverage run

Run in the canonical environment with CI's full dependency groups (chain,
archive, science-jax, science-torch, mcp), at suite digest
`sha256:6b8255c548e05c0f9e6009bb90852f840d399ddfc1bf35ef153a4d1226f45f84`.
- **All eight vectors PASS.** Every one of the 70 cited non-container checks
  ran and passed, and no uncited selected test failed.
  - pytest reported 259 passed and 551 deselected. The 259 include
    parametrized cases and same-named tests in the cited files.
  - pytest's exit code was 1 because of the invariant lane's deselection
    guard (`tests/invariants/conftest.py`), not because of a failure.
- **The container checks were not run** (`--sandbox`), so they are NOT_RUN
  by default.
- **The listed gaps stay open.** These are the work for step 4:
  - no byte-level detection of disguised executables;
  - no probes in the battery image;
  - no registered sealed pool, disclosure budget or anchor set;
  - no repeat-seed rebuild on a fresh worker;
  - no quarantine of unresolved battery grades, and no check of
    disagreement between workers;
  - no stale-cache test;
  - no cross-case leakage test.
- **An earlier run with only the `dev` group** left most checks NOT_RUN.
  Two failed on missing modules. That is why the suite now records each
  challenge's required groups (`environments`) and the groups a run had.

## Definition of done

- `suite_v1.json` loads and validates. Its cited checks all exist. Every
  admission construction check is mapped.
- The runner's three states are tested against a fake suite.
- Battery's coverage report is produced in the canonical environment and
  committed with the suite digest and commit it ran on.
- `protocol.json` step 3 is done, with the report as evidence. The protocol
  draft references the suite. The pipeline, protocol and suite tests pass.
  Black, ruff, hygiene and the hub pass.

## Maturity ceiling

A draft registry and a coverage runner. A PASS means the cited defense tests
pass. It is not security acceptance, and it does not prove resistance to
unrestricted agents.
