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

> **Wave-B development-governance transition.** Current main
> `62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
> `0cc4fc8661663b29d954eb617323cc4fefc6c9cb`, records A12 `done` and
> Wave A closed in bounded engineering scope through PR #52. This
> documentation-only candidate proposes Wave B as active bounded-development
> authority, `.agent/WAVE_B.md` v0.4 as its controlling register, and B-01 as
> the next selected `todo` ticket only after this exact candidate is reviewed,
> green, and normally merged. This change does not start B-01.
>
> The executive governance rule supersedes prior multi-role pre-approval,
> exact-byte approval-bundle, and separate activation-closeout prerequisites
> for development. Material decisions must be recorded and the designated
> SciML / Technical Lead, Harshdeep Sharma (`@harshaa765`), must be notified
> through issue #42. Notification is non-blocking unless the lead explicitly
> submits `REQUEST_CHANGES` or directs that the affected change is `BLOCKED`.
> Scientific truth and qualification, security acceptance, rights, live
> economics, launch, deployment, production, LIVE, frontier, product,
> settlement, chain, weight, and emission authority remain human-owned and
> unearned.

---

## Current process rules

- A-1 and A0–A12 are `done` only in their recorded bounded scopes. Wave A is
  closed in bounded engineering scope.
- Wave B becomes active in bounded development scope only after this exact
  governance candidate is independently reviewed, green, and normally merged.
  `.agent/WAVE_B.md` v0.4 then controls, and B-01 is the next selected `todo`
  ticket. This documentation change does not start B-01.
- Development requires no prior eight-role approval, exact-byte approval
  bundle, or separate activation closeout.
- Material decisions must be recorded and notified to Harshdeep Sharma
  (`@harshaa765`) through issue #42. Silence is non-blocking; an explicit
  `REQUEST_CHANGES` or `BLOCKED` direction pauses only the affected change.
- A12 uses exactly the twelve numbered Build Out section 2 rows as its
  denominator. A11 redaction maps to rows 1/4, fee isolation to row 11, and A8
  non-emission to row 9; none creates an extra invariant.
- PR #50 ratified that exact denominator. PR #51 merged the bounded lane with
  exactly `28` tests (`12` unique row-dedicated plus `16` infrastructure).
  Independent closeout audits pass `24/24` ticket criteria and `9/9` Wave-A
  acceptance bullets.
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
- Wave B ticket deliverables remain specified but unimplemented until their
  own bounded ticket branches begin. Later Waves H–N remain planning
  architecture until separately authorized by `.agent/WAVE.md`.

## Current A11 implementation and closeout evidence

A11-R1 through A11-R18 are ratified. PR #46's independently reviewed head
`e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb`, tree
`3d6682803422497efc6bff26451c12d9c306f96c`, merged normally as signed
merge commit `e2496e92eeae31befdaa430501bb9f00b0e6339e` with ordered
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

An independent A11 closeout audit passed **66/66 criteria, 0 FAIL**.
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
A12: done in its bounded invariant-judge/CI scope
Wave A: closed in bounded engineering scope
Wave B: inactive on the exact governance base; proposed active in bounded
development scope only after this governance candidate normally merges
B-01: todo and unstarted
```

No new owner decision or semantic amendment was introduced by closeout. The
full historical reconciliation and defect chain remains in
`.agent/DECISIONS.md` and `.agent/plans/A11_logging.md`.

---

## Current A12 implementation and closeout evidence

The ratified invariant set is exactly, in order:

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
`.agent/plans/A12_invariant_ci.md`. PR #50 ratified the contract from reviewed
head `6695c279728438befd6404fb81c4f7a27e382a67` by normal merge
`746e56e42c412bc8ba2eeb4d85ed83396e1a084c`, tree
`651c568631465a4902d69036a06c937104660d37`. PR #51 then merged the exact
bounded implementation from reviewed head
`33b4626a1ffe7d0c65336336a870a8f4a73ab92f` in PR #51 as merge commit
`2a8b273a1167588efb4a11159da5224264d5b37a`, tree
`cb7b23d32e3663bbf00704f1e28c16020bfb9226`. PR #52 then normally merged
the A12/Wave-A closeout as current main
`62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
`0cc4fc8661663b29d954eb617323cc4fefc6c9cb`.

The implemented invariant lane has exactly `28` tests: `12` unique dedicated
tests in A12-R1 through A12-R12 order and `16` infrastructure tests proving
crosswalk equality, canonical resolution, marker/entrypoint integrity,
fail-closed behavior, and containment. The canonical command is exactly
`python -m pytest tests/invariants -m invariant -q`; no normative bare-marker
form remains. The lane fails closed for a missing/empty suite, zero marker
matches, complete deselection, crosswalk or mapping drift, or prohibited
bypass. Green cannot come from skip, xfail, deselection, exception swallowing,
imported owner tests, private-state manufacture, weakened assertions,
reinterpretation, or bypass.

Main push CI run `33250521376` passed the `28` invariant tests in `4.22s`, all
`2310` CPU tests in `59.52s`, and Code quality at `Ruff 757/776; Black 62/68`,
removed debt `19/6`, five changed Python files clean, and no new debt. The
supporting owner regression passes `2052` tests. Independent closeout audits
pass all `24/24` ticket criteria and all `9/9` Build Out section 12 Wave-A
acceptance bullets; `.agent/WAVE_A_REPORT.md` preserves the evidence and the
unearned ceilings. No implementation repair or new owner decision was exposed.

Exact-main GitHub Actions run `33255939632`, attempt 2, passed on
GitHub-hosted Ubuntu: `28` invariant tests, `2310` CPU tests, and quality at
`Ruff 757/776; Black 62/68`, removed debt `19/6`, zero changed Python files,
and no new debt.

```text
A12 SPECIFIED / RATIFIED: YES
A12 IMPLEMENTED: YES, exact bounded invariant-judge/CI scope only
A12 TESTED: YES, exact recorded engineering scope only
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO
A12 WAVE STATUS: done in its bounded invariant-judge/CI scope
Wave A: closed in bounded engineering scope
Wave B: inactive on the exact governance base; proposed active in bounded
development scope only after this governance candidate normally merges
B-01: todo and unstarted
```

---

## Current next move

The current next gate is independent review, green exact-head CI, and normal
merge of this documentation-only Wave-B development-governance candidate.
Until that merge, current main continues to record Wave B inactive and B-01
`todo` and unauthorized.

After normal merge, Wave B is active only in bounded development scope,
`.agent/WAVE_B.md` v0.4 controls, and B-01 remains the next selected `todo`
ticket, authorized to begin only on its own later branch. No prior approval
bundle or separate activation closeout is required. Material decisions use the
non-blocking issue #42 lead-notification route. Issue #53 should then close as
superseded by executive governance, preserving its comments as historical
coordination evidence.

Every scientific, security, rights, economic, official, LIVE, launch,
frontier, product, settlement, chain, weight, emission, and production path
remains fail closed unless its separate human-owned gate is earned.
