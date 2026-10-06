## 2026-10-05 — VALIDATOR-09-PHASE3-VARIANT-01: Graphite phase 3 `--score-variant`, refused on every miner door

**Authority.**
- VALIDATOR-09 slice 2 (`.agent/tickets/VALIDATOR-09_development_score_variants.md`),
  the phase-3 part, as the Test Lead assigned it on 2026-10-05.
- OWNER-GRAPHITE-TEST-WAVE-08 §3: survivors become development score variants
  for Graphite pressure runs.
- The Carbon Validator's #654 contract: `load_variant`, `identity()`,
  `score_member`, the import boundary, `declared_score_components` as the
  only data hook, and phase 4 refused `attacker_score_variant_not_supported`.

Everything below is an engineering choice within that delegated authority. No
scientific value, weight, threshold, gate or tolerance is set here. There are
no chain writes, no live runs and no spend.

**Decisions.**

1. **Resolve before spend.** `phase3 run --score-variant VERSION` resolves the
   variant through #654's `load_variant` in `command_run`, immediately after
   the Challenge and level, before the dry run, the grant, a credential, a pod
   or a model call. A refusal is a typed `RunnerRefused`:
   - #654's own codes (unregistered, altered, malformed and the rest);
   - `score_variant_is_another_challenges`;
   - `score_variant_runs_at_level_0_only`;
   - the practice-contract codes of decision 6.
2. **Pinned in the brief and the profile.** The variant's `identity()` goes in
   the brief's `initial_observation.score_variant` and in the Level-0
   permission profile (`score_variant`). The campaign controller records the
   profile's digest at registration and on every launch intent. A root
   registered under another profile refuses the launch (`profile_not_in_force`).
   `recorded_level` recognises the scored profile as Level 0.
3. **Frozen beside the base rule, never in place of it.** `_frozen_rule()`
   returns `VariantRule`, which is the base rule plus `score_member` on
   `member_legs` of the same practice predictions. The base rule still scores,
   compares and decides promotion and delivery. The variant's comparison
   against the baseline is development evidence only:
   - an order under the variant's own score (closest to 1 is best,
     OWNER-TESTNET-WEIGHTS-01 §2a);
   - a gate FAIL ranks last (the EV5 ruling);
   - no margin, and `promotable: false`.

   Any margin or adoption is the science owner's. The Test Lead confirmed
   this design on #668, with one requirement: the agent's practice feedback
   shows the VARIANT's score as its `score`, labelled with the variant
   identity (`score_label`, `score_gate`), so Graphite optimises the variant.
   The feedback keeps the base rule's eligibility and gate failures and its
   `promotable` (`promotion_rule: base`). It withholds the base score, its
   components, deltas and interval. The baseline is shown by its variant
   score.
4. **Labelled everywhere.** Every result gets `label` (`identity()["label"]`),
   and every scored result gets its `score_variant` result. The rule identity,
   the agent's feedback, the session summary and `delivery.json` carry it too.
5. **Checked on resume.** `check_resume` compares the brief's pinned identity,
   digest included, with the provider's, and refuses on a mismatch:
   `score_variant_changed_since_the_session_opened`. This applies both ways,
   variant to none and none to variant. `run_session` refuses a brief naming
   another variant. A run whose brief pins another variant never scores
   (`score_variant_is_not_the_sessions`), but cancellation and reconciliation
   still run.
6. **The legs' value contract is EV4's development decision contract.** The
   Test Lead ruled this on #668, under the owner's delegation: it is
   `ev4-charge-protocol-selection.v1`, never EV5's frozen confirmation or the
   graphite-run5 panel copy.
   - **Declared once, as Challenge data.** It is
     `ChallengeScoring.practice_value_contract`, the digest #654's
     `load_variant` compares with, next to `declared_score_components`.
     `practice_value_contract_file` names the file the legs are read from.
     Battery declares EV4 by digest `sha256:fedd753c…38d1`. Resolution checks
     the committed file still has that digest
     (`score_variant_practice_contract_altered`).
   - **Recorded by each variant.** A variant records the digest it was
     registered against in #654's top-level `practice_value_contract` field,
     now on main.
   - **Refusals.** #654's own refusals apply:
     - an absent digest is `score_variant_malformed`;
     - a bad format is `score_variant_practice_value_contract_malformed`;
     - another contract is `score_variant_practice_value_contract_not_pinned`.

     The runner adds `score_variant_practice_contract_unpinned` for a
     Challenge that pins none (cooling), which #654 accepts.
   - **In every result.** The variant identity carries the digest.
7. **Level 0 only.** At a development level the permission profile is the
   contract variant's own registered digest, so a score variant cannot be
   pinned there without a controller change. A higher level is refused, typed.
8. **Every miner door refuses by name.** `capability_registry.is_development_variant`,
   the data-only name check every door already uses, also reads the score
   variant registry as data: names and digests, never the module. One check
   covers:
   - the capability registry and the contract compiler;
   - validator dispatch;
   - the Challenge registry;
   - the MCP `describe`;
   - Launchpad launch and submit;
   - the daemon and the intake.

   They answer `development_variant_not_served`. A malformed registry fails
   every door closed. The research tools' closed fields and the Graphite
   miner path refuse a `score_variant` or `rule` field before any request is
   built. Each door's test has a mutation-off twin.
9. **Phase 4 refuses.** `phase4 run --score-variant` and
   `AttackerProvider(score_variant=…)` are refused before anything, with
   `attacker_score_variant_not_supported`.
10. **No flag, no change.** Without the flag, no key is added to the brief,
    the profile, a result, a feedback, the summary or the delivery. The
    pinned phase-3 replays are unchanged.

**From #654.** #654 added the top-level `practice_value_contract` field
(required `"sha256:<64 hex>"`, on `ScoreVariant` and in `identity()`). This
slice reads only that field. #654's test fixture now records battery's
pinned EV4 digest.
