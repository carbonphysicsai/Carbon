# Julia Reference Backend v1 — Challenge-Qualified SciML Service

**Status:** OWNER-RECOMMENDED replacement framing for future migration of `Runtime_Julia_Truth_Oracle.md`.  
**Purpose:** Define how Julia/SciML may supply reference solves, adjoints, symbolic transformations, or corroborating evidence without becoming a universal scientific truth authority.

## 1. Core rule

> **Julia/SciML is a reference backend. The Challenge ReferencePolicy determines whether, where, and how its outputs have scientific authority.**

No backend certifies its own applicability.

## 2. Allowed roles

Depending on the Challenge, the service may provide:

- high-accuracy numerical reference solutions;
- mesh/time convergence studies;
- independent corroborating solutions;
- adjoint/sensitivity calculations;
- symbolic transformations or generated numerical operators;
- manufactured-solution checks;
- validation evidence for another production generator/reference implementation.

It may be primary truth for one Challenge and only a secondary witness for another.

## 3. Forbidden universal assumptions

Do not assume:

- `DifferentialEquations.jl` output is automatically ground truth;
- tight solver tolerances imply model-form/discretization adequacy;
- an independent code is correct because it is independent;
- one generic `l2 < 1e-3` rule determines pass/fail across Challenges;
- service success implies measurement applicability;
- service failure means candidate scientific failure.

## 4. ReferencePolicy binding

Every authoritative use should bind something conceptually equivalent to:

```text
ReferencePolicy {
  challenge_id / version
  reference_role
  backend_id / version / digest
  equation/model identity
  numerical method
  spatial/temporal discretization
  tolerances
  applicability / regime
  convergence / verification evidence
  uncertainty floor
  disagreement policy
  failure policy
  disclosure class
}
```

The Validation Dossier qualifies the policy and implementation.

## 5. Service interface

A backend may expose generic compute endpoints, but responses should be evidence objects rather than universal scientific verdicts.

Preferred:

```text
POST /solve_reference
POST /adjoint
POST /symbolic_transform
POST /manufactured_check
GET  /health
```

Response carries:

```text
backend identity
method / discretization
solution / result
status
numerical diagnostics
uncertainty / convergence metadata where available
provenance / hashes
```

Avoid a generic backend-owned `passes_threshold=true` unless the threshold is explicitly supplied by an authorized MeasurementContract/ReferencePolicy and the call records that identity.

## 6. Failure states

At minimum distinguish:

```text
REFERENCE_AVAILABLE
REFERENCE_UNCERTAIN
REFERENCE_DISAGREEMENT
REFERENCE_NUMERICAL_FAILURE
REFERENCE_FAILED_INFRA
REFERENCE_NOT_APPLICABLE
```

These states must be structurally unable to become a candidate physics zero unless an authorized Score Pack explicitly defines a scientifically valid treatment of the available evidence.

## 7. Burgers example

For the repaired periodic viscous Burgers Challenge, periodic Cole–Hopf is the preferred primary reference because the exact problem admits a stronger semi-analytic transformation. A Julia/SciML solve can remain a useful independent witness on selected cases.

This is an example of the general rule:

> **Choose the strongest qualified truth path for the Challenge; do not choose a technology first and call it truth.**

## 8. Multiphysics / future Challenges

For systems without analytic truth, Julia may be valuable as:

- one code in a code-to-code comparison;
- a high-order reference path;
- a coupling/adjoint service;
- a symbolic model authoring bridge.

Where industrial truth requires OpenFOAM, SU2, FEniCS, experimental instrumentation, a partner solver, a dataset, or another implementation, the ReferencePolicy should say so.

## 9. Operations

Service downtime should yield reference/infra degradation and retry/quarantine semantics. It must not fabricate scientific failure.

The service's deployment digest, package manifest, hardware/precision profile, and reference-policy compatibility should be monitored and versioned.

## 10. Final statement

> **Carbon does not have one universal truth oracle. It has Challenge-qualified reference policies that may use Julia/SciML where the evidence supports it.**
