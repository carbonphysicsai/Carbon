# Evidence readiness, before execution

EVIDENCE-READINESS-CHECK-01. Read-only DEVELOPMENT engineering inventory, not
scientific qualification, spend permission, operator credentials or a scheduler.
No solver, fitting/training, Docker calls, network or hidden-body reads.

```sh
python -m carbon.challenge_pipeline.onboarding status --challenge motor
python -m carbon.challenge_pipeline.onboarding readiness
python -m carbon.challenge_pipeline.onboarding readiness --challenge f02 --format json
```

`status` now appends this section. Its existing `status.generate/render` API and
historical tool-run receipts remain unchanged. `readiness` ranks eleven jobs by
verified prerequisite count, with tied ranks. Ranking is **not** a launch order
or a value score. The locally available `origin/main` is resolved by Git; there
is no fetch. A missing main is UNKNOWN, not an empty successful inventory. Only
named local main refs are accepted as evidence; HEAD/unmerged branch refs are
not treated as main. Every examined source has a SHA-256, plus the resolved main
commit and observation timestamp. Refetch before acting on a stale local view.

## Seven separate answers

1. **Panel:** main contains the registration binding exact physical tuples and
   all five physical/observer pins. Recompute duplicates and matches against an
   explicit public completed **and** scheduled inventory. Zero matches is valid
   only with a supplied complete inventory, never missing evidence.
2. **Solver/image:** current package digest and immutable image pin agree with
   a public operator-store observation of presence. No inference from an old
   digest/tag, a successful build or absence of failures. The observation must
   match package/image and be no more than 24 hours old (conservative engineering
   freshness bound, not a science tolerance). Check again immediately before
   dispatch; this is not perpetual proof of presence. Pending #1030 rebuilt
   Elmer after its old image disappeared; its dated repin field takes precedence
   over the historical top-level image. Future manifest revisions should carry
   a current pin explicitly; do not overwrite old run identities.
3. **Adequacy:** three separate, nonempty measured results: convergence,
   conservation, **code verification**. Each binds the current image and exact
   case family, its source result and the adopted DEVELOPMENT acceptance bands.
   The tool compares the numbers, not a producer's PASS Boolean. Smoke tests,
   another family's result and pre-rebuild verification do not substitute.
   Missing accepted criteria remain UNKNOWN. Reference failure is a **reference
   finding**, not candidate failure. Tier-2/tool agreement is still separate.
4. **Kit:** inspect its version-bound exported domain contract against **every**
   panel action, registered condition combination and required observable. No
   range inferred from test-panel extrema. The source adapter must preserve the
   merged kit's `domain`/`domain_gaps` checks (#1034 battery, #1035 motor, #1036
   f02), including discrete values/context support. A matching draft is PLANNED,
   not coverage. Data Collection/Model Kits exports this public domain metadata
   from the exact kit revision; no training run is needed for this command.
5. **TRAIN:** actual registered public physical inventory, bound by digest;
   compare action/condition tuples against panel, ignoring rung differences.
   Different seeds/names are not separation. Empty TRAIN or missing inventories
   are UNKNOWN; overlapping or duplicate tuples are NO.
6. **Cheap baseline:** inspect the implemented family adapter and required
   functions in main, without importing/executing producer code. Battery/motor
   use #917; cooling/f02 #994; f08/f13 use the **stronger** #1011 cross-geometry
   and multimode arms, not the weaker cached/plane-wave arms. YES is ready
   software with explicit producer-material requirements, **not** measured V4
   success or full-panel coverage.
7. **Equal budget:** inspect the family-supported #1016 evidence route, which
   wraps #998's replay. Current supported families are battery-v3 (indexed),
   motor and f02 (including indexed contexts). A neutral core without a family
   adapter is NO, not YES. Optimizer owns extending the closed route inventory.

**YES:** the item's bounded basis was examined and satisfied. **NO:** observed
contradiction or known unsupported implemented route. **PLANNED:** sourced
proposal/pending work, with no inspectable completion evidence. **UNKNOWN:**
missing, malformed, stale or unavailable evidence. Pointers and owning session
accompany all answers. Main source identity is a necessary basis, not proof that
a producer's acceptance decision was scientifically justified.

## Public metadata handoff, without moving case bodies

`bindings.json` contains pointers, aliases and pending PRs, never YES overrides.
The per-family `inputs/<family>.json` is an optional **PUBLIC_DEVELOPMENT**
summary of operator/producer evidence; none exists at this ticket's starting
main. Add it only from real public artifacts, not synthetic passing fixtures.
Existing fixtures in the tests are structurally examples, not earned evidence.
No hidden EVAL/STRESS/quiz/tuning inventory belongs here.

Input schema: `carbon.onboarding.evidence-inputs.v1`, `scope:
PUBLIC_DEVELOPMENT`, `challenge` equal to the registry family. Sections:

- `panel`: `cases` with nonempty `action`, `condition`, `rung` coordinate maps;
  `pins` (solver/environment/materials/observer/geometry_grammar, tagged SHA-256);
  `registration` source binding; `reuse` with `inventory_coverage` containing
  COMPLETED and SCHEDULED, and `source` binding. Registration JSON must contain
  `scope` and `panel_digest = identity({cases, pins})`. Reuse index is a list of
  `{identity, state, receipt}`; identity hashes `{case, pins}`, receipt is bound.
- `solver`: `package` binding, `image_digest`, `inventory` binding. Package has
  `image_id` (or #1030's historical `repin_2026_10_10.image_id`). Inventory has
  scope, package_sha256, image_digest, store_id, checked_at (aware ISO timestamp),
  present (Boolean). **Operator** supplies this sanitized metadata, not keys or
  engine paths. Report remains a timestamped observation, not live enforcement.
- `reference.checks`: exactly convergence/conservation/code_verification, each
  with kind, image_digest, family, result and acceptance source bindings. Result
  JSON has kind, image_digest, family and nonempty metrics. Acceptance JSON has
  `status: ACCEPTED_DEVELOPMENT`, kind, family and matching metric-name `[low, high]`
  ranges. Science/owner supplies those criteria; this ticket invents none.
- `kit`: source binding, domain_source binding, required_observables. Domain JSON
  has kit_sha256, action_bounds, optional action_values (discrete restrictions),
  exact supported conditions, observables. Preserve all kit restrictions in
  this adapter; unsupported richer grammars stay UNKNOWN, never approximate.
- `train`: registration and inventory bindings. Inventory has scope and cases;
  registration has `train_digest = identity(inventory)`. Physical separation is
  recomputed, not trusted from a zero-overlap label.

Each source binding is `{path, sha256}`. `identity` is tagged SHA-256 of compact,
sorted-key JSON (same implementation exported by the tool); no manually chosen
authority_main. Metadata has bounded sizes and explicitly allowed paths. Raw
reference values/curves, seeds and detailed inputs never appear in this report.

## Spending rule and today's next action

All seven YES are necessary before money/evidence work, **except outputs that
the exact approved run itself produces**. This exception is not a blank cheque:
the owner/operator names those outputs in that run's grant, with caps, exact
pins and all non-produced prerequisites established. This tool neither waives
items nor executes, grants, draws a bank, or qualifies an exam.

Retained `initial-report.json` is an observation at its stated main, not a live
board. f13's pending 60-mm-port result (≤0.02% power residual) is not yet main
evidence and is not code verification. Data Collection supplies identity-bound
public package/panel/domain/TRAIN/adequacy summaries, including rebuilt-image
MMS results; Optimizer supplies remaining family routes. Read again when those
artifacts merge, without rewriting historical receipts. CODE-VERIFICATION-MMS-01
is the next independent ticket; reuse #1030's Elmer test, not duplicate it.
