# Carbon agent pack — executor-agnostic Wave work

Protocol docs and optional harness notes. **Live board and tickets live at repo root `.agent/`.**

```text
constitutional authority
→ bounded ticket
→ DoD
→ tests
→ review
→ board evidence
→ next ticket
```

---

## Canonical paths

| Path | Role |
|------|------|
| **`/CONSTITUTION.md`** | Repository-wide scientific / implementation / business / publication authority map |
| **`/AGENTS.md`** | Default engineering behavior for every coding agent/human |
| **`/.agent/`** | WAVE, ORIENTATION, DECISIONS, INVARIANTS, tickets, plans |
| **`Design_Specs/Build_Out.md`** | Current detailed build sequencing |
| **`Design_Specs/Build_Out_Constitutional_Overlay.md`** | Migration guard for A8 onward and stale shorthand |
| **`Design_Specs/Agentic_Development_Master_Plan.md`** | Long-horizon A0→agentic-construction plan |
| **`docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`** | Integrated scientific constitution |
| **`Business/Business_Canon.md`** | Business authority outside scientific judge |
| **`agent_pack/EXECUTION_PROTOCOL.md`** | Ticket execution loop |
| **`agent_pack/PLANS.md`** | Plan template for complex tickets |
| **`agent_pack/executors/`** | Optional harness/vendor notes only |

---

> **Draft PR #49 closeout authority gate.** The merged A11 implementation and
> the recorded `66/66` audit are current-main engineering evidence. The A11
> `done` status, checked ticket criteria, closeout wording, and the A12-next-move
> text below are proposed administrative state only. They become repository
> authority only after the exact PR #49 head containing this gate is
> independently reviewed, explicitly human-authorized, and normally merged.
> Until then, current-main administrative authority remains A11 `in_progress`
> in `.agent/WAVE.md`, the A11 ticket remains at `66 unchecked / 0 checked`,
> A12 remains `todo` and unstarted, Wave A remains incomplete, and Wave B
> remains inactive. This draft does not authorize A12 or any later-wave work.

---

> **A12 contract-ratification authority gate.** The current six-file A12
> candidate is documentation only. It preserves the exact twelve numbered
> `Build_Out.md` section 2 invariants and defines a future dedicated CI lane;
> it does not add tests, change CI, implement A12, create the Wave-A report,
> close Wave A, activate Wave B, or authorize launch. It becomes
> `SPECIFIED / RATIFIED` only after exact-head independent review, explicit
> human authorization, and normal merge. Until then A12 remains `todo`, Wave A
> remains incomplete, and Wave B remains inactive.

---

## Current process rules

- Current board remains **Wave A**.
- A0–A11 are `done` only in the bounded scopes recorded in `.agent/WAVE.md`.
- A12 remains separately owned and `todo`. Wave A remains incomplete; Wave B
  remains inactive. No B ticket is authorized until every recorded activation
  gate is separately satisfied.
- The A12 contract candidate changes documentation only and uses the exact
  twelve numbered Build Out section 2 rows as its denominator. A11 redaction
  maps to rows 1/4, fee isolation to row 11, and A8 non-emission to row 9;
  none creates an extra invariant.
- A9 remains only the exact seven-tool bounded in-process Wave-A
  control/disclosure skeleton.
- A10 remains only the bounded in-process fixture leaderboard; it is not an
  official/LIVE board or a frontier, product, settlement, chain, weight, or
  emission authority.
- A11 remains only bounded in-process operational observability with injected
  trusted structural sinks, closed events/metrics, fixed errors, and
  primitive-only snapshots. It supplies no production provider, exporter,
  persistence, dashboard, alerting, authentication, transport, or public API.
- Build Out v1.4 remains current detailed sequencing, interpreted through the
  constitutional overlay.
- Read `CONSTITUTION.md` and `.agent/INVARIANTS.md` before every new ticket.
- Use orientation plus KEEP / WRAP / REPAIR / REPLACE, baseline tests before
  and after each ticket, and one bounded ticket per branch/worktree by default.
- Never infer scientific, security, network, commercial, or production
  qualification from implementation or test success.
- Wave B and later Waves H–N in the Agentic Master Plan remain planning
  architecture until their exact activation gates are explicitly satisfied.

## Current A11 implementation and closeout evidence

A11-R1 through A11-R18 are ratified. PR #46's independently reviewed head
`e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb`, tree
`3d6682803422497efc6bff26451c12d9c306f96c`, merged normally as signed
current-main commit `e2496e92eeae31befdaa430501bb9f00b0e6339e` with ordered
parents prior main `98865dd04c5a4018c8077517cb79aabd6045a468` and that reviewed
head. The reviewed and merge trees are identical; their diff is empty. The
prior-main manifest is exactly `.agent/WAVE.md`, the four
`carbon/observability/` source files, and `tests/cpu/test_observability.py`.

Greptile's exact-head record is `Confidence Score: 5/5`, with no actionable
defect. There are no review threads or formal change requests. Exact post-merge
run `33199541335` completed successfully: CPU job `98945235783` reported
`2310 passed in 62.62s`; Code-quality job `98945235938` retained `Ruff
757/776`, `Black 62/68`, removed debt `19/6`, five changed Python files clean,
and no new debt.

An independent current-main closeout audit passed **66/66 criteria, 0 FAIL**.
Fresh Python 3.11 Linux validation reported:

```text
focused observability: 337 passed
related A5/A7/A9/A10/A11 owner boundaries: 1330 passed
complete default CPU suite: 2310 passed
strict Ruff: passed on all five A11 Python/test paths
strict Black: 5 files unchanged
quality against e2496e92: Ruff 757/776; Black 62/68; removed 19/6;
                           changed Python files 0; no new debt
git diff --check: passed
```

The fresh no-dependency wheel installed with `--no-deps` and imported in
isolated mode outside the source tree:

```text
carbon-0.9.0-py3-none-any.whl
sha256:ea686e933f6f93c72df281e79a3baebcb05f6789b25d4499ff81e937980e94fe
```

It exposes exactly the ordered eighteen-name public surface. The four directly
constructible snapshot types are:

```text
SubmissionEventSnapshot(kind, submission_id, submission_state, score_status)
BoundaryErrorSnapshot(error_code)
CounterMetricSnapshot(metric_name)
DurationMetricSnapshot(stage, duration_ns)
```

The three service operations accept only the ratified request values and pass
only fresh primitive-only snapshots to sinks. The final private identity-bound
weak allocation mechanism is one-shot, consumed before validation, and
collects abandoned allocations; failed, partial, repeated, donor, alternate,
`object.__new__`, and concurrent construction fail closed. No owner/request/
enum object crosses the sink boundary.

```text
A11 SPECIFIED / RATIFIED: YES, A11-R1 through A11-R18
A11 IMPLEMENTED: YES, bounded in-process engineering scope only
A11 TESTED: YES, exact recorded engineering scope only
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: done
A12: todo
Wave A: incomplete
Wave B: inactive
```

No new owner decision or semantic amendment was introduced by closeout. The
full historical reconciliation and defect chain remains in
`.agent/DECISIONS.md` and `.agent/plans/A11_logging.md`.

---

## Current A12 contract candidate

The proposed manifest is exactly, in order:

```text
A12-R1   No seed leakage
A12-R2   Practice isolation
A12-R3   Pinned evaluation
A12-R4   Disclosure allow-list
A12-R5   LIVE requires qualification
A12-R6   Execution isolation
A12-R7   Infra ≠ science
A12-R8   Determinism
A12-R9   No placeholder LIVE
A12-R10  No silent rescore
A12-R11  Forbidden score inputs
A12-R12  Practice is useful without revealing the realized exam
```

The exact normative wording and bounded evidence ceiling live in
`.agent/plans/A12_invariant_ci.md`; the implementation criteria remain
unchecked in `.agent/tickets/A12_invariant_ci.md`. The plan preserves every
numbered Build Out rule, including execution isolation, no silent rescore, and
the full declared-incomplete practice/leakage rule that were not separate in
the former overlay shorthand.

The current `12/12` result is a contract-feasibility audit against existing
A3–A11 owner code/tests. It found no new implementation repair or owner
decision and the broad focused regression passed `2052` tests. It is not a
green A12 lane: current main has no `tests/invariants/` directory and no test
selected by the registered `invariant` marker.

After ratification and separate authorization, implementation must add
dedicated marked tests and a CI entrypoint running exactly
`python -m pytest tests/invariants -m invariant -q`, plus an R1–R12 crosswalk
and separately reviewed Wave-A report/board evidence. The explicit directory
is required because current `pyproject.toml` roots default pytest discovery at
`tests/cpu`. No dedicated tests, a missing or empty `tests/invariants/`, zero
`invariant` marker matches, or complete deselection must fail rather than
green. A failing invariant must stop closeout; green cannot come from skip,
xfail, deselection, exception swallowing, imported owner tests, private-state
manufacture, weakened assertions, reinterpretation, or bypass.

```text
A12 SPECIFIED / RATIFIED: candidate only until review, human authorization, and normal merge
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

---

## Current next move

The current next gate is independent exact-head review, explicit human
authorization, and normal merge of the A12 documentation contract. Only after
that merge may a separately authorized A12 implementation begin from the then
current main. Neither contract publication nor its merge closes Wave A or
activates Wave B. Every official, LIVE, evidence, Challenge-health, frontier,
product, settlement, chain, weight, and emission path remains fail closed.
