# A12 — Wave-A invariant CI contract candidate

**Ticket:** `.agent/tickets/A12_invariant_ci.md`
**Wave status:** `todo`
**Contract status:** documentation-only candidate; ratified only after independent exact-head review, explicit human authorization, and normal merge
**Ratification branch:** `agent/a12-contract-ratification`
**Starting main:** `37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1`
**Starting tree:** `8848085952115672a9f90d255e5feb9bee8116db`
**Starting subject:** `Merge pull request #49 from carbonphysicsai/agent/a11-closeout`

## 1. Purpose, verified base, and authority

This plan proposes the exact bounded Wave-A A12 invariant manifest and future
CI acceptance contract. It does not implement A12, add or mark an invariant
test, change CI, create `.agent/WAVE_A_REPORT.md`, change `.agent/WAVE.md`,
close Wave A, or activate Wave B.

The contract becomes repository authority only after this exact documentation
candidate is independently reviewed, explicitly human-authorized, and normally
merged. A separate implementation branch may begin only from the resulting
authoritative main and under separate authorization.

The starting main was freshly resolved against GitHub before editing:

```text
commit:    37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1
tree:      8848085952115672a9f90d255e5feb9bee8116db
subject:   Merge pull request #49 from carbonphysicsai/agent/a11-closeout
parent 1:  e2496e92eeae31befdaa430501bb9f00b0e6339e
parent 2:  0daafae840e920f2e3abd63bc26d7321a13f32da
signature: verified=true, reason=valid
```

PR #49 is normally merged at that exact commit. Exact-main push run
`33207423717` completed successfully: CPU job `98971914859` recorded `2310
passed in 63.74s`; Code-quality job `98971915133` recorded `Ruff 757/776`,
`Black 62/68`, removed debt `Ruff 19, Black 6`, zero changed Python files,
and no new debt.

The starting worktree was clean. `.agent/WAVE.md` records A0–A11 `done` only
in their bounded scopes, A12 `todo`, Wave A incomplete, and Wave B inactive.
No remote A12 branch or pull request existed at orientation.

This candidate changes exactly six documentation paths:

```text
.agent/DECISIONS.md
.agent/plans/A12_invariant_ci.md
.agent/tickets/A12_invariant_ci.md
Design_Specs/Build_Out_Constitutional_Overlay.md
agent_pack/README.md
docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

It leaves every Python file, test, fixture, dependency, package declaration,
workflow, CI job, quality baseline, `.agent/WAVE.md`, Wave-B artifact, and
Wave-A report untouched.

## 2. Reconciliation and conflict classification

### NO_CONFLICT

`Design_Specs/Build_Out.md` section 2 is the exact twelve-row mandatory
manifest. The constitutional overlay and A12 ticket provide current Wave-A
projections of those same rows; they do not replace the numbered source,
create a thirteenth invariant, or permit any numbered rule to be omitted.

The following current owner boundaries agree with that manifest:

- A3 owns exact Challenge status and qualification evidence binding;
- A4 owns seed/domain/context separation and leakage controls;
- A5 owns scoring pins, admissibility, score inputs, and scientific status;
- A6 owns internal-to-public positive disclosure projection;
- A7 owns submission identity, lifecycle, retry/refund, and fee isolation;
- A8 owns only a deterministic fixture-official, non-production execution
  stub;
- A9 owns only the bounded seven-tool in-process control/disclosure surface;
- A10 owns only a fixture, public-allow-listed leaderboard projection; and
- A11 owns only bounded in-process positive-construction observability with
  primitive-only sink snapshots.

### DOCUMENTATION_LAG

The short A12 ticket and overlay theme list do not preserve the exact numbered
denominator on their own. In particular, execution isolation, no silent
rescore, and declared-incomplete practice remain mandatory even though the
current overlay shorthand does not list them as separate bullets. Conversely,
A11 redaction, fee/payment isolation, and A8 non-emission are concrete
projections of numbered rows 1/4, 11, and 9 rather than extra invariants.

This candidate repairs that manifest presentation and the post-A11 current
state in the two live maturity summaries. Historical evidence remains
historical and is not rewritten.

### IMPLEMENTATION_LAG

The `invariant` pytest marker is registered, but current main has no marked
test and no `tests/invariants/` directory. CI has no dedicated invariant lane,
and `.agent/WAVE_A_REPORT.md` does not exist. Therefore A12 is IMPLEMENTED: NO
and TESTED: NO. Running the existing owner suites is contract-feasibility and
regression evidence only; it is not a green A12 invariant lane.

### MIGRATION_REQUIRED

None for this ratification candidate or the current bounded A3–A11 owners. The
missing dedicated suite, marker use, CI lane, and Wave-A report are expected
A12 implementation lag, not an owner migration.

If a ratified invariant cannot be enforced through the current public owner
surfaces, the affected owner must receive a separately reviewed repair before
A12 can close. A12 may not hide that implementation lag with skip, xfail,
deselection, exception swallowing, monkeypatch bypass, or a documentation-only
claim.

### NEW_OWNER_DECISION_REQUIRED

No new owner decision is required to ratify this exact current manifest and
future CI lane. The feasibility audit found a current fail-closed proof path
for all twelve rows.

Production sandbox design and security acceptance; scientific tolerances;
LIVE qualification content/signature custody; practice leakage thresholds and
shadow-case methodology; official/mock production backends; receipts and
signatures; frontier, Product Qualification, treasury, settlement, chain,
weight, and emission types; and Wave-B activation remain separately owned.
They are not decided or implemented here.

## 3. Exact twelve-invariant manifest

The identifiers below preserve the exact order and meaning of
`Design_Specs/Build_Out.md` section 2. A `12/12` result always means these
twelve rows—never an alternative count derived from the broader inventories in
`AGENTS.md` or `.agent/INVARIANTS.md`, or from the overlay's derivative theme
bullets.

### A12-R1 — No seed leakage

> **No seed leakage.** Official seeds, derived seeds, draw IDs, or reversible
> identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or
> miner-visible logs.

**Current Wave-A evidence ceiling.** Current proof includes A4
secrecy/domain separation, A6/A9/A10 public projection, and A11
positive-construction/forbidden-material coverage. A11 redaction is evidence
under R1 and R4, not a separate invariant. A12 creates no new public field,
log field, or secret-inspection oracle.

### A12-R2 — Practice isolation

> **Practice isolation.** Nominal practice/research execution never accesses
> official packs, official entropy/seeds, or protected exam data.

**Current Wave-A evidence ceiling.** Current Wave A has no nominal practice
execution backend. Existing fixture-official and mock domains remain
structurally distinct, and unavailable practice paths fail closed. Mock,
light, estimate, and scaffold surfaces are supporting boundary evidence; they
do not redefine practice execution or prove practice quality or security
qualification.

### A12-R3 — Pinned evaluation

> **Pinned evaluation.** Every scored submission is bound to immutable
> challenge / generator / Score Pack / backend (container digest) versions.

**Current Wave-A evidence ceiling.** A3/A4/A5/A7/A8 exact identity and pin
checks are supporting evidence. Pin mismatch fails closed and cannot be
silently normalized, substituted, or reclassified as candidate science.

### A12-R4 — Disclosure allow-list

> **Disclosure allow-list.** InternalResult / Model Card fields are never
> returned on miner-facing APIs unless explicitly allow-listed for the
> disclosure tier.

**Current Wave-A evidence ceiling.** A6 cards, A9 results, A10 rows, and A11
sink snapshots cross only positive allow-lists for their audiences. Generic
serialization, recursive dumping, serialize-then-redact, free-form telemetry,
or default-public fields cannot satisfy this invariant. A11 redaction and
hidden-material exclusion are evidence under R1 and R4, not a thirteenth A12
invariant.

### A12-R5 — LIVE requires qualification

> **LIVE requires qualification.** LIVE challenges require a complete signed
> human qualification manifest for that exact challenge version (not merely
> non-null YAML).

**Current Wave-A evidence ceiling.** A3 exact-version qualification and
fixture-origin/status relabeling guards are supporting evidence. A
deterministic generator or implementation test cannot establish LIVE
authority. Any future qualified-backend-profile requirement remains
conditional on its owner contract; scientific acceptance and signer/key
custody remain human-owned and unqualified.

### A12-R6 — Execution isolation

> **Execution isolation.** Miner-supplied strategies run under enforced
> compute, network, filesystem, and wall-clock limits. Strategy execution
> isolation is a **P0 security invariant** (implementation may live in ops
> docs; requirement is here).

**Current Wave-A evidence ceiling.** Wave A implements no miner-controlled
production runtime. Current proof is strictly the negative, fail-closed
capability boundary: current APIs and dependency seams cannot reach such
execution or mislabel the A8 fixture stub as it. Passing that negative boundary
does not mean a sandbox exists and does not earn SECURITY_QUALIFIED or
PRODUCTION_QUALIFIED status.

### A12-R7 — Infra ≠ science

> **Infra ≠ science.** Infrastructure failures (OOM policy kill, node death,
> queue loss) are never scored as scientific / physics failures and never
> grant emissions.

**Current Wave-A evidence ceiling.** A5 input boundaries and A7/A8 typed
failure paths preserve retry/refund/`FAILED_INFRA` and prevent infrastructure
material from becoming scientific score. Mandatory-gate failure remains
completed scientific evaluation and is not relabeled as infrastructure
failure.

### A12-R8 — Determinism

> **Determinism.** Re-running an identical official evaluation under identical
> versions, seeds, and limits is deterministic within documented tolerances.

**Current Wave-A evidence ceiling.** Current executable proof is limited to
exact pinned fixture reproducibility and exact owner values. A12 does not
choose scientific tolerances or claim production reproducibility.

### A12-R9 — No placeholder LIVE

> **No placeholder LIVE.** Placeholder, fixture, or mock values never enter
> LIVE configuration or emission weights.

**Current Wave-A evidence ceiling.** The current A8 fixture stub remains
structurally non-production and false-emission; A10 remains fixture-only. The
overlay's production-evidence and emission/settlement-entitlement guards are
current authority ceilings under R9. Future frontier, product, receipt,
treasury, settlement, chain, weight, or emission types remain reserved and
must not be invented merely to make a test pass.

### A12-R10 — No silent rescore

> **No silent rescore.** Historical evaluation records are never silently
> reinterpreted under newer packs; new pack ⇒ new scoring_version for future
> runs only.

**Current Wave-A evidence ceiling.** Immutable result/pin/scoring identities,
conflict/no-overwrite behavior, and prospective pack versioning are supporting
evidence. Pin integrity under R3 is necessary but does not replace this
historical-record rule. Current Wave A does not claim a production-qualified
durable historical store.

### A12-R11 — Forbidden score inputs

> **Forbidden score inputs.** Prior similarity/alignment, `estimate`, resource
> forecasts, practice/`light_*` metrics, research information value, exam fee,
> and mock metrics never enter `S_combined` / Yuma weights.

**Current Wave-A evidence ceiling.** A5 forbidden-input construction guards,
A7 fee isolation, and A9/A10 dependency/ordering guards are supporting
evidence. Fee/payment isolation is a required R11 case, not a separate
thirteenth row. A5 remains the scoring owner and A12 cannot add or exempt a
score input.

### A12-R12 — Practice is useful without revealing the realized exam

> **Practice is useful without revealing the realized exam.** Carbon measures
> leakage as incremental ability to infer protected official cases, realized
> stress composition, exact margins, or unresolved ordering after controlling
> for physics performance on evaluator-held shadow cases sampled from the
> declared distribution. Transferable rank improvement can reflect better
> physics and is not itself a leak. Practice remains declared-incomplete and
> outside official lifecycle, score, and scheduling authority.

**Current Wave-A evidence ceiling.** Current Wave A does not implement a
practice execution lane. Its proof is limited to the fail-closed absence of
official lifecycle/score/scheduling authority and the bounded non-executing A9
estimate/scaffold surfaces. The conditional-leakage gauntlet, evaluator-held
shadow cases, methodology, and thresholds remain Wave-B/science work. A12
neither chooses those values nor claims that current practice is useful or
scientifically adequate.

## 4. Future implementation and CI contract

After ratification and separate implementation authorization, A12 must:

1. add dedicated tests under `tests/invariants/` and mark every A12 invariant
   module/test with the already-registered `invariant` marker;
2. exercise all A12-R1 through A12-R12 through current public owner surfaces
   and explicit source/dependency guards where absence is the boundary;
3. include a clear machine-auditable crosswalk from every row to at least one
   dedicated assertion and the supporting owner tests;
4. add a dedicated CI entrypoint that installs the supported Python 3.11 dev
   environment and runs exactly:
   `python -m pytest tests/invariants -m invariant -q`
   The explicit `tests/invariants` path is mandatory because current
   `pyproject.toml` roots default pytest discovery at `tests/cpu`;
5. retain the default full CPU job and no-new-debt quality gate;
6. ensure no dedicated tests, a missing or empty `tests/invariants/`, zero
   `invariant` marker matches, or complete deselection fails rather than
   greens the lane;
7. preserve every existing owner test; never import existing owner test
   functions as the dedicated proof; and never skip, xfail, deselect, swallow
   an exception, manufacture private state, or weaken a failing invariant to
   obtain green CI;
8. make no production sandbox, LIVE, scientific, security, network,
   commercial, frontier, product, settlement, chain, weight, or emission
   claim from a passing engineering suite; and
9. create `.agent/WAVE_A_REPORT.md` and update `.agent/WAVE.md` only in the
   separately reviewed A12 implementation/closeout sequence after exact-head
   evidence exists.

The future implementation may change the dedicated invariant tests, the CI
workflow, the A12 ticket/plan/decision evidence, `.agent/WAVE.md`, and the
Wave-A report only within that separately authorized scope. It may not change
`.ci/quality-baseline.json` to absorb debt.

## 5. Failure, repair, and owner-decision gate

The dedicated suite is an integration judge, not a new semantic owner.

If branch-head implementation validation finds that an A12-R row cannot pass:

- preserve the failing test and exact owner meaning;
- classify the seam as implementation repair or owner decision;
- stop A12 closeout;
- repair the owning A3–A11 component on a separate reviewed change, or obtain
  the smallest named owner decision; and
- rerun the exact invariant, focused owner, full CPU, quality, and governance
  lanes from the repaired authoritative main.

A12 may not reinterpret the invariant, manufacture a private-state success,
or treat unavailable future authority as implemented behavior.

## 6. Feasibility and contract-ratification evidence

The documentation candidate uses existing tests only to establish that the
ratified manifest is implementable without a presently known source repair or
new owner decision. The exact twelve-row audit passed `12/12` on the starting
main. A broad supporting owner run passed `2052` tests:

```text
tests/cpu/test_no_leakage.py
tests/cpu/test_seeding.py
tests/cpu/test_registry.py
tests/cpu/test_scoring_engine.py
tests/cpu/test_card_store.py
tests/cpu/test_submission_fsm.py
tests/cpu/test_traineval_stub.py
tests/cpu/test_mcp_skeleton.py
tests/cpu/test_leaderboard.py
tests/cpu/test_observability.py
```

This is contract-feasibility evidence only. Current main has zero marked
invariant tests, so the future command
`python -m pytest tests/invariants -m invariant -q` must not be reported as a
green A12 result until the separate implementation creates the dedicated lane.

Before opening the contract PR, the exact candidate head must pass:

- the same ten-suite focused owner regression;
- the complete default CPU suite;
- the repository quality ratchet against exact base `37074e9f...`;
- `git diff --check`;
- an exact six-path manifest/protected-blob audit; and
- an exact-head remote/PR topology check.

## 7. Maturity and authorization ceiling

```text
A12 SPECIFIED / RATIFIED:
YES only after this exact documentation contract is independently reviewed,
explicitly human-authorized, and normally merged

A12 IMPLEMENTED: NO
A12 TESTED: NO
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO
A12 WAVE STATUS: todo
Wave A: incomplete
Wave B: inactive
```

Opening or reviewing this contract PR does not authorize A12 implementation,
Wave-A closeout, Wave-B activation, launch, or merge. Those gates remain
separate and prospective.
