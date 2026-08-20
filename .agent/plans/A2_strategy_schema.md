# Plan — A2 Strategy schema and `dry_validate`

**Ticket:** A2 only (`.agent/tickets/A2_strategy_schema.md`)

**Starting commit:** `e696cc43ace96a963f00bb28394da03d35eb267e`
**Relevant specifications:** root `AGENTS.md`; `SPEC.md`; `Design_Specs/Build_Out.md`
C2; `Design_Specs/Miner_MCP.md`; `Design_Specs/Data_Management.md`;
`Design_Specs/Trustless_Verification.md`;
`Design_Specs/Build_Out_Protocol_Extension.md`;
`.agent/{WAVE,DECISIONS,INVARIANTS}.md`; current context documents; and the
ratified A2 contract supplied for this ticket.

## Pre-implementation gate

- Fresh fetches resolved `origin/main` and `HEAD` to the required starting
  commit. The checkout was clean.
- A1 is `done`, A2 is `todo`, and the former A1 sequencing hold is closed.
- PR #9's final head `a247bb189d44ddf18de504572ef620cf5d501d10`
  and merge `819da3c163c2fb9476a6881aab8740cc6984066e` are ancestral to the
  starting commit.
- Current-main CI run `32330063194` passed both CPU tests and the quality gate.
  A fresh Python 3.11 environment also passed the supported installation and
  baseline: `python -m pip install -e ".[dev]"` followed by
  `python -m pytest -q` reported 27 passed.
- No canonical A2 module, API, plan, or CPU test was present at the starting
  commit.

## Existing implementation and classification

- **KEEP** `carbon/schema/` as the canonical package boundary.
- **KEEP as evidence only** the four cold-discoverable names in
  `carbon/backbones/__init__.py`: `deeponet`, `fno`, `physicsnemo_fno`, and
  `uno`. Validation will own an immutable schema-level constant and will not
  import or query the mutable runtime registry.
- **REPLACE as canonical A2 semantics** the defaulting, aliasing, coercion,
  lowercasing, and clamping behavior in `carbon/common/strategy_schema.py`.
  The legacy module remains untouched for historical callers; migrating those
  helpers is not required by A2.
- **KEEP as historical evidence only** `poc/schema/strategy_poc_v1.json` and
  `poc/validator/schema_check.py`. The PoC's `poc_v1`, `fno1d`, clamp, seed, and
  handoff behavior is not promoted into Strategy v1.0.
- **DO NOT IMPLEMENT** `Design_Specs/Strategy_Schema.md`; it is explicitly a
  pending v1.1 proposal.

## Resolved source conflicts

At implementation start the ticket text named `strategy_version`, while
miner-facing examples used `schema_version` and some SPEC/Miner MCP examples
showed a richer object-valued backbone and top-level training/loss fields. The
ratified A2 contract resolves the wire envelope to exactly four required
fields: `schema_version`, `challenge_id`, scalar `backbone`, and object
`parameters`. The Miner MCP scaffold is now reconciled to that envelope; the
pending Strategy Schema proposal remains unratified future design input.
`parameters` is inert and does not ratify any scientific knob catalog. For
OQ-008, the ratified contract settles only A2's declarative schema/validation
boundary. It does not close the broader execution threat model:
the permitted execution surface, sandbox/process isolation, parser and resource
limits, and production security/operations qualification remain unresolved.

## Implemented changes

1. Add immutable `ValidationIssue` and `ValidationResult` types plus pure
   `dry_validate(strategy: object)` under `carbon.schema`.
2. Validate exact built-in JSON container/scalar types without producing a
   normalized copy, coercing, defaulting, constructing models, consulting the
   registry, or importing optional dependencies. Use iterative traversal with
   active-ancestor cycle detection and completed-container tracking so hostile
   depth, cycles, and shared DAGs cannot trigger recursive or repeated-work
   non-termination.
3. Reject fixed-node unknowns and recursively reject an explicit, versioned
   vocabulary of capability and official-control fields under `parameters`.
   Match only superficial spelling variants of reserved names; arbitrary key
   semantics and string contents remain inert. The denylist is defense in
   depth, not executable-intent detection.
4. Use stable codes, generic non-echoing messages, escaped JSON-Pointer-like
   paths, and final deterministic issue sorting.
5. Export only the A2 public result types and validation function from
   `carbon.schema`; do not add hashing, challenge lookup, execution, transport,
   scoring, fee/FSM, or persistence behavior.

## Identifier decision

Both identifiers must already match the ASCII grammar
`[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`. This deliberately permits the lowercase
underscore/hyphen forms used by current ordinary repository identifiers while
excluding Unicode, uppercase aliases, whitespace/control characters, dots and
`..`, slash/backslash paths, empty segments, and leading digits. Validation
does not normalize input.

## Expected files

- `.agent/plans/A2_strategy_schema.md`
- `carbon/schema/strategy.py`
- `carbon/schema/__init__.py`
- `tests/cpu/test_strategy_schema.py`
- completion evidence in `.agent/{DECISIONS,WAVE}.md` and
  `.agent/tickets/A2_strategy_schema.md`

## Verification

- Focused Strategy tests, then the full default CPU suite.
- Strict Ruff and Black checks on changed Python files.
- Repository no-new-debt quality gate using the exact A2 base SHA.
- `git diff --check` and an isolated installed/outside-tree import diagnostic.
- A hostile import/runtime diagnostic proving validation does not load optional
  scientific/Bittensor packages or touch registry, seeding, scoring, TrainEval,
  filesystem, network, randomness, clock, or environment services.
- Re-run the existing PoC smoke baseline if feasible; preserve and report any
  unchanged inherited failure without repairing it in A2.

## Risks and unresolved values

- Exact parser byte, depth, node, string-length, and error-count limits remain
  security/operations decisions. A2 does not repurpose legacy training limits
  as parser limits. Iterative traversal and cycle detection address
  non-termination now and keep explicit counters/limits addable later.
- `parameters` has no execution semantics in A2. Later execution must explicitly
  register and understand a field before acting on it, must never execute,
  import, fetch, blindly forward, or silently drop unknown fields, and must
  independently enforce the qualified sandbox/resource policy.
- This ticket does not define persistent canonicalization or `strategy_hash`;
  A7/evidence work owns submission identity.
- Passing A2 tests establishes IMPLEMENTED/TESTED schema behavior only, not
  scientific validity, end-to-end isolation, LIVE readiness, or production
  qualification.

### Implementation result

A2 is locally **IMPLEMENTED** and **TESTED** on
`agent/a2-strategy-schema`. The public boundary is
`carbon.schema.{ValidationIssue,ValidationResult,dry_validate}`; it recognizes
only the ratified four backbones and returns immutable, deterministic,
miner-safe issues without returning a normalized document or defining a hash.
An initial local adversarial pass drove regression fixes for shared DAG
traversal and path ambiguity. Independent review on draft PR #12 subsequently
identified the overly broad semantic classifier, generic string-value
heuristics, non-ASCII public paths, specification/status drift, and quality
attribution corrected by the focused follow-up on this branch. Independent
rereview of that correction remains outstanding.

Verification from the exact starting commit:

- Pre-edit supported install and default CPU baseline: 27 passed.
- Focused A2 suite: 181 passed.
- Full default CPU suite: 208 passed.
- Ruff and Black: all three changed Python files strict-clean.
- Repository quality ratchet: passed at Ruff 757/776 and Black 62/68, unchanged
  from the A2 base; A2 added no Ruff or Black debt. The 19 Ruff and six Black
  reduction is cumulative from older baseline work, not attributable to A2.
- `git diff --check`: passed.
- A fresh non-editable, no-dependency wheel imported from `site-packages`
  outside the checkout; validation succeeded while all optional scientific,
  Bittensor, registry, execution, and other non-schema Carbon imports were
  blocked. No blocked import was attempted or loaded.
- Existing `POC_FAST=1 bash poc/scripts/smoke.sh`: the oracle and three
  protocol fixture runs completed, then pytest exited 2 at the unchanged
  inherited `ImportError` for absent
  `poc.generators.burgers1d.role_seed`. A2 does not repair that PoC defect.

No A3+ registry qualification, seeding, scoring, cards, hashing, persistence,
fees/FSM, execution, transport, leaderboard, logging, Bittensor, or scientific
behavior was added. External review/merge remains outstanding, so the Wave
board remains `in_progress`; scientific validity, end-to-end isolation, LIVE
qualification, and production qualification remain explicitly unclaimed.

Draft PR #12 review correction verification:

- Focused A2 suite: 231 passed.
- Full default CPU suite: 258 passed.
- Ruff and Black: both correction Python files strict-clean.
- Repository quality inventory: Ruff 757/776 and Black 62/68, unchanged from
  the exact A2 base; no A2 debt was added. The gate's 19 Ruff / six Black
  reduction is cumulative against the older committed baseline.
- `git diff --check`: passed.
- A fresh no-dependency wheel imported from `site-packages` outside the tree
  with optional scientific/Bittensor and every non-schema Carbon boundary
  blocked; no blocked import was attempted or loaded.
- The reconciled Miner MCP Strategy is covered by a positive acceptance test.
- Independent rereview and merge remain outstanding.
