# Ticket B-07B - Research tasks, ExperimentRecords, and receipts

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02B, B-07R, B-07S, B-07A, A11
**Build Out:** Wave B ExperimentRecord seam
**Master questions:** MQ-016, MQ-026, MQ-045
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§7, 11; `Physics_Intelligence_System.md` §§4-5, 10
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Create a typed, asynchronous, idempotent research lifecycle that records intervention evidence without creating a second official submission or score path.

## Definition of Done

- [ ] Consume B-07A's B-07S-ratified shared wire-visible `ResearchTask` and
      receipt primitives without redefining them; implement the state machine,
      idempotency/conflict identity, requester binding, lineage, cancellation
      cutoff/races, infrastructure retry ownership, polling limits, terminal
      receipts, and retention/reuse scope. Internal record models cannot widen
      the wire contract.
- [ ] Keep operational task state separate from scientific outcome and evidence class.
- [ ] Implement `ExperimentRecord` with exact contract pins, independently computed plan diff, evidence class, execution identity, typed failure, resource observations, and aggregate outcome refs.
- [ ] Bind evidence-role identity, source/reference policy identity,
      applicability, uncertainty/limitation refs, population or verification-
      campaign identity, censoring status, and evidence-quality metadata where
      the ratified schema permits. A manufactured-solution result must remain
      identifiable as verification evidence rather than target-population or
      physical-validation evidence.
- [ ] Preserve schema space for a later epistemic-status system without
      inferring or publishing causal authority in Wave B. An absent or future
      status cannot default to `experimentally_supported`.
- [ ] Implement the B-07S-ratified bounded miner-facing `ResearchReceipt` projection with no protected identifiers or private record aliases.
- [ ] Define `STRUCTURAL_ONLY`, `STATIC_EXACT`, `CALIBRATED_RESOURCE_FORECAST`, and `PRACTICE_NON_AUTHORITATIVE` without any conversion to `OFFICIAL_EVIDENCE`.
- [ ] Preserve infrastructure, strategy, reconstruction, generator, reference,
      measurement, and scientific-admissibility failures as separate categories.
- [ ] Retain scientifically meaningful failures without treating infra failures as negative scientific evidence.
- [ ] Preserve failed reference, MMS/mutation, generator-conformance, hybrid-
      component, and later Product Battery experiments as attributable evidence
      classes when authorized, without letting them alter a live Score Pack or
      official historical result.
- [ ] Add idempotency, lineage, cancellation, requester-binding/local-adapter isolation, mutation-isolation, retention-scope, failure-class, evidence-role-confusion, MMS-relabeling, epistemic-default, leakage, and installed-wheel tests; make no authentication or Sybil-resistance claim.

## Human input

Rights/counsel owners approve any ingestion beyond local/private research and
the exact retention/reuse semantics. Security approves requester isolation,
bounded projections, and private-record handling. Science/statistics approve
any evidence-quality or epistemic interpretation. Missing permission excludes
the record from learned aggregation; missing security acceptance leaves the
external service path unavailable.

## Must not

Write A5, A6, A7, leaderboard, frontier, weight, emission, or settlement state;
expose raw miner strings in future public priors; promote verification evidence
into validation or qualification; silently upgrade epistemic status; or claim
task completion proves scientific quality.
