# CHALLENGE-ADMISSION-01: two mandatory challenge-admission studies

**Authority:** owner's 2026-09-30 direction to pressure-test and harden construction
integrity and engineering-value tests as a standard Carbon protocol requirement,
**as amended on 2026-10-01** (OWNER-CHALLENGE-ADMISSION-01, `.agent/DECISIONS.md`,
merged in #467 and #469): an internal development protocol, never mainnet;
review moves from every change to every finding.
**Primary map_ref:** SYSTEM/AGENT-EXECUTION; affects WAVE-C/C-09.
**Scope:** prospective protocol, readiness evidence gate, EV evidence audit and
adversarial regression tests. No production permission expansion, score change,
new paid campaign, or scientific/security acceptance.
**Status:** implementation; bounded engineering completion conditional on required
CI and normal merge under OWNER-DX-03.

## Disposition

KEEP: battery EV1/EV2 history, reference, score, generator and reconstruction.
WRAP: EV results with a read-only audit exposing missing denominators, eligible
ranking and recipe/seed sensitivity. REPAIR: readiness v3 requires both admission
tracks, their scope/criteria/report/evidence/review bindings and no open blockers.

Material engineering decision CA-D1: extend existing readiness, not a second
registry or a permissive runtime. Two independent gates; expansion is a separate
prospective profile. Schema migration at stable catalogue paths retains historical
bytes through git. Unknown criteria/pins remain unavailable, no invented numeric
science threshold. Reversal is a prospective schema migration, not a historical
rescore. Dedicated science/security acceptance remains with the existing owners.

CA-D2: do not amend PR #457 or reinterpret its numerical evidence. Audit its pinned
results read-only; EV3 is draft and needs new confirmation conditions for admission.
No lead message is sent by this task; the user authorised repository work, not
person-directed messages. This ticket and PR retain the engineering decisions.

CA-D3 (2026-10-01 amendment): the trigger-based model.
- Track A records `expansions` (sequence, UTC time, profile, version, what
  widened, permissions digest) and `findings` (an emitted condition with
  digest-bound evidence). No expansion may follow a finding. Acceptance is one
  `LOCK` decision bound to the report, both ledgers and a recorded permissions
  state equal to the scope pin; a later finding voids it. Rejected alternative:
  per-expansion review records, which the owner removed.
- Track B acceptance names its trigger: `STUCK`, `WINNING` or `OWNER_REQUEST`.
- All anti-forgery checks are kept unchanged (digest binding; refusal of empty,
  failed, inconclusive, stale or tampered evidence; review-digest rewrite
  attacks).
- The detector `carbon.battery.value.divergence` emits
  `SCORE_VALUE_DIVERGENCE` (X scores at or above an eligible Y that decides
  better by more than the seed loss band) and `GATE_ANOMALY`; no threshold is
  chosen. The progress noise band is τ's spread over one-seed-per-recipe panels
  (EV2: 0.260; EV1: 0.365).
- The design optimizer is scoped in `docs/development/DESIGN_OPTIMIZER_SCOPE.md`,
  not built.

## Definition of done

- Prospective two-track protocol linked from challenge creation/validation and
  launch documentation; per-profile permission ladder with combined attacks.
- Current readiness records require both tracks; absent/failed/inconclusive,
  mismatched/tampered/empty evidence cannot satisfy launch-approved records.
  (Split 2026-10-01: this item lands with #458; see below.)
- Diagnostic reports do not count controls or ineligible models as real eligible
  models; show coverage and seed-group dependence, undefined statistics and limits.
- Positive specimens and deliberate attack mutations exercise the refusals.
- Pressure-test report records EV1/EV2 limitations without claiming new training.
- Hub records the new requirement without changing existing qualification states.
- (Amendment) Expansion proceeds without review; a finding stops widening and a
  lock is bound to both ledgers; Track B review names its trigger; the
  divergence detector fires on EV2's boundary-optimist control and stays quiet
  for a member that decides best; the noise band is derived from retained seed
  repeats; the optimizer is scoped with its gaps.

## Engineering verification

Native Python 3.11 diagnostics: 95 passed, one module skipped because JAX is not
installed, across admission/audit/readiness and adjacent battery checks. Existing
engineering-value and training-budget rules: 33 passed. Workbench proposal tests:
19 passed. Changed Python passes Black/Ruff; Hub source/render and diff coverage
validate locally, with live PR-body checks deferred to CI. Local canonical wrapper
cannot run without Docker; GitHub's required checks own canonical acceptance.

The adversarial report tests also rewrite the simulated review digest, so a stale
review cannot mask a missing check, empty observation, failed result or open blocker.

PR #458 canonical CI stops before Python acceptance on Ask Carbon's existing
`pilot_html_sha256` release-candidate mismatch. The same mismatch is independently
present at base `af5b8ac0`: recorded `4c9f3916...`, actual `be64f8b9...`.
This change regenerates the catalogue preview, so its new bytes also need a real
release-candidate reconciliation. PR #453 addresses the earlier candidate but does
not certify these later bytes. Do not edit a digest alone or waive the failing
check. Full canonical acceptance and merge remain blocked on that reconciliation.
The first Hub run also exposed the missing authority repin; current-role links are
now pinned to this ticket's committed authority, with historical links preserved.
Workbench's real-worker CI passed 47 tests with three skips. Its freshness check
found the source package needed regeneration after the readiness catalogue update;
the deterministic package and manifest are now regenerated and pass that check.

## Split delivery (owner decision, 2026-10-01)

On the owner's instruction "split 458 so we can keep moving", the core of this
ticket ships separately from #458: the protocol specification, the admission
evidence validator (`carbon/challenge_readiness/admission.py`), the read-only
EV audit, the pressure-test report and the optimizer scope, with their
record-independent tests. The readiness-record wiring (schema v3 records, the
`record.py` launch gate, `--require-admission`, their record/CLI tests) and the
Workbench regeneration it forces stay in #458, held until a new Ask Carbon
release candidate pins the regenerated Pilot Designer page. Until then the
readiness gate is specified, not enforced; no readiness record can be
launch-approved without the owner (the unchanged human-reserved rule).

## Remaining scientific execution

No challenge has passed this protocol. The new schema enforces completeness of
maintainer-held assertions and file hashes, not reviewer identity or scientific
truth. Real isolated adversarial campaigns, approved per-challenge numerical
criteria, an independent reviewer and fresh confirmation remain required. This
standard does not reintroduce the optional B-E4 research programme as a gate.
