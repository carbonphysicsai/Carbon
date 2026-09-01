# ReferencePolicy and TruthAsset Contract

**Version:** 0.1 candidate<br>
**Status:** bounded B-04 engineering-contract candidate; not ratified until the
exact reviewed tree normally merges and exact-main CI succeeds<br>
**Ticket:** B-04<br>
**Runtime authority:** none; this document defines a later implementation
boundary and does not qualify or run a reference method<br>
**Primary owners:** SciML, statistics, protocol, and independent reference
review<br>
**Repository package boundary:** the existing reserved `carbon.evaluation`
namespace; no production module is added by this contract PR

## 1. Purpose and authority ceiling

Carbon needs a Challenge-bound answer-key process without treating a solver,
dataset, experiment, language, or service as truth by reputation. This
contract defines the exact engineering boundary for a future
`ReferencePolicy`, reference runs, comparisons, answer-key admission, and
`TruthAsset` identity.

The governing chain is:

```text
Challenge-owned physical job and canonical case
        +
prospectively versioned ReferencePolicy
        +
policy-issued nominal runner role
        ↓
typed ReferenceRunOutcome
        ↓
optional policy-required comparison
        ↓
separately authorized positive admission
        ↓
TruthAsset: authority-bounded answer-key artifact
```

The name `TruthAsset` means an answer-key artifact admitted for one exact,
qualified, bounded use. It does not mean metaphysical, error-free, universal,
or production truth.

This candidate establishes no primary method, witness, physical envelope,
uncertainty floor, disagreement threshold, fallback, qualification decision,
`LIVE` Challenge, score, product claim, or economic outcome. All such values
remain `HUMAN_INPUT_REQUIRED`, `EVIDENCE_REQUIRED`,
`NEW_OWNER_DECISION_REQUIRED`, or typed unavailable.

## 2. Controlling authority and conflict handling

This contract is read with:

- [Scientific Challenge Authoring Contract](./Scientific_Challenge_Authoring_Contract.md);
- [Generator Runtime Contract](./Generator_Runtime_Contract.md);
- [Evidence and Envelope Standards](./Evidence_and_Envelope_Standards.md);
- [Trust-Minimized Verification](./Trustless_Verification.md);
- [Runtime Julia Reference Capability](./Runtime_Julia_Truth_Oracle.md); and
- [Scientific Reference Canon v4](../docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md).

Current code controls implemented behavior. This document controls the B-04
target boundary only after normal merge. Owner recommendations and open design
questions remain non-ratified until their owners act.

The B-04 audit classifies the current seams as follows:

| Classification | B-04 finding |
|---|---|
| `NO_CONFLICT` | The canon, evidence standards, trust-minimized verification, Julia target, B-02A authoring boundary, B-03 generator boundary, and downstream tickets agree on Challenge-bound authority, role separation, uncertainty, applicability, provenance, and reference-failure separation. |
| `DOCUMENTATION_LAG` | `Trustless_Verification.md` §2 and `Science_GTM_Engineering_Ticket_Delta.md` §2.1 say `TruthAsset` carries failure state; `Evidence_and_Envelope_Standards.md` §1 combines “analytic or manufactured” and §6 uses “reference rank”; the same ticket delta's B-E2 row broadly assigns fixture runners while the controlling B-04 ticket explicitly requires them. This contract uses positive-only assets, orthogonal evidence/authority/source axes, and assigns minimal standard-library fixtures to B-04 while B-E2 retains Julia/service and expanded failure work. |
| `IMPLEMENTATION_LAG` | `carbon/evaluation/__init__.py` is only a reserved package marker and has no B-04 policy, ref, codec, resolver, grant, runner, outcome, comparison, admission, or disclosure implementation. B-E2, B-05, B-06, B-07F, and future A3 integration remain later work. |
| `MIGRATION_REQUIRED` | `docs/history/LEGACY_CODE_INDEX.md` lists the quarantined `poc/eval/oracle_check.py` and Old Julia tree, while illustrative `Design_Specs/Implementation.md` §§19–23 describes direct Julia/SciML clients/services. None is current authority; any deliberate later reuse requires prospective wrapping behind B-04 and qualification. No archived executable was inspected in this session. |
| `NEW_OWNER_DECISION_REQUIRED` | Every real hierarchy, method, support boundary, configuration, uncertainty rule, conditioning rule, independence finding, disagreement policy, fallback, rights/access mode, resource policy, qualification, and activation decision remains reserved. |

No source is averaged with a conflicting source. A material conflict stops the
affected behavior and remains explicit.

## 3. Package ownership and dependency direction

The repository already reserves `carbon.evaluation` as the canonical package
for reference, measurement, uncertainty, Dossier, and later evaluation
orchestration concerns. B-04 therefore uses `KEEP + WRAP` for that namespace.
This contract does not add code or freeze a future module split.

A future B-04 implementation may consume only the exact narrow seams it needs
from:

```text
carbon.authoring.canonical   # low-level canonical value/ref codecs, not its closed top-level registry
carbon.authoring.cases       # protected CanonicalChallengeCase boundary
carbon.authoring.evidence    # EvidenceRoleBinding and CaseEvidenceBinding
carbon.authoring.errors      # fixed authoring boundary failures
carbon.authoring.model       # exact applicability/loaded-graph validation seams
carbon.authoring.primitives  # strict primitives and reconstructors
carbon.authoring.refs        # B-02A-owned physical/population/plan/case refs
carbon.registry.model        # ChallengeKey only
Python standard library
```

The implementation import allow-list must name exact symbols and reject
`carbon.registry` root, lifecycle, store, qualification gate, and artifact-I/O
surfaces. It must not depend on convenience root exports for protected B-02A
types deliberately kept in explicit submodules.

The initial B-04 owner must not import or call:

```text
carbon.generators
carbon.scoring
carbon.traineval
carbon.cards
carbon.fees
carbon.mcp
carbon.leaderboard
carbon.observability
carbon.qualification
retired namespaces
optional numerical/scientific libraries
filesystem, process, network, environment, or ambient-randomness APIs
```

Composition passes an exact B-02A `CanonicalChallengeCase`; it does not make
`carbon.evaluation` depend on B-03. No existing owner package reverse-imports
B-04. B-05 may later add separately owned measurement modules under the same
top-level namespace without allowing reference code to create scores.

The later implementation must define a curated `carbon.evaluation.__all__`
containing audience-safe policy/role/outcome and public projection contracts
only. B-04-D11 freezes its exact names and order before runtime code is added;
until then this contract makes no exact root-export claim. Protected case refs,
requests, resolution records, grants, runs, comparisons, artifacts, assets,
admission capabilities, and provider identities remain submodule-only and
deny-by-default.

## 4. Three-axis role and separate composition model

Evidence kind, reference authority function, and source/delivery class are
three orthogonal axes. Policy composition is a separate prospective structure,
not a fourth role label.

### 4.1 Evidence source kind

B-04 reuses B-02A's exact payload-bearing `EvidenceRoleBinding` taxonomy:

```text
ANALYTIC(EMPTY)
SEMI_ANALYTIC(EMPTY)
MANUFACTURED_SOLUTION_VERIFICATION(EMPTY)
NUMERICAL(EMPTY)
EXPERIMENTAL(EMPTY)
INDUSTRIAL(EMPTY)
REGISTERED_HYBRID(hybrid_role_ref)
```

`EvidenceRoleBinding` describes what kind of evidence a source supplies. It
does not say whether the source is primary, independent, qualified,
applicable, or admissible as an answer key. `REGISTERED_HYBRID` must preserve
and validate its exact prospectively reviewed B-02A `hybrid_role_ref`; no other
evidence role may carry that payload.

B-02A `REGISTERED_HYBRID(hybrid_role_ref)` and B-04
`REGISTERED_HYBRID_POLICY` are independent. The former is the evidence-kind
binding of one B-04 entry and does not create or authorize a policy
composition. The latter composes at least two distinct ordered B-04 entries
and does not synthesize a B-02A hybrid role or owner ref. A single-member
composition rejects and must use `SINGLE_ENTRY`; a single B-04 entry may carry
a B-02A registered-hybrid binding only when its exact owner ref is compatible
with the entry and policy scope. B-04-D11 freezes the exact payload and
cross-binding validation rules; neither construct may substitute for the
other.

### 4.2 Reference authority function

The future B-04 implementation must define one closed nominal
`ReferenceAuthorityFunction` axis:

```text
PRIMARY
CORROBORATING_WITNESS
VERIFICATION_ANCHOR
VALIDATION_ANCHOR
REGISTERED_COMPONENT
```

This axis describes how evidence functions in the policy. `PRIMARY` is the
ordinary answer-key source for an exact registered scope, not a universal
oracle. `CORROBORATING_WITNESS` tests the primary within a registered campaign
and cannot silently replace it. `VERIFICATION_ANCHOR` supports code,
discretization, convergence, or implementation verification.
`VALIDATION_ANCHOR` supplies separately registered physical/context evidence;
it is not automatically an answer-key runner. `REGISTERED_COMPONENT` is a
non-answer-key member of an exact qualified composition; membership transfers
no primary authority to the component.

### 4.3 Source and delivery class

A separate closed `ReferenceSourceClass` axis describes how the registered
source is delivered or composed:

```text
DIRECT_REGISTERED_SOURCE
EXPERIMENTAL_DATASET_OR_INSTRUMENT
INDUSTRIAL_OR_CUSTOMER_HOSTED_REFERENCE
QUALIFIED_SURROGATE_OR_ACCELERATOR
```

Each prospective policy entry binds exactly one B-02A evidence-role binding,
one authority function, and one source class. A separate closed target-level
`ReferenceCompositionKind` is `SINGLE_ENTRY` or
`REGISTERED_HYBRID_POLICY`. A registered hybrid is an ordered composition of
at least two distinct exact entry refs and has authority function `PRIMARY` or
`CORROBORATING_WITNESS`. Every computational member uses authority function
`REGISTERED_COMPONENT` and retains its own evidence-role binding, source
class, applicability, uncertainty, provenance, and qualification. Anchors and
corroborating witnesses remain separately registered evidence/execution
targets, not computational members of the primary they assess. A composition
and any witness target compared with it must have disjoint entry-ref sets;
shared underlying methods, data, or lineage remain explicit correlation
facts. This permits, for example, an industrial primary, a surrogate witness,
or an experimental validation anchor without conflating source class with
authority.

The required named semantic profiles are therefore exact combinations:

- primary reference: authority `PRIMARY`, with any separately eligible source
  kind and class;
- corroborating/witness reference: authority `CORROBORATING_WITNESS`;
- verification anchor: authority `VERIFICATION_ANCHOR`, including a
  `MANUFACTURED_SOLUTION_VERIFICATION` evidence kind where applicable;
- experimental validation anchor: authority `VALIDATION_ANCHOR`, evidence
  kind `EXPERIMENTAL`, source class normally
  `EXPERIMENTAL_DATASET_OR_INSTRUMENT`;
- industrial or customer-hosted reference: source class
  `INDUSTRIAL_OR_CUSTOMER_HOSTED_REFERENCE`, with its separately registered
  authority function;
- qualified surrogate or accelerator: source class
  `QUALIFIED_SURROGATE_OR_ACCELERATOR`, with its separately registered
  authority function; and
- registered hybrid policy: composition kind `REGISTERED_HYBRID_POLICY`, with
  a closed `PRIMARY` or `CORROBORATING_WITNESS` composition function and exact
  ordered `REGISTERED_COMPONENT` entries that retain their individual
  evidence-role bindings and source classes.

Only a single entry whose authority function is `PRIMARY`, an exact qualified
primary composition, a single entry whose function is
`CORROBORATING_WITNESS`, or an exact qualified witness composition may use the
nominal answer-key runner interfaces in section 8. Anchor and
`REGISTERED_COMPONENT` entries are evidence/component-only unless a distinct
prospective entry assigns the same underlying source a primary or witness
function and qualifies that use. Such a distinct entry never erases required
correlation disclosure and cannot overlap a compared composition's member
refs. A future computational or ingestion adapter for an anchor/component must
have its own nominal non-answer-key boundary; it cannot call a primary or
witness runner by alias.

Rules:

- a role/source label grants no authority by itself;
- agreement cannot qualify or promote a source;
- `MANUFACTURED_SOLUTION_VERIFICATION` cannot by itself establish target-
  population relevance, physical model validation, customer context of use,
  engineering qualification, or product fitness;
- experimental, industrial, and customer-hosted sources require exact
  measurement, provenance, rights, access, uncertainty, representativeness,
  and context bindings;
- a surrogate/accelerator inherits a bounded envelope and anchor obligations;
  speed or agreement cannot widen it;
- a registered hybrid is not majority voting, implicit averaging, or a
  caller-selected mixture; and
- a generator under test has no reference authority function or source class
  that can certify its own output as truth.

## 5. ReferencePolicy identity and prospective history

### 5.1 Common identity

Every `ReferencePolicy` binds at least:

```text
object_kind = reference_policy
schema_version
canonicalization_profile
ChallengeKey
policy_id
policy_version
supersedes: explicit BOUND or NOT_APPLICABLE
physical_system_ref
candidate_output_contract_ref
truth_target_ref
claim_scope_ref
target_population_binding
proposal_population_binding
evidence_population_bindings
SamplingPlan binding
reference_fidelity_allocation_ref
ordered prospective policy-entry refs
ordered prospective ReferenceCompositionRefs, or exact empty tuple
answer_key_authority_target: exact SINGLE_PRIMARY_ENTRY,
    QUALIFIED_PRIMARY_COMPOSITION, or typed unavailable reason
registered_witness_targets: exact ordered tuple of SINGLE_WITNESS_ENTRY or
    QUALIFIED_WITNESS_COMPOSITION targets, or exact empty tuple
comparison_policy_binding
fallback_policy_binding
uncertainty_policy_binding
applicability_policy_binding
qualification_policy_binding
provenance_policy_binding
disclosure_policy_binding
rights/access policy binding
resource policy binding
history and revocation bindings
```

The physical, output, population, and SamplingPlan identities remain owned by
B-02A. B-04 stores exact refs and validates cross-Challenge and cross-scope
consistency; it does not create parallel identities. A prospective policy does
not bind a not-yet-selected exact case, request, run, resource receipt, or
realized artifact digest. Those identities are added monotonically by the
request/grant and run-record layers described in section 7.

A usable policy must resolve exactly one closed `ReferenceAuthorityTarget` for
the requested scope:

```text
SINGLE_PRIMARY_ENTRY(ReferencePolicyEntryRef)
QUALIFIED_PRIMARY_COMPOSITION(ReferenceCompositionRef)
```

It may also register zero or more closed `ReferenceWitnessTarget` values:

```text
SINGLE_WITNESS_ENTRY(ReferencePolicyEntryRef)
QUALIFIED_WITNESS_COMPOSITION(ReferenceCompositionRef)
```

The single-entry target must name a `PRIMARY` entry. A composition is a
separate prospective object with authority function `PRIMARY` or
`CORROBORATING_WITNESS`; it binds at least two distinct ordered
`REGISTERED_COMPONENT` entry refs, exact combination method/implementation
constraints, applicability, uncertainty, correlation, provenance, and
qualification. Primary targets accept only a `PRIMARY` composition; witness
targets accept only a `CORROBORATING_WITNESS` entry or composition. Member
entries do not become primary or witness by participation. A primary target
and a witness target used in one comparison have disjoint member/entry-ref
sets. The composition is not an average, vote, or implicit fallback.

All targets are closed within the same exact policy version. The policy's
ordered entry, composition, and registered-witness-target tuples are each
duplicate-free by canonical semantic identity, including duplicate target
wrappers over the same entry/composition. A single-entry target ref must occur
exactly once in that policy's ordered entry tuple. A composition target ref
must occur exactly once in that policy's ordered composition tuple, and each
of its distinct member refs must occur exactly once in both the composition
member tuple and the same policy's entry tuple. Every entry, composition, and
target cross-binds the identical `ChallengeKey`, policy id/version,
physical/output/claim/population/SamplingPlan scope, and canonical profile. A
targeted single primary/witness entry has the matching authority function;
every composition member has exactly `REGISTERED_COMPONENT`. Expanding each
target to its single entry or complete component-entry set must itself be
duplicate-free and must yield disjoint primary and compared-witness sets. An
external, duplicate, cross-policy, cross-version, cross-scope, or role-
mismatched entry/composition ref rejects rather than being imported into the
policy.

An unresolved policy may exist as a draft authored object, but every run and
admission path returns typed unavailable until the authority target and all
mandatory bindings are resolved. No default primary or composition exists.

### 5.2 Material change and historical interpretation

The following changes require a new prospective policy version and cannot
silently reinterpret history:

- Challenge, physical system, truth target, output, population, SamplingPlan,
  or reference-fidelity allocation;
- role assignment, source, method, implementation, environment, precision,
  hardware, or configuration;
- support, applicability, conditioning, uncertainty, comparison,
  disagreement, fallback, or qualification policy;
- artifact representation, canonical encoding, cache meaning, provenance,
  disclosure, rights, access, or resource policy; or
- any change that could alter an admitted answer, its uncertainty, or its
  permitted use.

Historical requests, runs, comparisons, artifacts, and `TruthAsset`s retain
their original policy identity. Revocation blocks new use according to a
separately registered rule; it does not rewrite the old bytes or claim.

## 6. Exact refs and canonicalization

This contract fixes these B-04 v1 framing literals:

```text
schema_version = "1.0"
canonicalization_profile = "carbon_reference_truth_canonical_v1"
document_header = b"carbon.reference-truth.canonical.v1\x00"
```

The v1 B-04 primitive codec wraps, without weakening, the exact B-02A
canonical primitive semantics: distinct null/Boolean/Int64/UInt64/Float64/
TEXT/BYTES/tuple/record/union/ref tags; exact built-in nominal types and
subclass rejection; finite big-endian Float64 with positive-zero bits only;
strict pre-normalized NFC UTF-8 with control/surrogate rejection; distinct
signed and unsigned 64-bit ranges; strict canonical field order; closed enum,
union, object-kind and ref registries; set-like canonical-byte ordering and
duplicate rejection; no missing/extra/aliased fields; and rejection of unknown
tags, trailing bytes, and caller serialization.

The v1 engineering decoder ceilings inherit B-02A's exact hard maxima:

```text
canonical document bytes = 16_777_216
single TEXT or BYTES payload bytes = 65_535
tuple or record field items = 65_535
canonical nesting depth = 64
```

These are hostile-input decoder ceilings, not scientific fidelity, service
capacity, cache, latency, cost, or production resource policy. Owners may
later select tighter operational limits, but no implementation may exceed or
weaken these v1 hard maxima under the same profile.

The future implementation owns exactly these v1 top-level record/ref kinds:

```text
PrecomputedReferenceSourceManifestRef
ReferencePolicyRef
ReferencePolicyEntryRef
ReferenceCompositionRef
PrimaryReferenceRequestRef
WitnessReferenceRequestRef
PrimaryRunGrantRef
WitnessRunGrantRef
ReferenceResolutionRecordRef
ReferenceRunRecordRef
ReferenceComparisonRecordRef
ReferenceArtifactRef
FixtureReferenceAssetRef
TruthAssetAdmissionGrantIssuanceRecordRef
TruthAssetAdmissionGrantRef
TruthAssetAdmissionDecisionRecordRef
TruthAssetRef
```

The semantic fields and monotonic ownership layers are fixed by sections 5,
7–13. Before the first runtime model is added, a separately authorized,
reviewed, and notified prospective B-04-D11 canonical-schema decision must
freeze the complete field order/type registry, exact outcome/reason
compatibility matrices for every v1 record above, and exact curated root-export
tuple. Until that decision exists, this contract defines canonical
requirements and reserved ref names, not executable exact bytes, an exact root
surface, or an implemented identity claim.

It owns a versioned B-04 canonical profile and domain header while wrapping
B-02A's low-level canonical primitives and public ref codecs where their
semantics fit. B-04 registers its object kinds in its own closed owner
boundary; it must not widen B-02A's closed top-level object registry or reuse
the B-03 generator profile opportunistically.

Canonical behavior must be:

- strict and versioned, with one exact schema and profile per object version;
- field-complete and order-defined, with unknown, missing, duplicate, or
  out-of-order fields rejected;
- exact-type only, rejecting subclasses, booleans-as-integers, coercion,
  implicit defaults, non-finite numbers, and caller-defined serialization;
- content-addressed with a tagged SHA-256 digest over canonical bytes;
- verified with constant-time digest comparison at untrusted boundaries;
- reconstructive: every accepted record/ref pair is copied and its digest,
  type, Challenge, version, role, and meaning bindings are recomputed;
- immutable and mutation-isolated at untrusted boundaries; and
- safe under hostile input, without `repr`, `str`, exception-text, mapping,
  reflection, pickle, arbitrary object-graph, path, URI, or callable handling.

Text, bytes, tuple/collection length, nesting depth, and complete document size
must have exact required resource-policy bounds. This contract selects no
production numeric bound; until the owner supplies one, the applicable real
path is typed unavailable rather than unbounded.

A syntactically valid ref proves identity shape only. It is not authenticated
provenance, qualification, authorization, applicability, or scientific
authority.

## 7. Prospective entries and monotonic execution bindings

### 7.1 Prospective policy entry

Each `ReferencePolicyEntry` must be computable before a case run. It binds the
registered scope and constraints, never a future request, run, resource
receipt, or realized artifact:

| Binding | Prospective required meaning |
|---|---|
| Challenge scope | Exact `ChallengeKey`, physical system, candidate output, truth target, claim scope, and expected representation. |
| Population and plan | Exact target/evidence population roles, evidence campaign, SamplingPlan, stratum/support relation, and reference-fidelity allocation. |
| Role | Exact B-02A `EvidenceRoleBinding`, including `hybrid_role_ref` when and only when required, plus B-04 authority function and B-04 source class; no relabeling or payload loss. |
| Source and implementation constraints | Exact registered source, implementation revision/content or allowed immutable implementation manifest, method family, generated-code provenance, configuration constraints, and dependency constraints. |
| Environment constraints | Exact allowed runtime/environment identity, precision, deterministic-mode settings, platform, hardware/resource class, and numeric capability where material. |
| Expected artifact | Exact representation, units, coordinates, time semantics, shape/schema, and storage/access policy, but no not-yet-realized content digest. |
| Applicability | Exact support boundary, exclusions, assessment method, evidence refs, and limitations. |
| Conditioning | Exact conditioning/sensitivity assessment method, evidence refs, admissible status policy, and limitations. |
| Uncertainty | Exact required representation, estimand/meaning, units, method, evidence refs, coverage/applicability, and dependence disclosures. |
| Provenance and qualification | Exact evidence campaign, reviewer/authority refs, qualification requirement, rights/access policy, and disclosure restrictions. |

For a precomputed source, the entry may bind an immutable
`PrecomputedReferenceSourceManifestRef` describing the already existing source
corpus and its provenance. The later request still selects an exact case, and
the run record still binds the exact retrieved artifact digest.

A `ReferenceComposition` is also prospective. It binds composition kind
`REGISTERED_HYBRID_POLICY`, authority function `PRIMARY` or
`CORROBORATING_WITNESS`, at least two distinct ordered
`REGISTERED_COMPONENT` entry refs, exact combination
method/implementation/environment constraints, expected representation,
support/applicability, conditioning, uncertainty, independence/correlation,
provenance, rights, disclosure, and qualification policies. It contains no
future case, request, grant, run, resource receipt, or realized artifact.
Members gain no authority from composition. A primary composition and a
witness compared against it have disjoint member/entry refs; any shared
underlying method, data, implementation, or lineage remains a required
correlation fact.

### 7.2 Request, grant, and run layers

Identity is added monotonically without cycles:

Every primary request binds the policy's exact `ReferenceAuthorityTarget` as
both its answer-key and execution target. Every witness request binds that same
answer-key target for comparison scope plus one exact registered
`ReferenceWitnessTarget` as its execution target. The role-specific execution
target is therefore closed: a primary entry, primary composition, witness
entry, or witness composition; no untyped entry/composition union is accepted.

| Layer | Adds |
|---|---|
| policy entry | prospective scope, role/function/class, source/method/environment constraints, and required evidence policies |
| composition | optional prospective primary or witness composition over exact component entry refs with its own combination/applicability/uncertainty/provenance/qualification constraints |
| request | exact authoritative case ref, policy and answer-key target; for a witness, exact witness target; role-specific execution target, representation, request/idempotency, requested resource-policy and disclosure refs |
| grant | exact answer-key target, role-specific execution target and eligible entry/composition, implementation, environment, method/configuration, precision/hardware/resource authorization, request, and one-use capability identity |
| resolution record | exact request, resolver, terminal resolution outcome/reason, and the already constructed grant ref only for a grant-issued outcome; otherwise typed grant absence |
| run record | exact request/grant/resolution record, answer-key and execution targets, terminal outcome/reason, realized implementation/environment/member facts, artifact content descriptor/digest or typed absence, diagnostics, applicability, conditioning, uncertainty, provenance, and resource receipt; never a `ReferenceArtifactRef` |

The policy refers only to prospective entries/compositions; those objects never
refer to a request or run. On an issued path, the resolver constructs the grant
from its pre-existing issuer/capability identity and token, then constructs the
resolution record pointing backward to that completed grant ref. A non-issued
resolution record carries typed grant absence. The run refers backward to the
request, grant, resolution record, policy, answer-key target, and role-specific
execution target. A
`ReferenceArtifact` may then refer to the
completed run plus the same content descriptor/digest; the run never refers
forward to that artifact object. This directed graph is content-addressable
without a prospective/runtime identity cycle.

Authority never transfers automatically across another PDE, physical model,
regime, envelope, geometry, topology, boundary-condition class, forcing,
population, output representation, implementation, dependency, environment,
precision, hardware path, or Challenge version.

## 8. Resolution, grants, and nominal runner interfaces

### 8.1 Closed resolution and grant issuance

An exact primary or witness request is evaluated by trusted policy resolution
before any runner call. Resolution emits one immutable
`ReferenceResolutionRecord` with one closed result:

```text
PRIMARY_GRANT_ISSUED
WITNESS_GRANT_ISSUED
POLICY_INCOMPLETE
ROLE_UNAVAILABLE
NOT_APPLICABLE
UNSUPPORTED
APPLICABILITY_UNRESOLVED
QUALIFICATION_UNAVAILABLE
RESOURCE_AUTHORIZATION_UNAVAILABLE
IDENTITY_OR_PROVENANCE_FAILURE
```

The closed resolution-reason family is:

```text
RESOLUTION_REQUIREMENTS_SATISFIED
POLICY_PRIMARY_MISSING
POLICY_ENTRY_INCOMPLETE
ROLE_NOT_REGISTERED
CASE_NOT_APPLICABLE
CASE_UNSUPPORTED
APPLICABILITY_ASSESSMENT_UNAVAILABLE
QUALIFICATION_BINDING_UNAVAILABLE
RESOURCE_POLICY_UNAVAILABLE
RESOURCE_CAPACITY_UNAVAILABLE
RESOLUTION_IDENTITY_MISMATCH
RESOLUTION_PROVENANCE_INVALID
```

Only a grant-issued outcome may use
`RESOLUTION_REQUIREMENTS_SATISFIED`. The B-04-D11 compatibility matrix fixes
every other outcome/reason pairing; unknown or mismatched pairs reject.

When several resolution conditions are observed, the resolver emits the first
applicable outcome/reason under this exact total reason precedence:

1. `RESOLUTION_IDENTITY_MISMATCH`;
2. `RESOLUTION_PROVENANCE_INVALID`;
3. `POLICY_PRIMARY_MISSING`;
4. `POLICY_ENTRY_INCOMPLETE`;
5. `ROLE_NOT_REGISTERED`;
6. `CASE_NOT_APPLICABLE`;
7. `CASE_UNSUPPORTED`;
8. `APPLICABILITY_ASSESSMENT_UNAVAILABLE`;
9. `QUALIFICATION_BINDING_UNAVAILABLE`;
10. `RESOURCE_POLICY_UNAVAILABLE`;
11. `RESOURCE_CAPACITY_UNAVAILABLE`; and
12. `RESOLUTION_REQUIREMENTS_SATISFIED`, producing the nominal primary or
    witness grant outcome fixed by the request type, only after every prior
    condition is absent.

Secondary protected facts may be retained, but one resolution has exactly one
terminal outcome/reason and either one exact grant or no grant.

Only the two issued outcomes carry an exact nominal `PrimaryRunGrantRef` or
`WitnessRunGrantRef`. Every other result carries a closed reason and no grant.
The resolution record binds the exact request, policy, answer-key target,
role-specific execution target, case, role, applicability evidence,
qualification/resource authorization inputs, resolver identity, outcome, and
optional grant ref. A missing primary, incomplete policy, forged/mismatched
request, or unavailable qualification therefore has a canonical pre-run home
and never becomes a runner exception or fabricated run.

Each grant is immutable, one-use, audience-specific, and bound to the exact
request, policy, answer-key target, role-specific execution target, case,
authority function, source class, implementation, environment,
method/configuration, representation, resource, disclosure, and resolver
issuance identity. For a composition, that includes the exact composition
method/implementation and ordered component entry refs. The resolver issuance
identity is a pre-existing trusted issuer/capability identity plus an issuance
token; it is never the later `ReferenceResolutionRecordRef`. On a successful
path the resolver constructs the grant first, then constructs the resolution
record pointing backward to the completed grant ref. The grant never points to
that record, so no digest cycle exists. Grant construction and verification
are separate from runner implementation; a runner cannot issue its own
capability.

A primary grant targets either one exact primary entry or one exact qualified
composition. The latter binds the composition implementation and ordered
members as a single nominal primary capability; it does not expose a generic
caller-supplied list or promote member entries. A witness grant targets either
one exact witness entry or one exact qualified witness composition and also
cross-binds the policy's answer-key target. Compared primary and witness
targets reject any member/entry-ref overlap.

### 8.2 Primary and witness runners

B-04 requires distinct nominal primary and witness boundaries. Illustrative
names below define the semantic shape, not executable code in this PR:

```text
PrimaryReferenceRunner.run_primary(
    grant: exact PrimaryRunGrant,
    request: exact PrimaryReferenceRequest,
) -> exact PrimaryReferenceRunOutcome

WitnessReferenceRunner.run_witness(
    grant: exact WitnessRunGrant,
    request: exact WitnessReferenceRequest,
) -> exact WitnessReferenceRunOutcome
```

Trusted policy resolution issues the exact grant. The caller cannot choose or
override:

- a solver, language, package, executable, algorithm, tolerance, mesh,
  timestep, precision, hardware, environment, or reference role;
- a path, URI, module, callable, expression, arbitrary PDE string, code,
  package request, credential, or deserialization payload;
- a generic `truth_mode`, `primary | witness` string, fixture/production flag,
  fallback, retry, cache bypass, or qualification Boolean; or
- a different case, policy, role entry, population, evidence depth, or
  reference fidelity.

Each request binds the exact case, policy, answer-key target/function,
representation, request/idempotency, requested resource-policy, and disclosure
identities. A witness request additionally binds one exact registered witness
target/function and keeps the answer-key target as comparison scope. Trusted
resolution adds the exact role-specific execution target, eligible
entry/composition implementation and ordered members, environment,
method/configuration, precision/hardware, and resource authorization to the
nominal grant. A runner validates the exact grant object before crossing its
provider boundary and returns only its nominal outcome family.

Successful process execution proves only that a registered implementation
returned a structurally valid result. Language, library, solver name, cost,
speed, nominal tolerance, and process success grant no scientific authority.

Retries, fallback, scheduling, transport, service isolation, authentication,
and durable storage are not added here. A later owner may execute them only
without changing the registered case, role, fidelity, evidence depth, or
scientific meaning by candidate.

## 9. Closed run records and outcomes

Every grant-authorized invocation produces one immutable `ReferenceRunRecord`
and exactly one closed outcome. The semantic outcome partition is:

```text
SUPPORTED
UNCERTAINTY_UNRESOLVED
CONDITIONING_UNRESOLVED
APPLICABILITY_UNRESOLVED
NOT_APPLICABLE
UNSUPPORTED
NUMERICAL_FAILURE
MALFORMED_OR_PROVENANCE_FAILURE
INFRASTRUCTURE_FAILURE
CANCELLED
```

`SUPPORTED` means only that the exact registered run satisfies the structural
support, applicability, conditioning, diagnostic, provenance, and uncertainty
requirements stated by its policy and role-specific execution target. For a
composition this includes its exact combination method and component
bindings. It still does not create a `TruthAsset`; positive admission is
separate.

Every non-supported outcome carries exactly one closed
`ReferenceFailureReason` compatible with its outcome:

```text
POLICY_ENTRY_NOT_APPLICABLE
POLICY_ENTRY_UNSUPPORTED
UNCERTAINTY_EVIDENCE_UNRESOLVED
CONDITIONING_EVIDENCE_UNRESOLVED
APPLICABILITY_ASSESSMENT_UNAVAILABLE
REQUEST_OR_GRANT_INVALID
NUMERICAL_NONCONVERGENCE
NUMERICAL_INVALID_RESULT
PROVIDER_RESULT_MALFORMED
PROVENANCE_INVALID
VERSION_OR_IDENTITY_MISMATCH
DEPENDENCY_UNAVAILABLE
TRANSPORT_FAILURE
PROCESS_FAILURE
CAPACITY_UNAVAILABLE
RESOURCE_LIMIT
TIMEOUT
TRUSTED_CANCELLATION
```

The profile owns an exhaustive outcome-to-reason compatibility matrix.
Unknown or mismatched reason codes reject the provider result; free-text
provider exceptions never define outcome semantics.

These run outcomes apply only after resolution issued an exact grant. Missing
primary, policy incompleteness, or a pre-run applicability/qualification/
resource failure remains a `ReferenceResolutionRecord`, not a fabricated run.
If multiple conditions are observed after issuance, the future implementation
applies this exact total run-terminal reason precedence:

1. `REQUEST_OR_GRANT_INVALID`;
2. `VERSION_OR_IDENTITY_MISMATCH`;
3. `PROVENANCE_INVALID`;
4. `TRUSTED_CANCELLATION`, only when its atomic terminal claim was accepted;
5. `TIMEOUT`;
6. `RESOURCE_LIMIT`;
7. `CAPACITY_UNAVAILABLE`;
8. `DEPENDENCY_UNAVAILABLE`;
9. `TRANSPORT_FAILURE`;
10. `PROCESS_FAILURE`;
11. `PROVIDER_RESULT_MALFORMED`;
12. `NUMERICAL_NONCONVERGENCE`;
13. `NUMERICAL_INVALID_RESULT`;
14. `POLICY_ENTRY_NOT_APPLICABLE`;
15. `POLICY_ENTRY_UNSUPPORTED`;
16. `APPLICABILITY_ASSESSMENT_UNAVAILABLE`;
17. `CONDITIONING_EVIDENCE_UNRESOLVED`;
18. `UNCERTAINTY_EVIDENCE_UNRESOLVED`; and
19. `SUPPORTED`, with no failure reason, only when every preceding condition
    is absent.

The attempt ledger permits one atomic terminal claim. A cancellation racing a
provider result wins only if its trusted claim was accepted first; otherwise
the already accepted provider terminal is preserved. Secondary observed facts
may remain in protected diagnostics but cannot change the single terminal
outcome or public error.

The record binds the exact request/grant, case, policy, answer-key target,
role-specific execution target, evidence and authority roles, source,
implementation, environment, method/configuration, and, for composition,
ordered component entry/run-input facts. It also binds the artifact content
descriptor/digest or explicit absence (never an artifact ref), applicability,
conditioning, uncertainty, diagnostics, provenance, resource receipt, and
outcome-specific reason refs.

Rules:

- partial output cannot be promoted to `SUPPORTED`;
- nominal solver tolerance is not uncertainty;
- unsupported, not-applicable, uncertain, conditioning-unresolved,
  numerical, malformed/provenance, infrastructure, and cancelled outcomes
  carry no answer-key artifact authority;
- infrastructure ambiguity remains infrastructure, not candidate science;
- failures and public errors are fixed, typed, non-echoing, and unchained;
- protected case, solution, seed, draw, configuration, path, environment,
  provider, and diagnostic material cannot appear in public errors or logs;
  and
- an outcome cannot create a candidate gate failure, score zero, ranking loss,
  frontier event, settlement event, or product decision.

## 10. Comparison, disagreement, and contested reference

Primary/witness comparison is a separate policy-owned operation over exact run
refs. Neither runner may self-declare agreement, independence, or truth.

The closed comparison partition is:

```text
AGREEMENT_WITHIN_REGISTERED_POLICY
CONTESTED_DISAGREEMENT
COMPARISON_INDETERMINATE
```

The closed comparison-reason family is:

```text
COMPARISON_REQUIREMENTS_SATISFIED
PRIMARY_OR_WITNESS_NOT_SUPPORTED
COMPARISON_INPUT_IDENTITY_MISMATCH
COMPARISON_PROVENANCE_INVALID
COMPARISON_APPLICABILITY_MISMATCH
COMPARISON_METHOD_UNAVAILABLE
COMPARISON_UNCERTAINTY_UNRESOLVED
COMPARISON_DEPENDENCE_UNRESOLVED
REGISTERED_DISAGREEMENT_EXCEEDED
```

Exactly one outcome/reason is selected under this exact total precedence:

1. `COMPARISON_INPUT_IDENTITY_MISMATCH` → `COMPARISON_INDETERMINATE`;
2. `COMPARISON_PROVENANCE_INVALID` → `COMPARISON_INDETERMINATE`;
3. `PRIMARY_OR_WITNESS_NOT_SUPPORTED` → `COMPARISON_INDETERMINATE`;
4. `COMPARISON_APPLICABILITY_MISMATCH` → `COMPARISON_INDETERMINATE`;
5. `COMPARISON_METHOD_UNAVAILABLE` → `COMPARISON_INDETERMINATE`;
6. `COMPARISON_UNCERTAINTY_UNRESOLVED` → `COMPARISON_INDETERMINATE`;
7. `COMPARISON_DEPENDENCE_UNRESOLVED` → `COMPARISON_INDETERMINATE`;
8. `REGISTERED_DISAGREEMENT_EXCEEDED` → `CONTESTED_DISAGREEMENT`; and
9. `COMPARISON_REQUIREMENTS_SATISFIED` →
   `AGREEMENT_WITHIN_REGISTERED_POLICY` only when all prior conditions are
   absent.

The B-04-D11 matrix fixes these exact pairings and rejects unknown pairs.
Secondary protected facts do not create another comparison result.

The comparison record binds the exact policy and comparison-policy version,
answer-key authority target, exact witness target, both run records, common
case and representation, disjoint target member/entry refs, comparison method,
uncertainty/dependence treatment, applicability, evidence refs, and result.

No numerical disagreement limit is selected by this contract. Until a
Challenge owner supplies and qualifies one, real comparison is
`COMPARISON_INDETERMINATE` or typed unavailable.

Reference disagreement cannot be resolved by:

- averaging incompatible answers or uncertainties;
- majority vote, source count, solver reputation, cost, or speed;
- weakening a gate, widening a tolerance after observing the result, or
  choosing the more convenient source;
- treating shared implementation as independent corroboration; or
- turning the disagreement into candidate failure.

`CONTESTED_DISAGREEMENT` blocks answer-key admission for the affected scope
unless the same prospective policy already defines a separately qualified,
applicable resolution path. This contract registers no such production path.

## 11. Independence and correlation disclosure

Every comparison-capable policy records material shared and distinct factors
for at least:

```text
governing equations and model-form assumptions
closures, constitutive relations, and boundary/initial conditions
discretization and time-integration families
meshes, grids, quadrature, and adaptivity
transforms, bases, interpolation, and representation adapters
libraries, dependencies, generated code, and copied implementation paths
calibration, experimental, industrial, and training data
personnel, organizations, review, and common design lineage
floating-point, precision, compiler, runtime, and deterministic-mode paths
hardware, accelerators, drivers, and resource classes
```

“Independent implementation” is not a sufficient independence claim. Missing
evidence produces `EVIDENCE_REQUIRED` or a recorded correlation limitation.
Agreement between correlated sources cannot promote an unqualified source.

Uncertainty combination by quadrature or zero-covariance assumption is
forbidden unless the B-06 Dossier and later B-05 decision contract qualify the
exact dependence claim for the exact use. Otherwise the downstream owner uses
joint propagation, conservative bounds, or an indeterminate result.

## 12. Support, applicability, conditioning, and uncertainty

### 12.1 Support and applicability

Support and applicability are explicit case-level assessments bound to the
exact role-specific execution target and its evidence. For a composition the
assessment binds its composition method and ordered component refs as well as
the member evidence. They distinguish:

```text
SUPPORTED_AND_APPLICABLE
NOT_APPLICABLE
UNSUPPORTED
ASSESSMENT_UNAVAILABLE
```

An envelope label alone is insufficient. The assessment binds the exact
physical regime, geometry/topology, boundary/initial-condition class, forcing,
population/stratum, time horizon, representation, method/configuration,
precision, environment, and limitations that matter.

An unsupported or not-applicable case remains visible. It cannot be silently
replaced with an easier case, censored without the B-02A prospective policy,
or answered by a weaker unregistered source.

### 12.2 Conditioning and numerical sensitivity

Conditioning and sensitivity have explicit status:

```text
ASSESSED_WITHIN_REGISTERED_SCOPE
UNRESOLVED
OUTSIDE_REGISTERED_SCOPE
ASSESSMENT_UNAVAILABLE
```

The status binds its method, configuration, perturbations/refinement evidence,
precision/environment, evidence refs, and limitations. A converged process or
small residual is not by itself a conditioning assessment.

### 12.3 Uncertainty representation

Every uncertainty representation binds:

- the quantity/estimand and units it describes;
- interval, ensemble, bound, covariance, distributional, or other registered
  representation kind;
- construction method and implementation/environment refs;
- evidence refs, applicability and coverage meaning;
- aleatory, numerical, model-form, measurement, reconstruction, representation,
  execution, and other component labels where applicable;
- all known dependence and interaction bindings; and
- limitations, unresolved components, and propagation-use restrictions.

Component labels are bookkeeping, not proof of independence. A solver
tolerance, mesh spacing, residual, witness discrepancy, or single refinement
plot is not automatically an uncertainty floor. This contract sets no numeric
floor and no acceptance criterion.

## 13. Reference artifacts and positive-only TruthAsset admission

### 13.1 ReferenceArtifact

A structurally valid produced result is a `ReferenceArtifact`. It binds its
exact completed run-record ref, repeats the run's exact content descriptor/
digest and meaning identities, and remains unqualified answer-key material.
The run record never points forward to this artifact. A failed outcome has no
artifact except an explicit typed absence or diagnostic evidence ref.

### 13.2 TruthAsset admission

Only a separately configured `TruthAssetAdmissionAuthority` may decide
admission. Before it can act, a distinct trusted
`TruthAssetAdmissionGrantIssuer` evaluates the complete structurally bound
admission-attempt graph and
emits one immutable `TruthAssetAdmissionGrantIssuanceRecord`. Its closed
outcome is:

```text
ADMISSION_GRANT_AUTHORIZED
ADMISSION_GRANT_UNAVAILABLE
```

Its closed reason is exactly one of:

```text
ADMISSION_GRANT_REQUIREMENTS_SATISFIED
ADMISSION_GRAPH_CROSS_BINDING_MISMATCH
ADMISSION_GRANT_SCOPE_UNAVAILABLE
ADMISSION_AUTHORITY_BINDING_UNAVAILABLE
```

Only `ADMISSION_GRANT_AUTHORIZED` /
`ADMISSION_GRANT_REQUIREMENTS_SATISFIED` permits a grant. The issuer selects the
first applicable reason under this exact total precedence:

1. `ADMISSION_GRAPH_CROSS_BINDING_MISMATCH`;
2. `ADMISSION_GRANT_SCOPE_UNAVAILABLE`;
3. `ADMISSION_AUTHORITY_BINDING_UNAVAILABLE`; and
4. `ADMISSION_GRANT_REQUIREMENTS_SATISFIED`, authorizing a grant only when
   every prior structural/capability condition is absent.

B-04-D11 freezes the exhaustive compatibility matrix.

The issuer does not decide run support, artifact eligibility, comparison,
qualification, provenance/rights sufficiency, or use/disclosure sufficiency.
Those are substantive admission-authority decisions below. Grant issuance
proves only that one exact, structurally valid attempt may be decided; it does
not predict or constrain the decision outcome.

Malformed, noncanonical, or unreconstructable input fails at the issuer
boundary with a fixed non-echoing error and produces no issuance record or
grant. `ADMISSION_GRAPH_CROSS_BINDING_MISMATCH` is reserved for individually
reconstructable inputs whose exact policy/case/target/version refs disagree,
so the issuer can safely bind the attempted graph and typed mismatch without
canonicalizing hostile input.

The issuance record binds the exact issuer identity and pre-existing issuance
token, policy, answer-key authority target, primary execution target,
attempted run, artifact ref or typed absence, every submitted required
comparison/witness target and qualification binding, intended admission
authority, provenance/rights and use/disclosure inputs, scope, and
decision-profile version. It contains no grant ref. After its ref is computed,
the issuer may construct one immutable one-use
`TruthAssetAdmissionGrant` that repeats those bindings and points backward to
the exact issuance-record ref. The grant cannot point forward to a decision;
this order is acyclic. If the trusted issuer is unavailable, admission is
typed unavailable and no record or grant is fabricated.

The admission authority validates the exact issuance record and grant and
emits one immutable
`TruthAssetAdmissionDecisionRecord` with one closed outcome:

```text
ADMITTED
REJECTED
UNAVAILABLE
INDETERMINATE
```

The closed admission-reason family is:

```text
ADMISSION_REQUIREMENTS_SATISFIED
RUN_NOT_SUPPORTED
ARTIFACT_ABSENT_OR_INELIGIBLE
REQUIRED_COMPARISON_CONTESTED
REQUIRED_COMPARISON_INDETERMINATE
QUALIFICATION_UNAVAILABLE
POLICY_OR_IDENTITY_MISMATCH
PROVENANCE_OR_RIGHTS_INVALID
GRANT_INVALID_OR_CONSUMED
USE_OR_DISCLOSURE_UNAVAILABLE
```

Only `ADMITTED / ADMISSION_REQUIREMENTS_SATISFIED` is positive. The canonical
profile owns the exhaustive decision/reason compatibility matrix; unknown or
mismatched combinations reject.

Admission selects exactly one outcome/reason under this exact total
precedence:

1. `GRANT_INVALID_OR_CONSUMED` → `REJECTED`;
2. `POLICY_OR_IDENTITY_MISMATCH` → `REJECTED`;
3. `RUN_NOT_SUPPORTED` → `REJECTED`;
4. `ARTIFACT_ABSENT_OR_INELIGIBLE` → `REJECTED`;
5. `REQUIRED_COMPARISON_CONTESTED` → `INDETERMINATE`;
6. `REQUIRED_COMPARISON_INDETERMINATE` → `INDETERMINATE`;
7. `QUALIFICATION_UNAVAILABLE` → `UNAVAILABLE`;
8. `PROVENANCE_OR_RIGHTS_INVALID` → `REJECTED`;
9. `USE_OR_DISCLOSURE_UNAVAILABLE` → `UNAVAILABLE`; and
10. `ADMISSION_REQUIREMENTS_SATISFIED` → `ADMITTED` only when every prior
    condition is absent.

The arrows above are normative outcome/reason pairings. Secondary protected
facts cannot make multiple terminal decisions.

The decision record and ref bind the exact issuance record, grant, complete
submitted admission-attempt graph (including every typed absence), authority
identity, outcome, closed reason refs, and consumed-grant receipt. The issuer
and admission authority are distinct
configured identities. A runner, source adapter, generator, caller, artifact,
or admission authority cannot issue its own admission grant; the grant issuer
cannot decide admission. Rejected, unavailable, and indeterminate decisions
are typed records, never assets.

Bare absence or outage of the configured admission authority cannot be
self-recorded by that absent authority: it yields no admission decision/ref and
no B-02A eligibility. Only a separately registered infrastructure observer and
exact failure ref may support a later B-02A request. The closed decision
outcome `UNAVAILABLE` remains reachable through qualification or
use/disclosure reasons emitted by an available authority.

A `TruthAsset` may be constructed only from the exact `ADMITTED` decision and
must bind its `TruthAssetAdmissionDecisionRecordRef`. A raw run record, policy,
artifact, qualification slot, admission-authority label, or caller Boolean is
insufficient.

A `TruthAsset` binds at least:

```text
TruthAsset identity/version and supersession
Challenge, physical-system, output, claim, population, SamplingPlan, and exact case
ReferencePolicy, answer-key authority target, primary execution target, and any composition-member identities
authority and evidence roles
run and required comparison records
implementation, environment, method/configuration, precision, and hardware
solution artifact, representation, units, coordinates, and time semantics
support/applicability and conditioning status
uncertainty representation and evidence refs
independence/correlation limitations
provenance, rights/access, disclosure, qualification, and admission authority
exact positive admission-grant issuance record, grant, and decision record
known limitations and downstream-use restrictions
```

There is no failed, uncertain, contested, unsupported, or infrastructure
`TruthAsset`. Those are run, comparison, or admission outcomes. This
positive-only rule corrects documentation shorthand that could otherwise make
a failed object look like an answer key.

Production admission remains unavailable until B-06 implements and owners
approve the exact Dossier/qualification path. B-04 contract completeness is
not qualification.

### 13.3 FixtureReferenceAsset

Fixture runs use a distinct nominal `FixtureReferenceAsset`. It carries
structural fixture provenance and has its own exact canonical encoding and
ref. It cannot be relabeled, subclassed, wrapped, serialized, or re-encoded as
a `TruthAsset` or other production evidence, and it cannot be admitted as a
`TruthAsset`. It cannot enter a production
qualification manifest, B-05 score-bearing measurement, official evaluation,
`LIVE`, leaderboard authority, frontier, product, network, weight, emission,
payment, or settlement path.

The later B-04 implementation owns the minimal standard-library deterministic
primary and witness fixture runners, grants, outcomes, and fixture assets
needed to prove this contract and supply B-07F's existing dependency. They use
conspicuous fixed test data and do not implement a PDE, Cole–Hopf, Julia, a
numerical method, or a real provider. B-E2 owns later Julia/service adapters
and the expanded runtime, timeout, version-mismatch, transport, process, and
fault-injection harness. B-07F composes only the B-04 fixture surface; it does
not wait for or absorb B-E2.

## 14. Cache and precomputed-output identity

Cached or precomputed output is permitted only when its key binds every
identity that affects scientific meaning, including:

- Challenge, physical system, output, claim, population, SamplingPlan, case,
  and representation;
- policy, answer-key authority target, role-specific execution target,
  composition members, authority/evidence role, comparison and qualification
  state;
- source, implementation, code/dependency, method/configuration, precision,
  environment, platform, hardware/resource class, and deterministic mode;
- applicability, conditioning, uncertainty, provenance, rights/access, and
  disclosure policy; and
- artifact schema/content and canonicalization version.

A cache hit must revalidate the complete record/ref graph and return the exact
registered bytes. Unknown, partial, stale, revoked, cross-case, cross-role,
cross-policy, cross-environment, or otherwise mismatched cache state fails
closed. Cache presence, age, cost, or convenience grants no authority.

This contract selects no cache implementation, retention period, timeout,
retry policy, or production resource value.

## 15. No-silent-fallback rule

If the registered primary is absent, unsupported, inapplicable, uncertain,
conditioning-unresolved, contested, numerically failed, malformed,
provenance-invalid, infrastructure-failed, or cancelled, the result remains
typed and fail closed.

No mock, fixture, analytic convenience path, weaker solver, witness, surrogate,
stale cache entry, candidate output, generator output, or alternate service may
replace it implicitly.

A future fallback may exist only when the same immutable prospective policy
names, orders, qualifies, and bounds it, including exact applicability,
uncertainty, comparison, provenance, and historical-interpretation rules.
This contract chooses no fallback source or priority; therefore production
fallback is currently unavailable.

## 16. Disclosure, security, and public projection

Reference request, run, comparison, artifact, and `TruthAsset` records are
internal or protected by default. Public disclosure is positive allow-list
only and reconstructs new audience-owned projections.

No public surface, error, log, card, prior, practice result, leaderboard, or
MCP output may expose:

- protected case content or reversible case identity;
- official entropy, seed, draw, slot, ordering, or mixture realization;
- solution fields, per-case discrepancies, uncertainty internals, exact
  margins, conditioning diagnostics, or hidden reference depth;
- implementation paths, service topology, cache keys, provider details,
  environment variables, credentials, commands, stack traces, or exception
  text; or
- private rights, customer, industrial, experimental, or provenance material.

Public-safe policy and artifact identities may be exposed only when a
separately registered disclosure policy positively allows them and the
projection cannot reconstruct protected material. Hashing a secret value does
not automatically make it public-safe.

Authentication, network transport, process isolation, secrets, quotas,
customer privacy, and production operations remain later contracts. This
engineering contract makes no security qualification claim.

## 17. B-02A censoring and failure separation

B-02A already reserves exact reference censoring reasons:

```text
REFERENCE_UNAVAILABLE
REFERENCE_DISPUTED
REFERENCE_NUMERICAL_FAILURE
REFERENCE_RESOURCE_LIMIT
REFERENCE_TIMEOUT
```

B-04 owns the reference facts and policy eligibility required before trusted
composition may request those reasons. B-02A continues to own the
`CensoringRecord`, SamplingPlan linkage, intended-unit accounting, and
realized-valid-evidence population. B-04 does not create a second case state,
censoring record, replacement policy, or generator outcome.

The closed eligibility mapping is:

| B-04 terminal fact | Eligible B-02A censoring reason |
|---|---|
| resolution `POLICY_INCOMPLETE / POLICY_PRIMARY_MISSING` or `POLICY_INCOMPLETE / POLICY_ENTRY_INCOMPLETE` | `REFERENCE_UNAVAILABLE` |
| resolution `ROLE_UNAVAILABLE / ROLE_NOT_REGISTERED` | `REFERENCE_UNAVAILABLE` |
| resolution `NOT_APPLICABLE / CASE_NOT_APPLICABLE` | `REFERENCE_UNAVAILABLE` |
| resolution `UNSUPPORTED / CASE_UNSUPPORTED` | `REFERENCE_UNAVAILABLE` |
| resolution `APPLICABILITY_UNRESOLVED / APPLICABILITY_ASSESSMENT_UNAVAILABLE` | `REFERENCE_UNAVAILABLE` |
| resolution `QUALIFICATION_UNAVAILABLE / QUALIFICATION_BINDING_UNAVAILABLE` | `REFERENCE_UNAVAILABLE` |
| resolution `IDENTITY_OR_PROVENANCE_FAILURE / RESOLUTION_IDENTITY_MISMATCH` or `IDENTITY_OR_PROVENANCE_FAILURE / RESOLUTION_PROVENANCE_INVALID` | `REFERENCE_UNAVAILABLE` |
| resolution `RESOURCE_AUTHORIZATION_UNAVAILABLE` / `RESOURCE_POLICY_UNAVAILABLE` | `REFERENCE_UNAVAILABLE` |
| resolution `RESOURCE_AUTHORIZATION_UNAVAILABLE` / `RESOURCE_CAPACITY_UNAVAILABLE` | `REFERENCE_RESOURCE_LIMIT` |
| `CONTESTED_DISAGREEMENT` | `REFERENCE_DISPUTED` |
| `COMPARISON_INDETERMINATE` | `REFERENCE_UNAVAILABLE` |
| `NUMERICAL_FAILURE / NUMERICAL_NONCONVERGENCE` or `NUMERICAL_FAILURE / NUMERICAL_INVALID_RESULT` | `REFERENCE_NUMERICAL_FAILURE` |
| `INFRASTRUCTURE_FAILURE` / `TIMEOUT` | `REFERENCE_TIMEOUT` |
| `INFRASTRUCTURE_FAILURE` / `RESOURCE_LIMIT` or `CAPACITY_UNAVAILABLE` | `REFERENCE_RESOURCE_LIMIT` |
| `INFRASTRUCTURE_FAILURE` / `DEPENDENCY_UNAVAILABLE`, `TRANSPORT_FAILURE`, or `PROCESS_FAILURE` | `REFERENCE_UNAVAILABLE` |
| `MALFORMED_OR_PROVENANCE_FAILURE / REQUEST_OR_GRANT_INVALID` | `REFERENCE_UNAVAILABLE` |
| `MALFORMED_OR_PROVENANCE_FAILURE / PROVIDER_RESULT_MALFORMED` | `REFERENCE_UNAVAILABLE` |
| `MALFORMED_OR_PROVENANCE_FAILURE / PROVENANCE_INVALID` | `REFERENCE_UNAVAILABLE` |
| `MALFORMED_OR_PROVENANCE_FAILURE / VERSION_OR_IDENTITY_MISMATCH` | `REFERENCE_UNAVAILABLE` |
| `UNCERTAINTY_UNRESOLVED / UNCERTAINTY_EVIDENCE_UNRESOLVED` | `REFERENCE_UNAVAILABLE` |
| `CONDITIONING_UNRESOLVED / CONDITIONING_EVIDENCE_UNRESOLVED` | `REFERENCE_UNAVAILABLE` |
| `APPLICABILITY_UNRESOLVED / APPLICABILITY_ASSESSMENT_UNAVAILABLE` | `REFERENCE_UNAVAILABLE` |
| `NOT_APPLICABLE / POLICY_ENTRY_NOT_APPLICABLE` | `REFERENCE_UNAVAILABLE` |
| `UNSUPPORTED / POLICY_ENTRY_UNSUPPORTED` | `REFERENCE_UNAVAILABLE` |
| `CANCELLED / TRUSTED_CANCELLATION` | no automatic censoring eligibility; a separately registered B-02A policy must resolve cancellation without relabeling it reference failure |
| admission-grant issuance `ADMISSION_GRANT_UNAVAILABLE` with any compatible closed issuance reason | `REFERENCE_UNAVAILABLE` |
| non-`ADMITTED` admission decision | `REFERENCE_DISPUTED` only for `REQUIRED_COMPARISON_CONTESTED`; otherwise `REFERENCE_UNAVAILABLE` |

Eligibility does not itself censor or replace a case. Trusted composition
passes the exact terminal record/ref and proposed reason to B-02A, which
validates its own prospective policy and accounting. Unknown combinations fail
closed. Bare absence of the trusted admission-grant issuer or configured
admission authority, and malformed/unreconstructable issuer input, create no
B-02A eligibility because no exact B-04 terminal event/ref exists; only a
separately registered infrastructure trigger and exact failure ref may support
a later B-02A request for that absence.

Reference failure is not:

```text
candidate physics failure
mandatory candidate gate failure
candidate score zero
ranking loss
generator nonconformance by itself
frontier decision
product rejection
payment or settlement event
```

The affected case or evaluation remains typed unavailable, censored,
contested, indeterminate, or infrastructure-failed according to its separately
registered owner policy.

## 18. Downstream ownership seams

| Owner | B-04 supplies | B-04 does not supply |
|---|---|---|
| B-02A | Reference-trigger facts exact-bound to B-02A-owned case/evidence refs for trusted censoring composition. | Case/evidence identity, population, SamplingPlan, disposition, replacement, or realized-evidence accounting. |
| B-03 | No reverse dependency; composition hands B-04 an exact canonical case. | Generator adequacy, conformance, retry, or truth certification. |
| B-05 | An admitted `TruthAssetRef`, applicability/conditioning status, uncertainty representation, and limitations. | Measurement operator, numerical/reference floor, gate, threshold, weight, aggregation, ranking, or Score Pack. Raw run success is not score input. |
| B-06 | Policy, run, comparison, independence, uncertainty, provenance, limitation, and admission evidence slots. | Dossier schema, signer authority, qualification decision, or `LIVE` activation. |
| B-07F | Distinct fixture-only reference assets and typed fixture outcomes. | Production reference rights, real solver, `TruthAsset`, official scientific evidence, or lifecycle mutation. |
| B-E2 | Closed runtime/failure semantics for Julia or any other registered implementation. | Julia authority, solver qualification, or permission to add fallback. |
| A3 / later registry | A prospective exact `ReferencePolicy`/qualification identity seam after its owner contract. | Retroactive mutation of historical Challenge records or current LIVE qualification. |

## 19. Reserved human inputs

The following remain unavailable:

- viscosity `5e-3` or any other physical parameter as production authority;
- Cole–Hopf, Julia/SciML, a conservative solver, dataset, experiment,
  industrial golden, customer service, surrogate, accelerator, or hybrid as a
  qualified role;
- real truth target, primary/witness hierarchy, support/envelope, exclusions,
  failure regions, and case-specific reference depth;
- equations/closures, method, discretization, mesh, timestep, tolerance,
  precision, compiler, runtime, environment, hardware, or deterministic mode;
- uncertainty components, floors, coverage, covariance, dependence,
  conditioning, sensitivity, acceptable disagreement, or fallback order;
- cache, retry, timeout, capacity, cost, latency, resource, anchor-sampling,
  access, rights, privacy, security, operations, or retention policy;
- qualification evidence, acceptance criteria, reviewer signoff, or exact
  `LIVE` activation; and
- measurement, score, frontier, product, commercial, network, economic,
  settlement, weight, or emission policy.

Agents implement only explicit fail-closed seams. They do not populate these
values from recommendations, old fixtures, successful runs, or tests.

## 20. Implementation and test requirements for the later B-04 phase

Implementation cannot start until this exact contract tree normally merges,
exact-main CI succeeds, and the separately reviewed/notified B-04-D11 freezes
the complete v1 field/type/order registry, outcome/reason matrices, and exact
curated root-export tuple. A later implementation must add, at minimum:

- exact nominal models, refs, canonical bytes, history, runner grants,
  primary/witness requests and outcomes, comparison, admission, fixture asset,
  disclosure, and fixed errors under `carbon.evaluation`;
- exact positive-only admission-grant issuance records, grants, closed
  admission decisions, one-use consumption, decision refs, issuer/authority
  separation, and self-admission rejection;
- exact object/ref reconstruction, hostile-input, mutation, role-confusion,
  stale/cross-identity, cache, no-fallback, no-leakage, and outside-wheel tests;
- MMS-verification-versus-validation and authority-transfer rejection;
- correlated-witness disclosure and no-average disagreement tests;
- positive-only `TruthAsset` admission and fixture-to-LIVE impossibility;
- reference/infrastructure-versus-candidate/scoring failure separation; and
- package, dependency, code-authority, invariant, and no-optional-dependency
  coverage.

The fixture proof includes only the minimal deterministic standard-library
primary/witness runners and `FixtureReferenceAsset` path owned by B-04. B-E2
retains Julia/service adapters and expanded runtime/failure injection.

The implementation ticket must not add a real solver, Julia service,
Cole–Hopf routine, artifact store, network transport, measurement, score,
Dossier, production cache, or `LIVE` adapter.

## 21. Bounded maturity

At this contract session's stop:

```text
SPECIFIED: CANDIDATE — BOUNDED ENGINEERING CONTRACT
RATIFIED_ENGINEERING_CONTRACT: NO — NORMAL MERGE AND EXACT-MAIN CI PENDING
IMPLEMENTED: NO
TESTED: DOCUMENT AND EXISTING-BASELINE VALIDATION ONLY
REFERENCE_QUALIFIED: NO
OPERATIONS_APPROVED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```

> **Closing rule:** a solver produces a reference artifact. Only an exact,
> prospectively registered, applicable, uncertainty-bearing, independently
> reviewed, positively admitted evidence chain may create a bounded
> `TruthAsset`; every missing or failed link remains typed and fail closed.
