# CHALLENGE-AI-COOLING-06 — Level-0 Launchpad construction integration

**Status:** engineering implementation complete; canonical PR checks pending

**Authority:** OWNER-CHALLENGE-FOUNDATION-01,
OWNER-CHALLENGE-DESIGN-01, OWNER-GRAPHITE-TEST-WAVE-01 sections 1, 4 and 5,
and OWNER-LAUNCH-PORTFOLIO-02.

**Predecessor:** `CHALLENGE-AI-COOLING-FOUNDATION-01.md`; counted periodic-cell
study closed out by PR #557.

**Tracking:** `carbonphysicsai/Carbon#342`; one branch and one PR. PR Lead may
take over after the author pushes the reviewable head.

## Outcome

Make the existing periodic straight-channel cold-plate Challenge reachable as
a bounded, declarative Level-0 construction target from Carbon's Challenge
registry and Graphite admission study. The ticket adds:

1. a Challenge-specific construction contract over the existing public
   Gaussian kernel-ridge reconstruction;
2. strict compilation and reconstruction recipes bound to the pinned 400-case
   public TRAIN artifact;
3. a discovery document and Challenge registry entry;
4. a registered campaign/research composition and CPU worker declaration;
5. a Challenge-specific admission-study adapter with every construction
   dimension placed and one attack/control specimen for every Track A check;
6. focused regression tests proving cross-Challenge refusal and preserving the
   battery path.

Shared code remains Challenge-parameterized. A cooling value belongs in the
cooling adapter, never as a new default in shared code.

## Scope

KEEP the frozen periodic straight-channel cell, nine-input public development
population, three-output prediction contract, public TRAIN/PRACTICE artifacts,
registered physical-validity gates and Gaussian kernel-ridge baseline. WRAP
them with the existing Challenge construction, research and study seams.

The only rebuildable family in this ticket is the existing Gaussian
kernel-ridge model. Its `length` and `ridge` choices are the already published
calibration grid. The defaults are the already selected public calibration
result `(8.0, 1e-6)`. These are reconstruction settings, not new physical or
acceptance values.

Out of scope:

- changing the frozen eight-design by six-condition decision study, CFD
  evidence or closeout;
- manifolds, transients, two-dimensional chiplet maps or a physical rig;
- the PB-ADV/Mode-X optimizer or constructed Track B controls;
- creating or revealing a fresh sealed confirmation set;
- the cooling validator/scoring adapter and the Graphite scoring-seam
  migration;
- scientific qualification, security acceptance, customer acceptance, LIVE
  authority, rewards or launch readiness.

## Working decisions

- **COOL-L0-D1 — identity.** The construction token is the existing registry
  id `chip-cold-plate`, version `1.0`.
- **COOL-L0-D2 — bounded vocabulary.** `kernel_ridge`, `length` and `ridge`
  are the only rebuildable construction choices. Unsupported families and
  executable/pretrained submissions remain fail closed.
- **COOL-L0-D3 — public material.** Reconstruction reads only the digest-pinned
  public 400-record TRAIN artifact. Practice reads only the public 100-record
  PRACTICE artifact. No private or counted-CFD evidence enters construction.
- **COOL-L0-D4 — worker.** Reconstruction/practice uses the existing pinned
  Linux CPU isolated carrier and its exact NumPy environment. This ticket does
  not build or authorize a new image and offers no GPU lane.
- **COOL-L0-D5 — admission freeze.** The study adapter intentionally leaves
  the attack budget and evaluator-held fresh confirmation population as
  `HUMAN_INPUT`, so the sheet is not freezable and no Graphite attack wave is
  authorized by this engineering integration.
- **COOL-L0-D6 — downstream split.** PB-ADV, Track B controls, fresh
  confirmation material and the cooling validator/scoring adapter each remain
  separate tickets/PRs.

## Acceptance

- [x] The registry lists cooling as IMPLEMENTED at an exact version and its
  description is derived from executable registrations.
- [x] Cooling resolves to its own campaign; shared workflow code contains no
  new cooling or battery branch.
- [x] Contract validation refuses cross-Challenge families, unknown fields,
  non-grid settings and digest drift by name.
- [x] The compiler produces only a guarded `ColdPlateRecipe` and reconstructs
  the existing KRR model from verified public TRAIN bytes.
- [x] Practice and public-material providers disclose only registered public
  data and never counted/private reference evidence.
- [x] The worker declaration is CPU-only, pinned and DEVELOPMENT-only.
- [x] The study ladder places every contract dimension and its specimens cover
  all eight Track A checks exactly once.
- [x] Missing attack budget and fresh confirmation authority remain explicit
  and fail closed.
- [x] Battery contract, campaign, discovery and study behavior remain covered
  by regression tests.
- [ ] Focused tests, applicable subsystem checks, lint and canonical acceptance
  pass at the delivered head. Local diagnostic: 308 passed, 2 skipped,
  7 known host-limited cases deselected; Ruff passed; study pins show no drift.
  The local Docker/WSL service could not start the canonical wrapper, so PR CI
  remains the canonical authority.

## Maturity ceiling

At most SPECIFIED, IMPLEMENTED and TESTED in DEVELOPMENT scope. This ticket
cannot establish scientific qualification, security qualification, Graphite
wave approval, customer acceptance, production qualification or LIVE status.

## Hub impact

None. The Development Hub is retired by the current delivery protocol; the
ticket, decision record, code, tests and PR are the durable record.

## Human input required

None for this engineering ticket. The fresh confirmation population, attack
budget/security acceptance, validator activation and any later compute spend
remain human-owned downstream gates and stay fail closed.
