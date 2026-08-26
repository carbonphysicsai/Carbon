# Ticket B-06 - Validation Dossier and qualification-manifest machinery

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-03, B-04, B-05, A3
**Build Out:** C4
**Master questions:** MQ-003 through MQ-008, MQ-018
**Authority:** `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Launch_Bar.md`

## Goal

Create the artifact layout and fail-closed workflow that can later earn the right to activate an exact Challenge, without automating scientific signoff.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Validation_Dossier_Manifest_Contract.md`, obtain independent
      SciML/statistics/protocol/security review and explicit human ratification,
      and merge that contract normally; record the exact contract commit in the
      implementation plan.
- [ ] Implement D1-D12 Dossier slot identities, evidence refs, status, signer roles, supersession, and exact Challenge binding.
- [ ] Include population, SamplingPlan, generator conformance, reference, representation, measurement, statistical sufficiency, secrecy, censoring, limitations, and reproducibility sections.
- [ ] Require the statistical-sufficiency and reproducibility sections to bind
      the exact decision-interval method, dependence assumptions and evidence,
      reconstruction-by-case and reconstruction-by-stratum interaction
      diagnostics, empirical or
      simulated interval coverage, power by stratum, censoring/missing-cell
      treatment, and any sequential stopping or false-elimination audit.
- [ ] Implement qualification-manifest construction and exact hash checks against the active registry record.
- [ ] Reject missing, placeholder, fixture, unsigned, wrong-version, stale, malformed, or mismatched evidence.
- [ ] Keep human approval distinct from schema completeness and code execution.
- [ ] Add lifecycle, signature-slot, mismatch, placeholder, and no-LIVE-with-fixtures tests.

## Human input

Scientific, statistics, security, launch, and independent-review owners produce and sign the required evidence. Agents never set pass/fail.

## Must not

Infer qualification from complete fields, passing unit tests, a solver run, a
coding-agent assertion, or an uncertainty decomposition whose coverage and
dependence assumptions have not been qualified.
