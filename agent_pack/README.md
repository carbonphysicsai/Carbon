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
- A0–A10 are done in the bounded scopes recorded in `.agent/WAVE.md`.
- **A10's documentation-only closeout merged normally in PR #38 as
  `404c039596b487cf2649bb1d73b80e9b49baaced`; that merge is ancestral to
  current `main` `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`.**
  A10 is `done`
  only for the exact bounded in-process fixture leaderboard scope; the
  closeout adds no implementation or test evidence beyond the already-merged
  bounded work.
- Current main also contains candidate-only Wave B planning. Wave A remains
  controlling and incomplete; Wave B is inactive, and no B ticket is
  authorized until every recorded activation gate is separately satisfied.
- A11 and A12 remain `todo` on current main. PR #39 normally merged and
  ratified the exact A11-R1–A11-R17 bounded operational-observability contract
  as current-main commit `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`.
  Current main still contains no A11 implementation or focused A11 test.
- Draft implementation PR #46 is blocked by
  `P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`; its earlier generic-dataclass
  defect is repaired on that branch, but shared canonical A11/A5/A7 enum
  singletons still cross its sink seam. Its stale `66 PASS / 0 FAIL` claim is
  withdrawn, and its branch evidence is not current-main authority.
- A11-R18, the immutable A11-owned sink-snapshot amendment, is a
  documentation-only candidate. It selects fresh per-call primitive-only
  snapshots rather than an A5/A7 owner migration or weakened sink isolation.
  It is ratified only after independent review, explicit human authorization,
  and normal merge. It implements and tests nothing.
- A11 is neither implemented nor tested on current main and is not
  scientifically, security, network, commercially, or production qualified.
  Its current-main Wave status remains `todo`.
- A9 and A10 are not scientifically qualified, security qualified, network qualified,
  commercially validated, or production qualified.
- A10 implements only the bounded fixture projection. It does not provide a
  production provider or publication feed, an official/LIVE board, public
  identity or authentication, hotkey/anonymized/timestamp publication,
  transport, web/HTML publication, durable persistence, official score
  precision or cadence, adaptive-query security qualification, cross-Challenge
  or global ranking, frontier/Product Qualification authority, commercial
  ranking, settlement, treasury, chain, Bittensor, weights, emissions, A11
  logging/metrics, or A12 aggregate-invariant work.
- Build Out v1.4 remains current detailed sequencing, interpreted through the constitutional overlay.
- Read `CONSTITUTION.md` and `.agent/INVARIANTS.md` before every new ticket.
- Orientation + KEEP/WRAP/REPAIR/REPLACE.
- Baseline tests before/after each ticket.
- One bounded ticket per branch/worktree by default.
- Do not infer scientific/security/network/commercial/production qualification from test success.
- Current-main Wave B and later Waves H–N in the Agentic Master Plan are
  planning architecture only until their exact activation gates are
  explicitly satisfied.

## A11-R18 candidate summary

The public service-request operations remain exactly `emit_event(event)`,
`increment_counter(metric)`, and `observe_duration(stage, duration_ns)`.
Request enums and owner values are validated inputs only; they are never future
sink arguments. The future sink boundary uses fresh exact manual slotted
non-dataclass values:

```text
SubmissionEventSnapshot(kind, submission_id, submission_state, score_status)
BoundaryErrorSnapshot(error_code)
CounterMetricSnapshot(metric_name)
DurationMetricSnapshot(stage, duration_ns)
```

Their fields contain only exact built-in `str`, `int`, or `None` values mapped
from A11-owned fixed literal tables after exact request validation. They retain
no enum, `SubmissionId`, request, owner, mapping, exception, or arbitrary
metadata reference. The future ordered public surface has exactly eighteen
names: the previous fourteen public names plus these four snapshot types.

The revised structural, non-runtime-checkable Protocol seams accept only
`SubmissionEventSnapshot | BoundaryErrorSnapshot`, `CounterMetricSnapshot`,
and `DurationMetricSnapshot`. Each admitted call creates one fresh snapshot;
mutation through an A11-supplied sink value cannot alter caller, owner,
retained, concurrent, or later A11 state. This does not claim that A11
sandboxes a sink that independently imports and mutates unrelated process
globals.

---

## Current next move

1. independently review the exact documentation-only A11-R18 amendment;
2. normally merge the exact reviewed amendment only after fresh explicit human
   authorization through the review workflow;
3. synchronize blocked draft PR #46 with the exact amendment merge;
4. repair PR #46 to implement the immutable A11-owned snapshot boundary; and
5. independently review the repaired exact implementation before PR #46 may be
   marked ready or merged.

A12 remains `todo` and separately authorized; Wave A remains incomplete; Wave
B remains inactive; every official, LIVE, evidence, Challenge-health,
frontier, product, settlement, chain, weight, and emission path remains fail
closed.
