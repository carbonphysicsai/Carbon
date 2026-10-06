# VALIDATOR-05 — Graphite's neutral plumbing for a named Challenge

**Status:** implemented in bounded DEVELOPMENT scope, awaiting review.
**Authority:**
- the Test Lead's request, 2026-10-05: cooling through Graphite phase 3, from
  the Graphite Test executor's cooling readiness review;
- OWNER-GRAPHITE-TEST-WAVE-06 §5 (#595): Codex builds each Challenge's
  scoring pieces; this session builds the neutral plumbing that takes a
  named Challenge, with a hook where Codex's adapter plugs in.

**Executor:** the Carbon Validator session. Branch
`claude/graphite-neutral-challenge`, from main `e736dfda5`.

## Outcome

A Graphite session reads its own Challenge's published material and writes
bundles in neutral words.
- The phase-3 Constructor and the phase-4 Attacker check out the material
  of the Challenge they serve, never battery's by default.
- Each Challenge's scoring adapter can supply its own list.

DEVELOPMENT only. No score, weight or reward changes.

## The gaps, read-only on main `e736dfda5`

**Closed on main by #584:**
- **Gap 1:** cooling's scoring.
- **Gap 3:** unnamed callers.
- **Gap 4:** `--challenge`.
- **Gap 5:** a permission profile per scoring.
- **Gap 6:** `RunPodPods` and `real_path_check` take the scoring.
- **Gap 7:** `next_level` uses the named contract.
- **Gap 8:** the bundle's clean rebuild resolves the strategy's own
  Challenge.
- **Gap 9:** the dry run is built from the port's hooks.

**Open, closed here:** gaps 15, 16 (bundle text) and 18.

## Working decisions (delegated engineering scope)

- **VAL5-D1 — published material per Challenge.**
  - `boundaries.PUBLISHED_MATERIAL` maps each contract token to its Level-0
    material:
    - the interface;
    - the recipes and the code that builds a construction;
    - the public reference solver (invariant 33);
    - the construction contract and the strategy schema.
  - Battery's entry is the unchanged `_PUBLISHED_CHALLENGE` tuple, so its
    checkout and manifest digest are byte-identical.
  - Cooling: `cold_plate/{domain,challenge,recipes,compile,contracts,openfoam}.py`
    and `learned_baseline.py`.
  - Motor: `motor/{domain,challenge,recipes,compile,contracts,getdp,mesh}.py`
    and `learned_baseline.py`.
  - An unknown Challenge is refused (`challenge_material_not_registered`).
  - The denylist still wins over every list.
- **VAL5-D2 — the hook.**
  - `ChallengeScoring.published_material()` defaults to the boundary's
    registered list. A Challenge's adapter may override it without editing
    `boundaries`.
  - `scoring.published_material(challenge_id)` uses the registered scoring,
    or the boundary's list while a Challenge has no scoring yet (motor today).
  - Phase 3 passes `scoring.published_material()`.
  - Phase 4 passes the attacked adapter's Challenge.
- **VAL5-D3 — bundle text is neutral, tool text is not changed here.**
  - `WRITEUP.md` names the rule by its registered identity and reads
    `important_score` only if present. `REBUILD.md` names the bundle's
    Challenge.
  - Correction to the gap review: cooling's rule summary carries
    `important_score`, so the old writeup did not crash on cooling; it only
    said "battery" and "rule v2".
  - The agents' tool descriptions (`roles.py`) are part of every recorded
    plan. `test_a_v1_plan_is_byte_identical_to_the_one_written_before_the_change`
    pins those bytes.
  - So changing that text changes historical plans, and could refuse the
    resume of a session in flight. It needs a versioned role record selected
    at session open, which is a separate change; see Human input required.
- **VAL5-D4 — test fixtures for synthetic Challenges.** Phase 4's stand-in
  and synthetic adapters name Challenges that have no material. Their tests
  register battery's files for those synthetic ids, which is what every
  Attacker received before. A real unregistered Challenge is refused.

## Changes

- `carbon/agent_campaign/boundaries.py`: `PUBLISHED_MATERIAL`,
  `published_material`.
- `carbon/challenge_validator/scoring.py`: `ChallengeScoring.published_material`
  and the module's `published_material`.
- `carbon/agent_campaign/graphite/phase3.py` and `phase4.py`: checkouts use
  the session's Challenge.
- `carbon/agent_campaign/graphite/delivery.py`: neutral writeup and rebuild
  text.
- `carbon/agent_campaign/graphite/next_level.py`: neutral docstring.
- Tests:
  - new: `tests/cpu/test_graphite_named_challenge.py`;
  - updated fixtures in `tests/cpu/test_graphite_phase3.py`, where the
    recorded-checkout stand-in accepts battery's named list, and
    `tests/cpu/test_graphite_phase4.py`, which registers the synthetic
    material.

## Validation

- `tests/cpu/test_graphite_named_challenge.py` covers:
  - each Challenge's list exists and passes the denylist; unknown
    Challenges are refused;
  - battery's checkout digest is unchanged;
  - the hook supplies the list, and the denylist still wins;
  - the Constructor checks out its own Challenge's material;
  - the Attacker checks out the attacked Challenge's material, for every
    registered adapter;
  - a cooling fixture dry run ends with a bundle whose writeup names the
    cooling rule and whose writeup and rebuild text name no battery, and
    whose clean rebuild is REBUILT.
- **Native, 20 suites:** the Graphite phase 3, phase 4, literature, limits,
  mutations, ladder, planner, method-card, harness and boundary suites, the
  agent-campaign boundary, controller and mutation suites, the attack
  knowledge and synthetic-adapter suites, the cooling scoring suite and the
  cooling and motor construction-contract suites.
  - 602 passed and 9 failed before the fixes in VAL5-D3 and VAL5-D4.
  - After the fixes, the 9 and their files pass (phase 4: 47; named-challenge
    plus limits plus the pre-D34 replay: 80).
- `scripts/check_quality.py --base origin/main`: passed.
- **Canonical:** recorded in the PR.

## Invariants exercised

- **1 and 2:** a session reads only its Challenge's published material,
  with the denylist (evidence, EV4, EV5, confirmation) winning.
- **4:** an allow-listed checkout.
- **10:** recorded plans and checkouts stay byte-identical.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT). Not SECURITY_QUALIFIED.

## Human input required

- **Neutral agent tool text:** make the Constructor's tool descriptions
  challenge-neutral as a versioned role record that a new session selects
  and records, keeping v1 for replay. This is the Test Lead's call on
  priority.
- **Literature (gap 17):** the battery-specific search topics and the
  card-extraction prompt are queued as their own design (Test Lead,
  2026-10-05).
