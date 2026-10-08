## 2026-10-07 — OWNER-LADDER-THROUGH-LAUNCHPAD-01: construction levels pass only through the Launchpad

**Authority.** The owner, 2026-10-07, relayed verbatim by the Test Lead to
the Launchpad Acceptance session:

> yes, do it that way. Lets start the launchpad work needed now though to build the construction levels in.

"That way" is the Test Lead's proposal, which the owner accepted.

**Decision.**
1. **Construction levels go into the Launchpad now,** built once,
   generically and from data. No level gets its own screens or code path.
   - **The data:** the Challenge's ladder (`carbon/challenge_pipeline/ladder.py`
     and its pipeline record), its level proposals
     (`carbon/challenge_pipeline/proposals/<challenge>/level-N.json`) and the
     development-variant registry
     (`carbon/reconstruction/development_variant_policies/`).
   - **Both doors** offer the same level views and choices, browser and MCP.
2. **Exploration and attacks stay on the development door**
   (`carbon/battery/dev_submit.py`).
3. **No level counts as passed until it also passes real runs through the
   Launchpad.** That means a few real freeze → commit → submit → verdict
   runs, on a separate testnet development-ladder deployment on valV2.
   - The Carbon Validator builds that deployment.
   - It is never the main battery deployment.
   - It is never mainnet until the owner locks a level.
4. **Level 4 runs through the Launchpad from its Phase 3,** because graph
   lowering happens there. Until then, its Launchpad slot is designed, not
   built (OWNER-LEVEL4-GRAPH-ONLY-01).

**Deployment facts (Test Lead, 2026-10-07).** These are facts, not owner
quotes.
1. The development-ladder deployment is VALIDATOR-25, `battery-dev-ladder`.
   It accepts only a dedicated rehearsal hotkey, `carbon-rehearsal-minerC`
   (the owner creates it), never minerA or minerB. The chain allows one
   commitment per hotkey per tempo, so sharing a hotkey would collide with
   rehearsal 3a.
2. It shares the main deployment's live windows, with one exposure account.

**What this amends.** OWNER-GRAPHITE-TEST-WAVE-03 §1 says a development-only
contract variant is never served to a miner, and the Launchpad sends none
(`development_variant_not_served`). That stays true for every deployment
except the development-ladder deployment. There, the Launchpad may send a
variant's recipe:
- only when that deployment says it serves the variant;
- only for a level above its miner-facing level;
- always labelled DEVELOPMENT.

The amendment is prospective, and no recorded run is reinterpreted.

**Unchanged.**
- Every level's bounds, gates and scoring.
- Which level is frozen for miners (the owner's lock under the ladder's
  `LAUNCH`).
- Levels 4 and 5 stay refused by the variant registry until the security
  owner accepts their isolation.
- Weights and settlement. A `development_only` deployment never sets weights
  (`carbon/battery/deployment.py`). Whether the ladder deployment is one, or
  needs a new kind, is the Carbon Validator's design to bring to the owner.

**Ticket:** LAUNCHPAD-LEVELS-01, after LAUNCHPAD-ACCEPT-04 (#778).
