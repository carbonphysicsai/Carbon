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

## Current process rules

- Current board remains **Wave A**.
- A0–A11 are `done` only in the bounded scopes recorded in `.agent/WAVE.md`.
- A12 remains separately owned and `todo`. Wave A remains incomplete; Wave B
  remains inactive. No B ticket is authorized until every recorded activation
  gate is separately satisfied.
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

## Current next move

The next separately authorized Wave-A ticket is A12 invariant closeout. It
must begin with its own orientation and baseline and may not infer Wave-A
completion or Wave-B activation from A11 closeout. Every official, LIVE,
evidence, Challenge-health, frontier, product, settlement, chain, weight, and
emission path remains fail closed.
