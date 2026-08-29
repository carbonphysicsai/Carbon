# A12 — Wave-A invariant CI closeout candidate

**Ticket:** `.agent/tickets/A12_invariant_ci.md`
**Wave status:** proposed `done`; authoritative `todo` until the exact closeout
head is independently reviewed, explicitly human-authorized, and normally
merged
**Contract status:** ratified by PR #50 and implemented in bounded scope by
PR #51
**Historical ratification branch:** `agent/a12-contract-ratification`
**Historical ratification base:** `37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1`
**Historical ratification base tree:** `8848085952115672a9f90d255e5feb9bee8116db`
**Ratification merge:** `746e56e42c412bc8ba2eeb4d85ed83396e1a084c`
**Implementation branch:** `agent/a12-invariant-ci`
**Reviewed implementation head:** `33b4626a1ffe7d0c65336336a870a8f4a73ab92f`
**Implementation merge / closeout base:** `2a8b273a1167588efb4a11159da5224264d5b37a`
**Closeout branch:** `agent/a12-closeout`

## 1. Purpose, verified base, and authority

This plan records the documentation-only closeout of the exact A12 contract
and bounded invariant-judge implementation already merged on `main`. It adds
no source, test, fixture, workflow, dependency, packaging, or quality-baseline
change. It neither activates Wave B nor begins B-01.

The contract-ratification starting main was freshly resolved before its
historical edit:

```text
commit:    37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1
tree:      8848085952115672a9f90d255e5feb9bee8116db
subject:   Merge pull request #49 from carbonphysicsai/agent/a11-closeout
parent 1:  e2496e92eeae31befdaa430501bb9f00b0e6339e
parent 2:  0daafae840e920f2e3abd63bc26d7321a13f32da
signature: verified=true, reason=valid
```

PR #49 was normally merged at that exact commit. Exact-main push run
`33207423717` completed successfully: CPU job `98971914859` recorded `2310
passed in 63.74s`; Code-quality job `98971915133` recorded `Ruff 757/776`,
`Black 62/68`, removed debt `Ruff 19, Black 6`, zero changed Python files,
and no new debt.

That historical ratification candidate was independently reviewed and
normally merged by PR #50. Its reviewed head
`6695c279728438befd6404fb81c4f7a27e382a67` became parent 2 of merge
`746e56e42c412bc8ba2eeb4d85ed83396e1a084c`; both have tree
`651c568631465a4902d69036a06c937104660d37`. PR #51 subsequently merged the
bounded implementation. Reviewed head
`33b4626a1ffe7d0c65336336a870a8f4a73ab92f` became parent 2 of current
`main` `2a8b273a1167588efb4a11159da5224264d5b37a`; both have tree
`cb7b23d32e3663bbf00704f1e28c16020bfb9226`.

The historical ratification candidate changed exactly six documentation
paths:

```text
.agent/DECISIONS.md
.agent/plans/A12_invariant_ci.md
.agent/tickets/A12_invariant_ci.md
Design_Specs/Build_Out_Constitutional_Overlay.md
agent_pack/README.md
docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

The current closeout candidate changes exactly the separately authorized eight
documentation paths: `.agent/DECISIONS.md`, `.agent/WAVE.md`, the new
`.agent/WAVE_A_REPORT.md`, this plan, the A12 ticket, the constitutional
overlay, `agent_pack/README.md`, and the current implementation ledger. It
leaves every Python file, test, fixture, dependency, package declaration,
workflow, CI job, quality baseline, `Design_Specs/Build_Out.md`, and Wave-B
artifact untouched.

The board and ticket remain administratively `todo`/incomplete on pre-closeout
`main`. The checked ticket and closed board state on this branch are proposals,
not repository authority. They become authoritative only after independent
exact-head review, explicit human authorization, and normal merge of the
closeout PR.

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

Pre-closeout `main` still records A12 `todo`, Wave A incomplete, no Wave-A
report, unchecked ticket criteria, and preimplementation/current-state prose
in the ticket, plan, decision log, overlay, README, and implementation ledger.
That lag is administrative only: PR #50 ratified the contract and PR #51
merged the bounded implementation and tests. This eight-document candidate
reconciles those records while preserving historical evidence as historical.

### IMPLEMENTATION_LAG

None within A12's ratified bounded integration-judge scope. Current `main`
contains the dedicated marked suite, exact machine-readable crosswalk,
fail-closed entrypoint guard, and the Python 3.11 invariant CI job. The suite
has 12 unique row proofs plus 16 infrastructure tests, and the canonical
command passes 28 tests with no deselection, skip, xfail, or xpass. This does
not implement the future capabilities excluded by the row ceilings.

### MIGRATION_REQUIRED

None for this closeout candidate or the current bounded A3–A11 owners. The
branch-head 24-criterion and nine-item Wave-A acceptance audits exposed no
owner repair.

If a ratified invariant cannot be enforced through the current public owner
surfaces, the affected owner must receive a separately reviewed repair before
A12 can close. A12 may not hide that implementation lag with skip, xfail,
deselection, exception swallowing, monkeypatch bypass, or a documentation-only
claim.

### NEW_OWNER_DECISION_REQUIRED

No new owner decision is required to close this exact bounded engineering
milestone. The ratification feasibility audit and merged executable judge
preserve a valid current proof path for all twelve rows.

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

## 4. Merged implementation and CI contract

PR #51 implemented the smallest coherent A12 integration judge within the
ratified scope:

1. all A12 tests live under `tests/invariants/` and carry the registered
   `invariant` marker;
2. exactly A12-R1 through A12-R12 are each exercised by one unique dedicated
   assertion through public owner surfaces or an explicit structural-negative
   guard;
3. `tests/invariants/a12_crosswalk.json` records the exact contracts,
   dedicated nodes, supporting owner nodes, proof kinds, and evidence ceilings;
4. the dedicated Python 3.11 CI entrypoint runs exactly
   `python -m pytest tests/invariants -m invariant -q`; the explicit directory
   remains mandatory because `pyproject.toml` roots default discovery at
   `tests/cpu`;
5. the complete default CPU and no-new-debt quality jobs remain intact;
6. the committed guard fails the lane for missing/empty targets, zero marker
   matches, complete or partial deselection, runtime or collection skip,
   expected xfail, and non-strict xpass;
7. owner tests are references, not imported aggregate proof; no private-state
   manufacture, skip, xfail, deselection, exception swallowing, or weakened
   assertion creates green; and
8. the implementation earns no sandbox, LIVE, scientific, security, network,
   commercial, frontier, product, settlement, chain, weight, emission, or
   production claim.

The exact implementation manifest is the modified
`.github/workflows/ci.yml` plus six added files under `tests/invariants/`:
`a12_crosswalk.json`, `a12_support.py`, `conftest.py`,
`test_a12_crosswalk.py`, `test_a12_entrypoint.py`, and
`test_a12_invariants.py`. No owner source, owner test, fixture, dependency,
package configuration, quality baseline, or authority document changed in
PR #51.

## 5. Failure, repair, and owner-decision gate

The dedicated suite remains an integration judge, not a new semantic owner.
During review, every finding was repaired within the A12 contract/crosswalk/
test/CI scope. No branch-head proof exposed an A3–A11 implementation defect or
required a new scientific, security, protocol, economic, or commercial owner
decision.

The standing gate remains: a future failing A12-R row must preserve the exact
owner meaning and failure; classify the seam as an implementation repair or
owner decision; and block closure/regression acceptance until the owner repair
or smallest named decision is separately reviewed and merged. A12 may never
reinterpret an invariant, manufacture private-state success, or treat
unavailable future authority as implemented behavior.

## 6. Ratification, implementation, repair, and validation evidence

### Review and repair chronology

- **A12-CI-1:** PR #50 candidate head
  `4e85e3cd4b1c0ee9ef4910db24cad60e4b7c397e` was superseded after review
  found that the bare marker command could not discover the required suite
  under the repository's `tests/cpu` default. The ratified contract now uses
  the canonical explicit-directory command everywhere. Final reviewed
  ratification head `6695c279728438befd6404fb81c4f7a27e382a67`
  merged normally as `746e56e42c412bc8ba2eeb4d85ed83396e1a084c`.
- **A12-TEST-1:** implementation candidate head
  `18d4f02895533d3a850217824e44b0d6d587c1b0` was superseded because its
  subprocess cases did not behaviorally exercise the exact committed
  anti-greenwashing guard. The repair copied that guard byte-for-byte into
  temporary suites and covered partial deselection, runtime skip, expected
  xfail, non-strict xpass, and collection-time skip.
- **A12-XWALK-1:** the same superseded head accepted broad proof-kind values
  and arbitrary nonempty ceilings. The replacement locked the exact ordered
  proof kinds and exact bounded ceilings, including the R6, R8, and R12
  limits, and made the infrastructure-node inventory exact and resolvable.
- **A12-R11-1:** the same replacement expanded the dedicated forbidden-score
  proof across both public numeric and Boolean input channels and proved the
  named forbidden set disjoint from every loaded pack input key.
- The combined A12-TEST-1/A12-XWALK-1/A12-R11-1 replacement head
  `bf978b6e073c7b431b2fcb68cf9826bf582903a9` passed 27 invariant tests but
  was later superseded by **A12-XWALK-2**.
- **A12-XWALK-2:** review found lexical owner-path containment could accept
  traversal or symlink aliases. The final repair added strict canonical
  resolution/containment for dedicated, infrastructure, and owner nodes plus
  direct traversal and symlink canaries. Final reviewed head
  `33b4626a1ffe7d0c65336336a870a8f4a73ab92f` passed 28 tests in candidate CI
  run `33248924648` and merged normally as current `main`
  `2a8b273a1167588efb4a11159da5224264d5b37a`.

Superseded heads are chronology only and confer no current review authority.

### Exact executable evidence

The machine-readable crosswalk has 12 ordered rows, 12 unique dedicated row
proofs, 16 exact infrastructure/anti-greenwashing tests, and 28 total tests.
All contract text equals `Design_Specs/Build_Out.md` section 2; all referenced
dedicated, infrastructure, and supporting-owner nodes resolve canonically and
are marked as required; no suite test is unmapped; and the R6 negative-only,
R8 pinned-fixture-only, and R12 declared-incomplete ceilings remain exact.

The supporting-owner regression contains exactly these ten files and passes
2052 tests:

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

Current-main push run `33250521376` completed successfully on
`2a8b273a1167588efb4a11159da5224264d5b37a`: invariant job `99095290077`
recorded `28 passed in 4.22s`; CPU job `99095290170` recorded `2310 passed in
59.52s`; Code-quality job `99095290146` retained `Ruff 757/776`, `Black
62/68`, removed debt `Ruff 19, Black 6`, all five implementation Python files
clean, and no new debt.

The closeout branch audit passes all **24/24** ticket criteria: 12 invariant
rows, six dedicated suite/CI criteria, and six failure/closeout governance
criteria. The exact `Design_Specs/Build_Out.md` section 12 Wave-A acceptance
audit passes **9/9**: CI schema/seed/mock/scoring coverage; LIVE qualification
blocking; exact seven-tool A9 surface; A2-delegated/non-executing A9
validation/estimate; A7 lifecycle, fee isolation, and idempotence; budget-first
published-result polling; A6 allow-listed/requester-bound card storage;
non-emitting fixture-official A8; and EvaluationCard/leaderboard leakage
coverage.

## 7. Maturity and authorization ceiling

```text
A12 SPECIFIED / RATIFIED: YES on current main
A12 IMPLEMENTED: YES for the bounded invariant-judge/CI scope on current main
A12 TESTED: YES for the recorded bounded engineering evidence on current main
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO

A12 WAVE STATUS: proposed done; todo until the closeout PR normally merges
Wave A: proposed closed in its bounded engineering scope; incomplete until merge
Wave B: inactive
```

Wave-A closure is an engineering milestone only and earns none of the listed
qualifications. Neither this branch, a draft PR, local validation, nor green
CI supplies administrative closeout authority. The proposed A12 `done` and
bounded Wave-A closed state become repository authority only after independent
review of the exact closeout head, explicit human authorization, and normal
merge. Wave-B activation and B-01 remain separate future gates; no Wave-B
authority is granted here.
