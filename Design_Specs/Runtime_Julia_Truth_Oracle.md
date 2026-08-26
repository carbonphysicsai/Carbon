# Runtime Julia Reference Capability

> **Historical filename:** retained to avoid breaking repository links. Julia
> is not a universal truth oracle, and this file does not grant any solver
> scientific authority.

**Version:** 2.0
**Status:** reconciled target architecture; not implemented or qualified
**Audience:** SciML, protocol, operations, security, and implementation teams
**Controlling science:** `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`,
`Evidence_and_Envelope_Standards.md`, and the future ratified
`Reference_and_TruthAsset_Contract.md` owned by Wave B ticket B-04
**Operations:** `Operations.md`
**Sequencing:** `.agent/WAVE_B.md`

---

## 1. Decision

A Julia/SciML runtime may implement one registered role in a
Challenge-specific reference hierarchy. It is a computational instrument, not
truth by language, library, solver name, cost, or numerical tolerance.

For each Challenge, the future ratified `ReferencePolicy` must state whether a
Julia implementation is:

- the routine primary reference;
- a corroborating or methodologically independent witness;
- a qualification or audit anchor; or
- not applicable.

That limited authority is earned by the Challenge's Validation Dossier. A
successful process, a small solver tolerance, or agreement with another
correlated implementation is not enough.

```text
CanonicalChallengeCase
        +
qualified ReferencePolicy
        +
pinned implementation and environment
        ↓
typed ReferenceRunOutcome
        ↓
TruthAsset with provenance and uncertainty
        ↓
registered MeasurementContract and Score Pack
```

The service computes a reference realization on the generator's exact
Challenge-specific conditions. It does not define the physical population,
select the official case, set a gate, or decide a winner.

---

## 2. Authority and maturity

| Claim | Current state |
|---|---|
| Target Julia reference interface described | Yes |
| Exact B-04 contract ratified | No |
| Runtime implementation present and integrated | No evidence from this file |
| Reference method scientifically qualified | No |
| Production security or operations qualified | No |
| Universal ground-truth oracle exists | No, by design |

The exact public/internal types, canonical encoding, endpoint shape, bounds,
and error precedence remain owned by B-04 and any later transport ticket. Code
must not be implemented from illustrative historical endpoint shapes.

---

## 3. Required request and result semantics

The reference runner consumes only a canonical, already-authorized request
bound to exact identities such as:

```text
challenge_ref
canonical_case_ref
reference_policy_ref
reference_role
implementation_ref
environment_ref
method_config_ref
request_id / idempotency identity
resource_policy_ref
```

The caller cannot submit an arbitrary PDE string, executable expression,
solver choice, tolerance, code fragment, file path, URI, package request, or
generic `truth_mode`. Those choices belong to the registered policy and pinned
implementation.

A successful outcome must bind at least:

```text
exact request identity
case and policy identities
reference role
implementation and environment identities
method and configuration identities
solution artifact reference
units, coordinates, and time semantics
applicability and conditioning status
uncertainty representation
convergence / diagnostic evidence references
resource receipt
```

The output becomes a `TruthAsset` only through the B-04 contract. The
`TruthAsset` name means a qualified answer-key artifact with bounded authority,
not metaphysical or exact physical truth.

---

## 4. Primary, witness, and anchor separation

Primary and witness implementations must have nominally separate runner roles,
provenance, and outputs. The witness does not silently replace the primary or
vote truth into existence.

The Validation Dossier must assess relevant correlation risks, including:

- shared equations or model-form assumptions;
- shared discretization and time-integration families;
- shared meshes, transforms, libraries, or generated code;
- common calibration data;
- common personnel or copied implementation paths;
- shared floating-point and hardware failure modes.

When independence is insufficient, the Dossier records the limitation and the
decision interval widens or remains unresolved. Disagreement beyond the
registered policy produces a typed contested outcome, not an averaged answer
or candidate failure.

---

## 5. Failure contract

Reference and infrastructure failures are never candidate physics failures.
Required outcomes include distinct classes for:

- unsupported or out-of-applicability case;
- conditioning or numerical-sensitivity failure;
- non-convergence or diagnostic failure;
- primary/witness disagreement;
- stale or mismatched policy, implementation, or environment;
- malformed artifact or provenance failure;
- timeout, capacity, dependency, transport, or process failure;
- cancellation.

If the registered primary reference is unavailable and no already-qualified
fallback is named by the same immutable `ReferencePolicy`, official evaluation
waits or returns the registered indeterminate/infrastructure outcome. It does
not fall back to a mock, analytic fixture, weaker solver, cached unbound output,
or candidate-generated result.

Mocks and analytic fixtures are permitted only in structurally test-only
contexts. Their provenance must make LIVE activation and economic settlement
impossible.

---

## 6. Reproducibility and supply chain

Every runnable Julia environment must be content-addressed and immutable for
the registered policy:

- exact Julia runtime and platform identity;
- committed `Project.toml` and `Manifest.toml` hashes;
- immutable package artifact/depot image;
- exact service image and source revision;
- solver, algorithm, tolerance, mesh, precision, threading, accelerator, and
  deterministic-mode configuration where relevant;
- hardware/resource class and numeric capability;
- canonical request/result encoding;
- checksums for produced artifacts.

Production startup must instantiate the pinned manifest without resolving or
updating packages. `Pkg.add`, `Pkg.update`, mutable tags, and implicit depot
state are forbidden in a registered runtime. Promotion of any dependency or
environment creates a new implementation/environment identity and requires the
registered verification and review path.

Residual nondeterminism is measured. It contributes to the uncertainty and
decision interval and may make the reference inadmissible.

---

## 7. Security and data boundary

The runtime receives the minimum authorized canonical case material and returns
only the registered result/provenance fields. It must not:

- execute expressions supplied by miners or general callers;
- expose official seeds, case identities, mixture realizations, or per-case
  protected data on public or miner-visible surfaces;
- perform request-time package installation or network retrieval;
- accept caller-selected filesystem paths or deserialization payloads;
- log raw protected inputs or outputs outside the approved evidence store;
- reveal validator topology, protected reservoir depth, or scheduling signals;
- combine reference execution with scoring, ranking, payment, or settlement.

Authentication, transport, isolation, quotas, secret handling, and production
key custody are later security/operations contracts. Wave B may implement only
local fixture runner interfaces and fail-closed production seams.

---

## 8. Operational policy

Operations may schedule, prefetch, cache, or replicate only within the exact
registered scientific identity. Capacity policy cannot change cases,
measurements, reference fidelity, stress coverage, or exam depth by candidate.

Cache keys must include every identity that affects scientific meaning. A cache
hit must return byte-identical, provenance-bound material. Unknown identity,
partial artifact, or stale environment fails closed.

Cost, hardware count, audit frequency, latency budget, and strong-anchor
sampling remain owner-approved planning inputs. Historical dollar figures and
single-GPU deployment sketches are not current decisions.

---

## 9. Qualification evidence required before authority

The Challenge's Dossier must include, as applicable:

1. analytic or manufactured-solution checks;
2. refinement and convergence evidence;
3. conservation, invariance, and limiting-case tests;
4. methodologically independent cross-code evidence;
5. conditioning and failure-region mapping;
6. residual numerical and reconstruction variance;
7. applicability and exclusion boundaries;
8. uncertainty propagation into Carbon's decision interval;
9. evidence that remaining reference error cannot plausibly reverse the
   smallest superiority decision Carbon permits;
10. reproducibility from the pinned environment and artifacts;
11. security, disclosure, and failure-injection evidence;
12. named independent and accountable review.

Passing this campaign grants only the exact role, envelope, implementation,
environment, and Challenge version recorded in the signed Dossier. Authority
does not transfer automatically to another PDE, regime, solver configuration,
hardware path, or Challenge.

---

## 10. Wave B implementation boundary

B-04 may define typed primary/witness runner interfaces, fixture outcomes,
provenance, uncertainty, and failure semantics. B-06 may define the evidence
slots and fail-closed qualification manifest. B-E2 may exercise Julia/reference
failure behavior. B-07F may use fixture reference packs behind the unchanged v1
fixture lifecycle.

Wave B does not deploy a public Julia service, run a real protected exam,
qualify a solver, activate a LIVE Challenge, or authorize an economic result.

> **Closing rule:** Julia can be a powerful implementation of a qualified
> reference role. Carbon trusts its output only to the degree demonstrated by
> independent, Challenge-bound evidence and carried into the decision interval.
