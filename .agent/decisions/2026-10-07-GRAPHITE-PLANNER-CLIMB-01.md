## 2026-10-07 — GRAPHITE-PLANNER-CLIMB-01: a climb session for Graphite's level planner

**Authority.**
- **The owner's approval, 2026-10-07 ("Approved"), relayed by the Test Lead.**
  Battery climbs Levels 2 and 3 as quick, declarative-only climbs while
  Level 4's Phases 0-1 are built.
- **The Test Lead's direction.** Graphite's level planner proposes real
  Level 2 and Level 3 capabilities, the contract owner accepts them through the
  climb procedure, and the development-only variants are built the way #611
  built Level 1.
- **Bounds.** OWNER-GRAPHITE-DEV-LEVELS-01 sets them: development-only
  variants, drafted surfaces allowed, and Level 3 a declarative menu only.

Everything below is an engineering choice within that authority. It adds no
grant and makes no call.

**The gap.** The six accepted battery level proposals (level-plan-3) widen
nothing past today's contract. The planner's brief places the contract's own
capabilities on the ladder, so a Level 2 or Level 3 reply listed what already
exists.

**Decisions.**
1. **A climb session** (`LevelPlanner.plan(..., climb=True, levels=...)`, or
   `--climb --level N` on the runner).
   - **Brief:** the brief is marked `mode: climb`, so a climb is its own
     session. A plain brief, and so every earlier session's digest, is
     unchanged.
   - **Rules sent as data with each level:**
     - propose what the level adds beyond today's contract;
     - never re-list a contract capability;
     - each capability is development-only and declarative, running no
       participant code;
     - at Level 3, each capability is one fixed menu of named routines, with
       the whole menu and its default in its bounds.
   - **Unchanged:** the prompt and its digest.
2. **Climb levels.** A climb runs only Levels 1-3. Level 0 is today's
   contract; Levels 4-5 wait for the security owner's isolation acceptance.
   Any other level set is refused before any call (`levels_refused`).
3. **One new refusal.** A climb reply whose capability id is a contract id is
   rejected (`climb_capability_already_in_contract`) and recorded like any
   other rejection.
4. **Level selection** (`levels`) also narrows the request-size check to the
   levels asked for.
5. **A required Level 2 capability.** The owner approved this addition,
   relayed by the Test Lead on 2026-10-07: Level 2's sampling includes data
   selection from a fixed, pre-solved public pool.
   - **The rule:** a Level 2 climb is told to propose `data.pool_selection`
     (`CLIMB_REQUIRED`). A reply without it is rejected
     (`climb_required_capability_missing`).
   - **The owner's constraints, sent as data:**
     - the same pool for everyone, with no new solves;
     - reproducible from the recipe;
     - the subset size counts against the compute budget, using the cost
       calculator;
     - disjoint from every hidden, tuning, confirmation, study and EV set,
       checked with the validator's overlap check.
   - **A missing pool:** if no such pool is published yet, the planner names it
     in `left_out` as a dependency.
   - **The planner's part:** the capability's content stays the planner's
     proposal.

**Running it** (the executor, on the operator host). The run uses the one
planner grant, `GRAPHITE-GRANT-PLANNER-02`: its worst case per run is USD
1.50, and its runner caps a session at 8 calls. A Levels 2-3 climb makes 2
calls plus any retries. The proposals stay under the run's private root.
Committing them, and the contract owner's acceptance, are separate acts.

**Tests.** `tests/cpu/test_graphite_level_planner.py` adds four climb tests:
- a Levels 2-3 climb proposes only those levels and sends the climb and
  Level 3 menu rules;
- a re-listed contract id is rejected;
- Levels 0, 4, 5 and an empty set are refused before any call;
- a plain brief is unchanged.
