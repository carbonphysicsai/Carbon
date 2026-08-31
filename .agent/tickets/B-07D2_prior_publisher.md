# Ticket B-07D2 - TEST_ONLY prior publisher and disclosure ledger

**Wave:** B candidate
**Status:** todo
**Depends on:** B-07D1, B-07B
**Build Out:** C10 fixture prior pipeline
**Master questions:** MQ-016, MQ-018, MQ-025, MQ-026, MQ-045, MQ-051
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md` §§9.3-9.6, 10, 12; `Landscape_Agent.md`; `Launch_Bar.md`

## Goal

Implement the offline fixture publication pipeline and cumulative disclosure machinery while making learned public activation structurally impossible.

## Definition of Done

- [ ] Implement an injected deterministic publisher over synthetic record fixtures only; integrated practice and qualified official ingestion are later authority.
- [ ] Implement immutable evidence snapshot, eligibility, lineage aggregation/influence caps, association analysis, deterministic coarsening, joint-cell suppression, lag, fixed activation windows, and bounded version changes.
- [ ] Implement persistent `PriorDisclosureLedger` accounting across estimands, scopes, fields, cohorts, provenance, related releases, and version differences; unavailable or conflicting ledger fails closed.
- [ ] Enforce `evidence_cutoff_epoch + minimum_lag < activation_epoch` and prevent evidence produced in an active window from influencing the pack consumed in that window.
- [ ] Make fixture, mock, infrastructure, partial, stale, rights-ineligible, small-cell, identifying, poisoned, and unsupported evidence incapable of producing `BOOTSTRAP_PUBLIC` or `LEARNED_PUBLIC`.
- [ ] Reject any actionable positive item that omits material eligible null,
      negative, mixed, or out-of-scope evidence. Verify `NONE_FOUND` against the
      exact public search scope and cutoff; preserve counterevidence through
      coarsening, publication receipts, supersession, and withdrawal.
- [ ] Generate no free text from private or fixture records and expose no exact recipes, effects, counts, identities, raw Strategy keys, lineages, or protected context.
- [ ] Implement the non-circular fixture staging gate: exact candidate bytes →
      structural/redaction/canary/poisoning/differencing conformance → exact-
      hash delegated structural fixture authorization under B-07R-D8 → one
      atomic fixture-ledger append plus the B-07S-ratified private test-only
      authorization-receipt/snapshot update. This is not science, security-
      acceptance, rights, utility, publication, or release approval. Preserve
      `TEST_ONLY / NOT_UTILITY_QUALIFIED`; provide exact-ref eligibility only,
      never public-channel activation.
- [ ] Specify and test the stronger future public pipeline separately:
      `BOOTSTRAP_PUBLIC` consumes only rights-reviewed curated public
      science/methods/hypotheses and no private Carbon records or lineages;
      `LEARNED_PUBLIC` consumes only eligible qualified official aggregates
      through lineage/confounder controls. Both retain origin and converge only
      after their source-specific construction branch on the common
      candidate bytes → exact-hash utility/leakage and integrity gauntlets →
      exact-hash approvals → publication receipt → one atomic
      disclosure-ledger commit plus public-index activation. A test-only
      authorization receipt cannot satisfy this gate, and Wave B fixtures
      cannot execute a public-class activation.
- [ ] Add eligibility, poisoning, duplicate-lineage, joint-cell, canary,
      release-differencing, contrary-evidence suppression, false-`NONE_FOUND`,
      applicability erasure, raw-string, lag/window, ledger/index TOCTOU and
      race, reciprocal/cyclic-ref rejection, receipt, authority, resource, and
      installed-wheel tests.

## Human input

The exact TEST_ONLY bytes receive only delegated structural fixture
authorization after engineering checks and notification. Science, statistics,
security, protocol, and rights owners later supply the real cohorts, cadence,
lag, bands, diversity metric/floor, public approvers, rights, and public
utility/leakage thresholds. Missing inputs keep public activation unavailable;
fixtures cannot choose production values.

## Must not

Activate public guidance, call observational evidence causal, use informal random noise as the privacy model, or treat a fixture gauntlet as Landscape qualification.
