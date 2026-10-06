# VALIDATOR-08 — Literature for a named Challenge

**Status:** implemented in bounded DEVELOPMENT scope, awaiting review.
Tooling, tests and the owner-approved grant. No fetch or extraction has run.
**Authority:**
- the Test Lead's approval of the design, 2026-10-05 (gap 17 of the Graphite
  cooling readiness review; the owner wants every option tested);
- OWNER-GRAPHITE-LITERATURE-GRANT-01, the owner's "approve" for
  `GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR`.

**Executor:** the Carbon Validator session. Branch
`claude/graphite-literature-challenges`, from main `d62fefb90`.

## Outcome

A cooling or motor Graphite Constructor can be offered literature about its
own Challenge, ranked for it. Battery's literature is untouched:
- its query set `graphite-phase2-queries.v1`;
- its v1 prompt;
- its `backfill/` card store;
- its frozen snapshot (4adb013d).

## Working decisions (delegated engineering scope)

- **VAL8-D1 — a registered literature profile per Challenge.**
  - Each is a document in `graphite/literature_profiles/`, pinned by digest,
    holding the Challenge's query set (6 domain queries), its arXiv
    categories, and its primary and secondary domain cues.
  - Profiles exist for `chip-cold-plate` and `electric-motor-magnetics`.
    Battery has none: its pipeline is phase 2's.
  - A profile may not reuse battery's query set.
  - The miner edition's focus rule (`miner/focus.py`) and its digest are
    unchanged. The profiles reuse its whole-phrase matching, surrogate and
    learning cues, ranked fields and grade thresholds.
- **VAL8-D2 — fetch.**
  - `phase2 fetch --challenge X` fetches the profile's query set into the
    shared raw store, with a default quota of 3 pages per query.
  - Records are content-addressed and shared. The retrieval journal says
    which query set fetched each one.
- **VAL8-D3 — neutral extraction, paid only for the Challenge's own papers.**
  - `phase2 triage --challenge X` uses the miner edition's Challenge-neutral
    Reader prompt (`miner.hunt.READER_PROMPT`). It writes card schema v2 into
    a shared `backfill-v2/` store, since a neutral card serves every
    Challenge.
  - It extracts only records the profile's query set retrieved and its free
    pre-filter keeps (`LiteratureProfile.triage`).
  - The run record names the Challenge and profile. A battery run's record
    is unchanged.
  - A live run requires `GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR`.
- **VAL8-D4 — per-Challenge applicability is a deterministic grade.**
  - It is not a model field. `LiteratureProfile.grade` scores the card's
    ranked fields, leaving `applicability` out, as the miner's grade does:
    - 3 for a primary domain, or 1 for a secondary one;
    - 1 for a surrogate or learning method;
    - 1 when code is available.
  - The focus rule's thresholds turn the score into a grade from 0 to 3. The
    ranking rule is data (`ranking_rule()`) with a digest.
- **VAL8-D5 — the Challenge's snapshot (schema v3).** `phase2 snapshot
  --challenge X` keeps the profile's v2 cards of grade 1 or more, best first.
  It records:
  - the Challenge, the profile digest, the query set and prompt digests;
  - the ranking rule with its digest;
  - the grade of every card.
- **VAL8-D6 — the session's offer** (the Test Lead's notes 1 and 2).
  - An offer from a v3 snapshot lists cards best first: the brief's 100
    cards follow the ranking.
  - Its session record adds `challenge_id`, `ranking_rule`,
    `ranking_rule_digest` and `unchecked_fraction`, the share of offered
    cards no person has checked.
  - An unranked offer (battery's v1 and v2 snapshots) has none of these
    keys, so its records keep their bytes.
  - `--allow-unchecked-cards` works for cooling and motor as for battery,
    and every tool result still marks an unchecked card.
- **VAL8-D7 — phase 3 refuses another Challenge's literature** (the Test
  Lead's note 4). The CLI and `Phase3Provider` refuse
  `literature_snapshot_is_for_another_challenge`. An unranked snapshot
  counts as battery's.
- **VAL8-D8 — the grant.**
  - `GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR`: USD 4.00 ceiling, 2.49 worst
    case per run, 3 runs, 0.10 cleanup, 360,000 s, expiring 2026-12-31. The
    arithmetic is in `grants/README.md`.
  - **The ceiling binds:** a run opens only while booked spend is at most
    USD 1.41. Running each Challenge with `--max-calls 850` keeps both runs,
    and a third, inside it.

## Design note: attack literature (later, the Test Lead's note 3)

The phase-4 Attacker has no literature tools today. Its per-Challenge
knowledge is the attack-knowledge store, already keyed by Challenge. Once
it gets literature tools, an attack-literature profile follows the same
pattern as the Challenge profiles here:
- a registered query set: adversarial machine learning, benchmark and
  metric gaming, surrogate failure modes and out-of-distribution
  breakdowns, data leakage and contamination;
- a grade that ranks methods against the Attacker's families;
- its own snapshot, offered to the Attacker only.

It is not built here.

## Operator steps (after this PR and the grant are on main)

```
python -m carbon.agent_campaign.graphite.phase2 fetch    --root DIR --challenge chip-cold-plate
python -m carbon.agent_campaign.graphite.phase2 fetch    --root DIR --challenge electric-motor-magnetics
python -m carbon.agent_campaign.graphite.phase2 triage   --root DIR --challenge chip-cold-plate \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR.json \
    --credential-env ENGY_API_KEY --max-calls 850 --run-id cooling-1
python -m carbon.agent_campaign.graphite.phase2 triage   --root DIR --challenge electric-motor-magnetics \
    --grant ... --credential-env ENGY_API_KEY --max-calls 850 --run-id motor-1
python -m carbon.agent_campaign.graphite.phase2 snapshot --root DIR --challenge chip-cold-plate
python -m carbon.agent_campaign.graphite.phase2 snapshot --root DIR --challenge electric-motor-magnetics
```

Then a cooling phase-3 run passes its snapshot:
`--challenge chip-cold-plate --literature-snapshot DIR/backfill-v2/cards/snapshots/<sha>.json
[--allow-unchecked-cards]`.

## Validation

- `tests/cpu/test_graphite_challenge_literature.py` (10 tests) covers:
  - registered and pinned profiles, and battery's query set unchanged;
  - an altered profile is refused;
  - the pre-filter keeps each Challenge's domain and drops the rest
    (category, whole phrases);
  - grades follow the cues and ignore `applicability`;
  - extraction uses the neutral prompt and v2 cards on the Challenge's
    records only;
  - the v3 snapshot is graded and ranked; the offer is ranked, recorded and
    briefed best first;
  - an unranked offer keeps its record keys;
  - phase 3 refuses another Challenge's literature, both ways;
  - a live extraction needs the literature grant;
  - the grant file holds the owner's values.
- **Native:** the new suite, method cards, the phase-2 runner and mutations,
  literature fetch, phase-3 literature and mutations, phase 3, the level
  planner and the miner library: 251 passed, 1 skipped.
- `scripts/check_quality.py --base origin/main`: passed.
- **Canonical:** recorded in the PR.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT). No literature has been fetched
or extracted for cooling or motor. Cards are UNCHECKED until a person checks
them. A card's claims are its paper's, never Carbon's.
