## 2026-10-05 — GRAPHITE-ATTACK-IDENTITY-01: the attack engine counts constructions by their rebuilt artifact; the copy probe; cooling's and motor's confirmation roles sealed

**Authority.**
- OWNER-GRAPHITE-TEST-WAVE-04 §1 (owner, 2026-10-05, Q7, record PR #592):
  anything that counts, limits, deduplicates or rewards *distinct
  constructions* identifies them by the rebuilt artifact (the
  trained-parameter or built-artifact digest the reconstruction rule binds),
  never by recipe or expression text. Participant-keyed limits are
  unaffected.
- OWNER-GRAPHITE-TEST-WAVE-05 §4 (record PR #593): the sealed confirmation
  roles `cooling-graphite-confirmation-v1` and
  `motor-graphite-confirmation-v1`, beside battery's
  `graphite-confirmation-v1`.
- The Test Lead's work items for §1 (attack engine and B2, the knowledge
  store, a copy probe, and cross-run proposal identity found by the Graphite
  executor).

Every choice below is an engineering decision within the attack engine's
delegated authority (OWNER-GRAPHITE-ATTACKER-01). None sets a scientific
value, threshold, gate or tolerance, touches EV5 or sealed material, the
validator, `carbon/design_search`, `pod_outcome.py` or the attribution
policies, or changes a participant-keyed limit. No live run, pod or spend.

### 1. What the identity is

- **The artifact** (`carbon/agent_campaign/attack/identity.py`
  `artifact_of`): the adapter's own `artifact_identity(rebuilt)` when it has
  one; else the **build identity** of Carbon's rebuilt record
  (`carbon/reconstruction/artifact_identity.py` `build_identity`); else the
  rebuilt record's digest.
- **Why the build identity, not the record digest.** Battery's built record
  (`ChallengeScoring.built_record`, the fields `REBUILT_FIELDS` names) binds
  `strategy_hash`, `plan_digest` and `recipe_digest`, which digest the
  strategy *as written*, and stages them in `recipe.json`. Measured on the
  battery scaffold: making the default `activation: "gelu"` explicit gives a
  different record digest, `strategy_hash`, `plan_digest`, `recipe_digest`
  and staged `recipe.json`, with identical recipe settings, staged data,
  program and seed. The trainer reads only the family, settings and seed
  (`carbon/battery/worker.py`: `recipes.build(recipe["family"],
  recipe["settings"])`, `fit(..., recipe["seed"])`). The record digest would
  therefore count a reworded copy as new. The build identity is the digest
  of the record without those provenance fields (and without the staged
  `recipe.json`, whose family, settings and seed the record binds anyway).
  Same recipe, same seed and same pinned trainer give the same build
  identity; another seed or setting gives another. Cooling's and motor's
  records have the same shape.
- It lives in `carbon/reconstruction/` so Graphite's delivery can bind it
  without importing the attack package, which must stay unreachable from
  the miner surfaces (`tests/invariants/test_attack_store_unreachable.py`).
- **No artifact.** An attempt Carbon rebuilt nothing for (no construction,
  Graphite's own refusal, a path or Carbon refusal before a rebuild, an
  unrebuildable construction) has no artifact. It is counted as an attempt
  and as `without_artifact`, never as a distinct construction. A *breach*
  without one (an exposure, or the path accepting what Carbon cannot
  rebuild) is still a finding, recorded and emitted as before; for distinct
  counts it counts once per **behaviour**: its family, conditions and
  verdict reason (`identity.behaviour_key`; in the store the reason code,
  `knowledge.behaviour_label`, `unspecified` when it is not a short code).
  So it can never be rewarded as distinct by rewording it. Carbon's own
  deterministic harness attacks have no participant construction; each
  declared attack counts once (`declared`).
- **Text identity** (`evidence["construction"]`, `identity.text_identity`,
  `construction_digest` on report rows) is kept as a diagnostic only.

### 2. Every text-keyed count, limit, dedupe or reward found, and the fix

Scope searched: `carbon/agent_campaign/attack/*` (engine, adapter,
analysis, verify, report, benchmark, knowledge), Graphite's `phase4.py`
(Carbon's side), `delivery.py`, `experiment.py`, `phase3.py`.

| Site | What it did | Fix |
|---|---|---|
| `report.summarize` `verified`, `held`, `attempts` | per-attempt counts, the only counts; a reworded copy of a breach counted as a second verified finding | `distinct` added per family and for the report (`identity.distinct`): constructions, held and verified by artifact, breaches without one by behaviour. Per-attempt counts and every finding kept. Report schema v4. |
| `benchmark.b2` `verified_difference` | difference in breached *attempts*: rewording a found breach raised the Attacker's credit | `verified_difference` is the difference in distinct verified findings (`benchmark.found`); `verified_attempts_difference` kept as a diagnostic. B2 schema v2, `identity_rule`. The equal budget stays an attempt budget (what each side spent). |
| `verify.Verdict` | no identity; only `evidence["construction"]` (digest of the construction as written) | `artifact` on every verdict on a rebuilt construction; verdict schema v2. |
| `verify._specimen` folder | keyed by family + the attempt's journal identity, which every session sharing the specimen directory reuses (a second session's different recipe collided with the first bundle, `write_once` conflict, specimen lost) | keyed by family + artifact; a later breach of the same artifact re-checks the bundle there (`reused`). |
| `knowledge` `priors(...)["by_strategy"][...]["found"]` ("strategies that worked") | one entry per finding record, whose digest includes the attempt and specimen text | one entry per distinct finding (Challenge, family, condition, identity). |
| `knowledge.specimens` / `regression_due` / `replay_specimens` | one regression specimen per finding record | one per distinct finding; a reworded copy adds none. |
| `knowledge` priors counts | per-record only | `distinct_constructions`, `without_artifact`, `distinct_findings`, `legacy_findings` beside them (priors v2). |
| `phase4.remember` | stored no identity | passes the verdict's `artifact`, or the behaviour for a finding without one. |
| `experiment` stall evidence | digest of the run's proposal ids only, which repeat in every run | binds the run id and each proposal's recipe digest. |
| `delivery` bundle manifest | proposal id + run id + recipe digest | adds `artifact` (bundle schema v3); `clean_rebuild` checks it, and still reads v2 bundles. |

Checked and left as they are, each with the reason:
- `engine.run_family` budget and `attack_names_are_unique`: Carbon's own
  declared attacks, counted and named by Carbon, never a participant
  construction.
- `engine.control_identity` and `adapter.validate`'s held-out/trained
  duplicate check: Carbon's own controls, identified by input digest so a
  relabelled held-out control is refused; nothing is counted or rewarded,
  and changing it would change battery's Track A records.
- `knowledge._put`: the record digest is storage identity (an attempt is an
  attempt); construction identity is the new `identity` field.
- `verify.record` / `record_engine_findings` finding ids: one per finding's
  evidence, every finding recorded; they stop expansion and reward nothing.
- `phase4._log` (by run id) and `pin_session` (by session): participant- or
  session-keyed, unaffected by §1.
- Graphite's proposal ids within one run (records under the run's own
  root), the next-level proposal ids (they include the run id) and
  `experiment._finding` (its evidence names the run id).

### 3. Proposal ids are run-local labels (the executor's finding)

`p-<hex>` is `digest(journal identity)`: `epoch-1-tool-003` gives the same id
in every run, so `p-891e0fd1ebdb` named an MLP in run 4 and a DeepONet in
run 5. Nothing counted by it. Under §1 the cross-run identity is the rebuilt
artifact everywhere a record leaves its run: the attack store's `identity`,
the specimen folders, the delivery manifest (`artifact` beside `run_id` and
`recipe_digest`) and the stall evidence (run id + recipe digests). A test
runs two runs reusing one id for different recipes: nothing merges, dedupes
or counts them as one (`tests/cpu/test_attack_identity.py`).

### 4. The knowledge store is versioned, never reinterpreted (invariant 10)

- Record schema v2 carries `identity` (`{basis, key}`: `rebuilt_artifact`
  and the digest, `behaviour` and the reason code, or `none`). v1 records
  stay readable; a v2 record without `identity` (or a v1 record with one)
  is corrupt.
- Snapshot schema v2 names its `identity_rule` (`rebuilt_artifact.v1`). A v1
  snapshot is read under `record_digest.v1`: priors v1 and one specimen per
  finding record, exactly as frozen; replay under its digest is unchanged.
- In the live store a v1 record is `legacy_unkeyed`: counted as an attempt
  or finding, never distinct, its specimen kept on its own (a regression is
  never dropped).
- The journal schema (v2, hash-chained) is unchanged. The store's reviewed
  import list is unchanged: the rule's names are kept in the store and a
  test holds them equal to the engine's.

### 5. The copy probe (leaderboard / copy attack)

- **Where:** the shared layer, `attack/identity.py` (`copy_family`,
  `copy_probe`), so every Challenge gets it without an adapter edit.
  Graphite phase 4 runs it on Carbon's side of every session
  (`construction_identity` in the coverage report, schema v6; findings under
  `findings_by_source["copy_probe"]`, through the same controller path).
  It is not construction-specific: it needs only the adapter's `rebuild`.
  `cooling.py` and `motor.py` are not edited.
- **Incumbent:** the adapter's `incumbent_constructions()`, else the
  Challenge's registered scoring baseline (`baseline_strategy()`). Motor
  registers no scoring yet (WAVE-05 §1), so motor's probe is NOT_RUN
  (`no_incumbent_construction`), never a pass, until it does; with its
  scaffold passed in, motor's real rebuild holds.
- **Rewordings:** key order, whitespace, every letter escaped, the default
  seed made explicit, a default setting made explicit (from Carbon's own
  rebuilt settings) and, Level-1-ready, every loss expression wrapped in
  `scale(1, E)` or with its commutative arguments reordered. A rewording
  Carbon will not rebuild is not a copy and is listed apart.
- **Boundary:** the incumbent and the copy are verified by `verify.verify`
  and reported as breaches; the real report, B2, knowledge-store priors
  ("found", distinct findings) and specimens must each count one. The
  **vulnerable specimen** runs the same mechanisms with identity assigned
  from the text as written: they count two, so the detector fires. The
  **valid control** is the incumbent at another seed: two.
- **Level 1:** with `carbon/reconstruction/loss_expressions` (pure, cheap)
  a synthetic Level-1 adapter whose artifact is what training computes holds
  on `scale(1, E)` and commuted arguments; one whose artifact is the
  expression's digest is a FINDING on `scale(1, E)` (packet U3). Nothing
  depends on the Level 1 build in progress.
- Results at this head: battery, cooling: IN_PROGRESS (every attack HELD,
  every specimen FIRED, control PASSED); motor: NOT_RUN without an
  incumbent, IN_PROGRESS with its scaffold.

### 6. Cooling's and motor's confirmation roles are sealed (WAVE-05 §4)

`knowledge.SEALED_IDENTITIES` gains `cooling-graphite-confirmation-role`
(`cooling-graphite-confirmation-v1`, copied from
`carbon/challenge_validator/interface.py` `COOLING_CONFIRMATION_ROLE`) and
`motor-graphite-confirmation-role` (`motor-graphite-confirmation-v1`, copied
from WAVE-05 §4 into this record, the committed public record on this
branch). Both are phrases matched after the same normalisation (NFKC,
format characters, homoglyphs, case, separators). They are listed before
battery's role, which each contains as a token sequence, so a match names
the right role. A record naming either is refused on write and withheld on
read; a finding naming either is an `OTHER_SIGNAL` exposure. Ordinary
repository text gives no false hit: a new role id matches only a line that
names that role, and the scoped cooling condition ids stay at zero.

### 7. Battery's Track A output pin

`carbon/battery/track_a.py` and the engine's attempt records are not
changed; the byte pin holds (see the PR's test results). No pin update.

**Not done here.** Graphite's own phase-3 session metrics outside the
modules above were not audited. A Level 1 adapter must supply an artifact
identity that is the trained result (or an equivalent canonical build), not
the expression digest; the probe will flag one that does not.
