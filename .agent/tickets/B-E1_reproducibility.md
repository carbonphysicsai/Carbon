# Ticket B-E1 - R0/R1/R2 reproducibility harness

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-02B, B-02C, B-04, B-05
**Build Out:** Wave B evidence harness
**Master questions:** MQ-007, MQ-008
**Authority:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md` §4 C13-C14 and
§§6-11; `Evaluation_Evidence_and_Validator_Audit.md` §4;
`Miner_MCP_Wave_B_Research_Contract.md` §8.2
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

## Goal

Provide fixture machinery for distinguishing exact identity, numerical reproducibility, and decision reproducibility without inventing tolerances.

## Definition of Done

- [ ] Represent R0 exact artifact/configuration identity, R1 numerical comparison, and R2 decision comparison as separate results.
- [ ] Define reconstruction × whole-case/trajectory evidence identities,
      stratified by the registered stress design, for incumbent and challenger,
      with exact provenance, common-case pairing, and joint reference-
      uncertainty realizations where material. Reconstruction replicates are
      separately realized and producer-independent; registered pairing or
      common random numbers are allowed and all shared dependencies remain
      represented.
- [ ] Preserve reconstruction-by-case and reconstruction-by-stratum
      interaction, heteroscedasticity, representation/execution dependence,
      missing or censored cells, and any deliberately paired training seed or
      hardware role through a qualified crossed/hierarchical resampling method,
      hierarchical model, or conservative bound.
- [ ] Represent reference variability, primary/witness disagreement,
      measurement/reference floors, generator/reference discrepancy,
      reconstruction variability, and finite-case/trajectory sampling variation
      as distinguishable evidence factors. Combine them only through the
      injected, qualified decision procedure.
- [ ] Treat component uncertainty budgets as diagnostics. Permit quadrature or
      zero covariance only when an injected Dossier qualifies the procedure and
      applicability test and the exact fixture incumbent-challenger evidence
      satisfies that test; otherwise use joint propagation or conservative
      bounds and return indeterminate when unresolved.
- [ ] Represent a staged `ReconstructionEvidencePolicy` with static admission,
      registered complete base reconstruction evidence (one or more builds),
      repeat promotion evidence, frozen-build reuse, random stability audits,
      coverage-qualified scientific sequential stopping or extension, and a
      separate heuristic-futility seam. A pre-base or heuristic stop returns
      typed non-scientific `EVIDENCE_DEFERRED`; it cannot become
      `NOT_SUPERIOR`, gate failure, or candidate physics failure.
- [ ] Represent resolved, unresolved/indeterminate, evidence-deferred,
      reference-uncertain, reference-disagreement, reference-not-applicable,
      reference-failed, reconstruction-failed, measurement-unresolved, and
      infrastructure-failed outcomes without collapsing their authority.
- [ ] Define typed contested-outcome plumbing without implementing frontier promotion.
- [ ] Exercise cases where an exact or manufactured anchor is numerically
      flawless but population, measurement, or model-form evidence remains
      insufficient; the decision must remain unresolved rather than inherit the
      anchor's exactness.
- [ ] Inject all tolerances, sample sizes, and power criteria; missing values fail closed.
- [ ] Add deterministic fixture, null/coverage/power, correlated-error,
      heteroscedastic stress, interaction, missing/censored evidence,
      reference-disagreement, measurement-floor, manufactured-anchor-
      overreach, sequential-stopping, false-elimination, ordering,
      hardware-profile, and failure-class tests.

## Human input

SciML/statistics owners derive numerical and decision tolerances, sample sizes,
minimum resolvable improvement, dependence model, interval procedure, exact-
pair applicability test, coverage and power requirements, scientific stopping/
extension rule, heuristic-futility error bound, stability-audit rate, and
supported backend profiles.

## Must not

Treat exact bits or exact manufactured fields as universal reproducibility or
qualification, use arbitrary epsilons, assume independence from component
labels, let a quality screen deny registered base evidence, convert
`EVIDENCE_DEFERRED` into negative scientific evidence, rank inside an unresolved
interval, or create a frontier event.
