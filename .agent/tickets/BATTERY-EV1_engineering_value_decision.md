# BATTERY-EV1 — Fixed-candidate engineering-value experiment

**Programme:** battery testnet hardening track (parent #341)
**Status:** `in_progress`, pending delivery in its PR
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Authority:** the owner's 2026-09-25 engineering-value direction and
OWNER-DX-03. Decisions: BATTERY-EV1 (EV1-D1 to D8).
**Depends on:** BATTERY-TESTNET-M3 and M4P (the truth environment).

## Outcome

Carbon compares several models on the same engineering decision. The
decision is: choose, from a fixed set, the charging protocol that reaches
constant-voltage onset soonest under declared constraints. Carbon then shows
whether its scoring prefers the models whose selections the reference
verifies as better. This is public synthetic, off-chain DEVELOPMENT
evidence.

## Scope

- The Engineering Value Contract `carbon.engineering-value-contract.v1` and
  its EV1 instance.
- `carbon/battery/value/`:
  - `contract`: loading and validation;
  - `decision`: measure, select, verify, outcome and agreement metrics;
  - `scoring`: the rules under test on the fixed scoring set;
  - `panel`: reconstructed recipes and labelled controls;
  - `experiment`: freeze, references, panel, evaluate, status and export;
  - `report`.
- `carbon/scoring/weight_profile.py`: `carbon.development-weight-profile.v1`
  (zero-weight semantics). The core Score Pack is unchanged.
- `carbon/scientific_tasks/workbench_value.py`: contract import and a results
  view, public synthetic only.
- `docs/development/BATTERY_ENGINEERING_VALUE_EV1.md`: the operator guide,
  capability inventory, run plan, the charging-time extension plan, the next
  experiment and the design-loop gap.

## Definition of Done

- [x] The contract validates. Client scope, out-of-envelope conditions, an
      off-grid baseline, bad profiles and non-DEVELOPMENT authority are
      refused by name.
- [x] Decision cases, each tested:
  - the known best feasible candidate;
  - a faster but infeasible candidate;
  - no feasible candidate, with correct abstention;
  - incorrect abstention as a missed opportunity;
  - a localized error that changes the selection, with a false
    acceptance;
  - a correctly predicted unacceptable outcome, which is not a model
    failure;
  - boundary uncertainty left UNRESOLVED;
  - missing references and missing outputs;
  - selection isolated from the references;
  - the deterministic tie rule.
- [x] Zero-weight semantics: an omitted leg, all-zero refused, the exact sum,
      a missing positive component refused, a zero component giving 0, and
      the Score Pack parser unchanged.
- [x] End to end through the real truth service and panel path: an
      interrupted run resumes without re-solving or re-reconstructing, then
      evaluate, report and export. Contract and artifact mismatches and
      foreign reference inputs are refused. There is one runner per root, and
      a missing runtime is reported, not faked.
- [x] Workbench: public synthetic import only, and a retained-results view.
- [ ] The authentic run: pinned PyBaMM references, reconstructed members,
      evaluation and report (see the PR).

## Evidence classes

| Class | Status |
|---|---|
| Implemented, tested locally (fixture world) | yes |
| Authentic references (pinned PyBaMM, sandbox CPU) | see PR |
| Isolated containers / GPU / testnet | not applicable to EV1 |
