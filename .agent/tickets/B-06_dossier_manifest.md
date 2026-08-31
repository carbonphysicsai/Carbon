# Ticket B-06 - Validation Dossier and qualification-manifest machinery

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-03, B-04, B-05, A3
**Build Out:** C4
**Master questions:** MQ-003 through MQ-008, MQ-018
**Authority:** `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Launch_Bar.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Create the artifact layout and fail-closed workflow that can later earn the right to activate an exact Challenge, without automating scientific signoff.

## Definition of Done

- [ ] Before implementation, produce
      `Design_Specs/Validation_Dossier_Manifest_Contract.md`; record material
      engineering decisions and notify SciML/statistics/protocol/security
      owners; pass applicable document validation and exact-head CI; repair
      every valid Greptile finding with zero Greptile threads unresolved; and
      normally merge the exact reviewed tree. A documented invalid finding may
      be closed with rationale, and any tree change requires rereview. Record
      the exact contract commit in the implementation plan. Notification is
      not ratification and silence is no gate. Scientific/security
      qualification and Challenge activation remain human-owned and fail
      closed.
- [ ] Implement D1-D12 Dossier slot identities, evidence refs, status, signer roles, supersession, and exact Challenge binding.
- [ ] Include population, SamplingPlan, generator conformance, reference, representation, measurement, statistical sufficiency, secrecy, censoring, limitations, and reproducibility sections.
- [ ] Add explicit evidence slots and typed manifests for manufactured-solution
      refinement and observed-order studies, planted-defect/mutation campaigns,
      analytic or limiting-case anchors, primary/witness convergence,
      reference disagreement, generator-oracle adversarial tests, measurement
      floors, decision-resolution studies, and residual limitations.
- [ ] Enforce cross-section non-substitution: MMS or another verification
      campaign alone cannot pass physical-model validation, target-population
      adequacy, SamplingPlan adequacy, customer context-of-use adequacy,
      product qualification, or a LIVE decision. Every claim must reference the
      evidence class that can support it.
- [ ] Require generator-conformance evidence to remain distinct from reference
      adequacy and require both to remain distinct from measurement adequacy.
      Agreement between two layers cannot satisfy the missing layer's section.
- [ ] Require the statistical-sufficiency and reproducibility sections to bind
      the exact decision-interval method, dependence assumptions and evidence,
      reconstruction-by-case and reconstruction-by-stratum interaction
      diagnostics, empirical or
      simulated interval coverage, power by stratum, censoring/missing-cell
      treatment, and any sequential stopping or false-elimination audit.
- [ ] Implement qualification-manifest construction and exact hash checks against the active registry record.
- [ ] Reject missing, placeholder, fixture, unsigned, wrong-version, stale, malformed, mismatched, role-confused, or claim-inadequate evidence.
- [ ] Keep human approval distinct from schema completeness and code execution.
- [ ] Add lifecycle, signature-slot, mismatch, placeholder,
      MMS-only-qualification, evidence-role-substitution,
      generator/reference-collapse, and no-LIVE-with-fixtures tests.

## Human input

Scientific, statistics, security, launch, and independent-review owners produce and sign the required evidence. Agents never set pass/fail.

## Must not

Infer qualification from complete fields, passing unit tests, an MMS campaign,
a solver run, cross-code agreement alone, a coding-agent assertion, or an
uncertainty decomposition whose coverage and dependence assumptions have not
been qualified.
