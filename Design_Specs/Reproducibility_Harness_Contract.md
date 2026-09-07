# R0/R1/R2 Reproducibility Harness Contract

**Ticket:** B-E1
**Version:** 0.1 bounded engineering contract
**Status:** fixture-only implementation contract; not scientifically qualified,
security qualified, production qualified, or LIVE
**Runtime namespace:** `carbon.reproducibility`
**Upstream owners:** B-02A, B-02B, B-02C, B-04, and B-05
**Downstream consumers:** B-E4 and B-GATE fixture evidence only

## 1. Purpose and authority

This contract defines a deterministic fixture harness that keeps exact
identity (R0), numerical reproducibility (R1), and decision reproducibility
(R2) nominally separate. It does not supply a tolerance, statistical model,
sample size, dependence assumption, interval method, coverage or power target,
scientific stopping rule, supported production backend, ranking, frontier
promotion, or settlement policy.

The harness consumes exact upstream identities and policies. It does not copy
or replace their semantics:

- B-02A owns Challenge, population, SamplingPlan, case, and stratum meaning;
- B-02B owns resolved construction-plan identity;
- B-02C owns build, replicate, reuse, resource-stop, and receipt facts;
- B-04 owns reference provenance, applicability, disagreement, and failure;
- B-05 owns uncertainty and reconstruction-evidence policy authorship.

## 2. R0 exact identity

An `ExactIdentityManifest` binds the exact B-02A physical-system,
candidate-output, target-population, and SamplingPlan refs; candidate artifact;
B-02B resolved construction plan; uncertainty, reconstruction-evidence, and
reference policies; generator; scoring; backend profile; environment;
execution limits; seed-role structure; receipt construction; and hardware
role. Exact equality yields only `R0Outcome.EXACT_MATCH`. Any differing field
is reported by name and yields `IDENTITY_MISMATCH`.

R0 never constructs an R1 or R2 result. Bit identity, an exact manufactured
anchor, or an exact control-plane replay cannot infer numerical or decision
reproducibility.

## 3. R1 numerical comparison

R1 compares two exact-identity run captures only through an injected
`NumericalComparisonProcedure`. The procedure binds an exact procedure,
tolerance-policy, Dossier-qualification, and backend-profile identity. The
harness supplies no default procedure or epsilon.

Missing procedure authority, unsupported backend identity, identity mismatch,
non-finite material, malformed output, or procedure failure remains typed and
fail closed. A procedure returns per-output deltas and one explicit
`REPRODUCIBLE`, `NOT_REPRODUCIBLE`, or `INDETERMINATE` result. Synthetic
numeric policies are permitted only in test-owned fixtures.

## 4. Crossed evidence identity

`CrossedEvidenceDesign` declares:

- exact incumbent and challenger evidence-set refs;
- separately realized, producer-independent reconstruction refs for both arms;
- the complete B-02A `CanonicalChallengeCaseRef` inventory and registered
  whole-case/trajectory scope and stress stratum for every case;
- required common-case, common-random-number, reference-realization,
  training-seed, hardware, representation, execution, data, backbone, and
  implementation dependency declarations where applicable; and
- exact B-05 uncertainty and reconstruction-evidence policy refs.

`CrossedEvidenceGraph` contains exactly one cell for every
arm × reconstruction × whole-case/trajectory design coordinate. B-E1 owns
observed, missing, censored, reconstruction-failed, measurement-unresolved,
and infrastructure-failed cell states. Each cell separately carries the exact
B-04 `ReferenceRunOutcome` and optional `ReferenceComparisonOutcome`; B-E1
does not duplicate or reinterpret B-04's reference uncertainty, disagreement,
not-applicable, or failure vocabulary. Missing and censored cells remain
present; they are never dropped from the realized population.

Each cell preserves its reconstruction, case, stratum, reference realization,
registered randomness role, training-seed role, hardware role, representation,
execution, provenance, and separate evidence-factor observations. Detectable
shared identities across arms must have an exact dependency declaration.
Different labels never imply independence.

The six mandatory evidence-factor kinds are reference variability,
primary/witness disagreement, measurement/reference floors,
generator/reference discrepancy, reconstruction variability, and finite-case
or trajectory sampling variation. Model-form and population-adequacy
limitations remain explicit unresolved claims rather than being absorbed by an
exact anchor.

## 5. R2 decision procedure

R2 first applies typed failure and evidence-sufficiency precedence. Reference,
measurement, reconstruction, and infrastructure outcomes cannot become
negative candidate evidence. An unresolved claim, insufficient evidence,
unqualified missing/censoring policy, or unavailable decision procedure yields
an unresolved result.

Evidence combination occurs only through an injected procedure. Selection is:

1. an applicable qualified joint-propagation procedure;
2. otherwise an applicable qualified conservative-bound procedure;
3. otherwise an applicable exact B-05 dependence shortcut; or
4. `UNRESOLVED_INDETERMINATE`.

A quadrature, independence, or zero-covariance shortcut must match one exact
B-05 `DependenceShortcutBinding`, including incumbent/challenger evidence-set
refs, case and stratum scopes, assumption, applicability test, and Dossier
qualification. The injected applicability assessment must repeat those exact
identities and bind an exact test-result ref. Broader, narrower, missing,
stale, or mismatched scope cannot call the shortcut.

The injected decision returns both decision stability and the typed scientific
outcome. Stable `RESOLVED_SUPERIOR` or `RESOLVED_NOT_SUPERIOR` may be
represented in the fixture result; an unstable or crossing/contested result is
unresolved. The result contains no rank, winner selection, frontier event,
entitlement, weight, or settlement field.

## 6. Reconstruction evidence audit

The harness reuses `assess_reconstruction_evidence` and records distinct
events for static admission, complete base evidence, frozen-build reuse,
repeat-promotion evidence, random stability audit, scientific sequential
decision, and heuristic futility.

- Static rejection may reject protocol/resource admission only; it creates no
  candidate-physics judgment.
- Before complete registered base evidence, any requested stop is
  `EVIDENCE_DEFERRED`.
- A heuristic-futility event is always `EVIDENCE_DEFERRED`, even after base
  evidence; it cannot call a scientific decision procedure.
- A scientific sequential decision requires an injected procedure with exact
  coverage qualification and stopping-rule identity. Missing authority is
  unresolved. `CONTINUE` requests extension; exhaustion is indeterminate.
- Frozen reuse and stability-audit events retain their separate roles. Neither
  substitutes for the producer-independent repeat evidence required by policy.

## 7. Canonical fixture and hostility boundary

All public values are immutable, exact-type checked, Challenge-bound, and
bounded. Evidence design and graph collections have deterministic canonical
ordering while retaining every coordinate and dependency edge. Canonical
bytes use profile `carbon_reproducibility_canonical_v1`; refs use domain-
separated SHA-256 digests.

The package accepts no callable paths, imports, serialized executables, raw
protected payloads, seeds, draw IDs, filesystem paths, URLs, credentials,
generic mappings, or caller-selected production/LIVE mode. Procedure objects
are constructor-injected trusted test seams and their exceptions are translated
to typed infrastructure failure without exposing exception text.

## 8. Maturity and non-goals

The bounded implementation may earn only:

```text
SPECIFIED: YES
IMPLEMENTED: YES for the fixture harness
TESTED: YES for deterministic engineering fixtures
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```

B-E2, real reference execution, real reconstruction, production backend
qualification, real statistical calibration, ranking, frontier promotion,
network transport, settlement, weights, emissions, and later tickets are not
implemented here.
