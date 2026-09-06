# Ticket B-06 - Validation Dossier and qualification-manifest machinery

**Wave:** B candidate
**Status:** in_progress
**Depends on:** B-02A, B-03, B-04, B-05, A3
**Build Out:** C4
**Master questions:** MQ-003 through MQ-008, MQ-018
**Authority:** `Generator_Validation.md`, `Evidence_and_Envelope_Standards.md`, `Launch_Bar.md`
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

**Selected from:** owner-accepted merged B-05 dependency at main
`2500e51042f39a31f5056c74ce2ac5065657ec2a`, tree
`89763523576cef09f40fd8a205aa86d169d679de`, under B-06-D0. This does not
assert that B-05's ordinary delivery predicate completed.

**Working contract:** `Design_Specs/Validation_Dossier_Manifest_Contract.md`
**Implementation plan:** `.agent/plans/B-06_validation_dossier_manifest.md`
**Evidence:** `.agent/evidence/wave_b/b-06.md`

## Goal

Create the artifact layout and fail-closed workflow that can later earn the right to activate an exact Challenge, without automating scientific signoff.

## Definition of Done

- [ ] Begin the single-ticket PR with the working
      `Design_Specs/Validation_Dossier_Manifest_Contract.md`, material
      decisions, plan, and SciML/statistics/protocol/security notification;
      implement coherent vertical slices against that contract; then review
      the final contract, implementation, tests, and stable evidence together.
      Require applicable validation and exact-head `Merge gate`; obtain fresh
      read-only Codex/GPT review of the complete diff; repair or disposition
      every finding; require distinct non-author human approval carrying the
      closed receipt, successful `GPT review gate`, and zero unresolved review
      threads; and normally merge the exact reviewed tree. Any tree change
      requires rereview, and a
      separate contract PR requires an exception in
      `.agent/DELIVERY_PROTOCOL.md`. Notification is not ratification and
      silence is no gate. Scientific/security qualification and Challenge
      activation remain human-owned and fail closed.
- [x] Implement D1-D12 Dossier slot identities, evidence refs, status, signer roles, supersession, and exact Challenge binding.
- [x] Include population, SamplingPlan, generator conformance, reference, representation, measurement, statistical sufficiency, secrecy, censoring, limitations, and reproducibility sections.
- [x] Add explicit evidence slots and typed manifests for manufactured-solution
      refinement and observed-order studies, planted-defect/mutation campaigns,
      analytic or limiting-case anchors, primary/witness convergence,
      reference disagreement, generator-oracle adversarial tests, measurement
      floors, decision-resolution studies, and residual limitations.
- [x] Enforce cross-section non-substitution: MMS or another verification
      campaign alone cannot pass physical-model validation, target-population
      adequacy, SamplingPlan adequacy, customer context-of-use adequacy,
      product qualification, or a LIVE decision. Every claim must reference the
      evidence class that can support it.
- [x] Require generator-conformance evidence to remain distinct from reference
      adequacy and require both to remain distinct from measurement adequacy.
      Agreement between two layers cannot satisfy the missing layer's section.
- [x] Require the statistical-sufficiency and reproducibility sections to bind
      the exact decision-interval method, dependence assumptions and evidence,
      reconstruction-by-case and reconstruction-by-stratum interaction
      diagnostics, empirical or
      simulated interval coverage, power by stratum, censoring/missing-cell
      treatment, and any sequential stopping or false-elimination audit.
- [x] Implement qualification-manifest construction and exact hash checks against the active registry record.
- [x] Reject missing, placeholder, fixture, unsigned, wrong-version, stale, malformed, mismatched, role-confused, or claim-inadequate evidence.
- [x] Keep human approval distinct from schema completeness and code execution.
- [x] Add lifecycle, signature-slot, mismatch, placeholder,
      MMS-only-qualification, evidence-role-substitution,
      generator/reference-collapse, and no-LIVE-with-fixtures tests.

## Human input

Scientific, statistics, security, launch, and independent-review owners produce and sign the required evidence. Agents never set pass/fail.

## Second-review repair checkpoint

Slices 1 through 4 are implemented on the B-06 ticket branch. Slice 2 adds the
exact typed evidence-manifest subject graph, explicit claim/evidence matrix,
pending-ratification statistical/dependence scope, intended/realized attempt
accounting, secrecy/role-separation bindings, scoped limitations, and a
separate deterministic canonical profile. The D1-D12 identities are unchanged.

Slice 3 adds an exact qualification-manifest candidate, closed artifact set,
external per-role signer-authorization result seam, deterministic candidate
identity, and a pure comparison with an explicitly supplied immutable A3
`ChallengeRecord`. It compares exact qualification snapshot, required slots,
artifact IDs/digests, dossier, measurement set, fixture/currentness, and draft
lifecycle compatibility. It performs no registry lookup or mutation, artifact
dereference, signature verification, scientific approval, or LIVE transition.

Slice 4 adds a separate canonical campaign-manifest domain with exact
prospective acquisition and externally supplied result records for MMS/
refinement/observed order, planted-defect mutation, analytic anchors,
primary/witness convergence and reference disagreement, generator-oracle
adversarial work, measurement floors, decision resolution, and residual
limitations. It reuses existing B-02A/B-03/B-04/B-05 identities, preserves
explicit evidence-to-claim mappings, and provides no campaign execution,
threshold, computed interval, winner selection, scientific verdict, or
qualification path. Unusable, fixture, placeholder, stale, or failed records
cannot satisfy the dossier boundary.

The first fresh complete-diff review returned `FINDINGS` for three
machine-implementable defects. `B06-CR-001` repairs recursive fixture-origin
projection through references, supersession, candidates, and artifacts.
`B06-CR-002` requires every required complete D1-D12 section to cite the exact
primary ref derived from its supplied typed manifest. `B06-CR-003` applies the
existing campaign document ceiling to encoders and therefore digest/ref
helpers. The prior exact-head CI and review are stale for the repaired tree;
fresh exact-head CI and a completely fresh complete-diff review remain
required. This is still not ticket completion: approval, merge, and closeout
remain future B-06 delivery work. Real signer authorization
and signature verification remain external and human/security-owned.
`Generator_Validation.md` v2.1 dependence
policy and the corresponding scientific-canon v4.1 additions remain pending
owner ratification; populated structural fields grant no acceptance.

The second fresh complete-diff review at exact head
`5763d14cf5cd0c7a18040d91437990a20c4d6ace` returned `FINDINGS` while
verifying `B06-CR-001/002/003` repaired. This repair addresses exactly
`B06-CR-004/005/006`: fixture > unresolved > registered origin propagation
across complete graphs, pure parity with A3's required-slot reference
missing/placeholder checks, and rejection of conflicting same-version nominal
identities before canonical ordering. Its predecessor CI and both prior
reviews are stale. Fresh exact-head CI, a completely fresh review, distinct
human approval with a closed receipt, protected review gate, merge, and
closeout remain incomplete. B-06 remains `in_progress`.

The third fresh complete-diff review at exact head
`8d23b70cda6a08fd99f0ad4174b7c381e2f7ac7b`, tree
`1dcf6244e4ae64c011e0b93badc21a2830ce45d4`, returned `FINDINGS` while
independently verifying `B06-CR-001` through `B06-CR-006` repaired. This
bounded repair addresses exactly `B06-CR-007/008`: a merely specified campaign
cannot carry or project a result, and D11's decontamination and role-separation
audits must use distinct nominal kind/ID/version identities. Its predecessor
CI and all three prior reviews are stale. Fresh exact-head CI, a fourth
completely fresh review, distinct human approval with a closed receipt,
protected review gate, merge, and closeout remain incomplete. B-06 remains
`in_progress`.

## Must not

Infer qualification from complete fields, passing unit tests, an MMS campaign,
a solver run, cross-code agreement alone, a coding-agent assertion, or an
uncertainty decomposition whose coverage and dependence assumptions have not
been qualified.
