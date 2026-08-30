# Scientific Challenge Authoring Contract

**Version:** 0.1
**Status:** **AGENT-SELECTED WORKING CONTRACT**
**Ticket:** B-02A — Scientific authoring and canonical-case contracts
**Authority base:** `e10107644d5fb0c7d69b153c0c3b8a03b93b19bb`, tree `0f6beb5b000e771fd7e050f150e1074ea2a6fb1f`
**Delegated governance:** PR #61 merge `7bdf4971b7d0b3ee8ffde577595a49c6b5456961`, tree `109bb59e117d25cbdfddcc4c4a8fe6e3f3f34cdb`
**Final review required:** independent SciML/physics, statistics, and protocol review; blocking-finding resolution; exact-head CI; normal merge
**Implementation:** bounded PR #60 candidate present under `.agent/DELEGATED_DECISION_PROTOCOL.md`; final exact-head review, CI, and normal merge remain pending; no affirmative lead-response or silence gate applies

> **Maturity ceiling.** This document specifies the working B-02A semantics.
> Neither the document nor an implementation/test result creates scientific
> qualification, security qualification, network authority, commercial
> validation, production qualification, LIVE authority, product claim,
> frontier event, launch decision, settlement obligation, chain action,
> scoring weight, network weight, or emission authority. A content digest,
> fixture, deterministic reconstruction, review request, draft pull request,
> or normal merge does not create any of those states.

---

## 1. Purpose, scope, and normative language

Carbon must author the scientific task before a generator, solver, compiler,
candidate, scorer, or runtime path can define it by accident. This working
contract defines the immutable authored objects, exact references, canonical identity,
validation rules, population distinctions, canonical-case boundary,
provenance seams, and downstream ownership needed for that purpose.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, and **MAY** are normative for the B-02A working
implementation. Final repository acceptance still requires independent review,
resolution of blocking findings, exact-head validation, and normal merge.

The contract owns the semantics of exactly these top-level identity object
families and their exact references. The first five are prospectively authored
contracts; `CanonicalChallengeCase` is an immutable realization record created
under the prospectively authored case schema:

- `PhysicalSystemSpec` and `PhysicalSystemSpecRef`;
- `CandidateOutputContract` and `CandidateOutputContractRef`;
- `InstanceDistributionContract` and
  `InstanceDistributionContractRef`;
- `SamplingPlan` and `SamplingPlanRef`;
- `TrainingSupportContract` and `TrainingSupportContractRef`; and
- `CanonicalChallengeCase` and `CanonicalChallengeCaseRef`.

It also defines the subordinate records required to bind those families. This
document itself confers no runtime or authority. The bounded PR #60 candidate
implements the B-02A types, exact refs, schema-local canonicalizer, loaders,
append-only store, `carbon.authoring` package, tests, and the narrow A3-owned
authoring-graph verification seam described below. It implements no generator,
compiler, reference policy/runner, measurement, Score Pack, dossier, research
service, protected entropy path, qualification decision, or LIVE activation.

### 1.1 Explicit non-goals

This candidate does not:

- select the first real physical task, governing values, official envelope,
  target population, proposal law, evidence weights, strata, sample counts,
  allocations, tolerances, sufficiency rules, training material, data rights,
  censoring/replacement policy, or evidence thresholds;
- adopt fixed-viscosity Burgers, `nu = 5e-3`, a historical viscosity range,
  or any other example as LIVE truth or a default;
- make open PR #40 or the Wave B Miner MCP owner-review candidate into
  authority;
- implement B-02B's compiler or `ResolvedTrainingSamplingPolicy`;
- define B-03 generation, B-04 reference qualification, B-05 measurement or
  scoring, B-06 dossier conclusions, B-07R research architecture, or B-07S
  service wire canonicalization;
- alter A3 Challenge identity or transfer A3 lifecycle, qualification, or LIVE
  ownership; the only A3 change is the fail-closed exact graph-fingerprint and
  configured-verifier integration required by B-02A-D8;
- alter A4 entropy, seed, draw, or commitment authority; or
- revive or select the retired `carbon/challenges`, `carbon/data`, or
  `carbon/physics` paths. Working decision B-02A-D6 selects only
  `carbon.authoring`.

### 1.2 Fail-closed master questions

MQ-001 and MQ-002 are both `DEFERRED_FAIL_CLOSED` for this working-contract
implementation and final-review phase.
The real scientific values they concern remain
`NEW_OWNER_DECISION_REQUIRED`, but their absence does not prevent defining
exact types and authority boundaries. A required unresolved value makes
production authoring unavailable. The literal strings `HUMAN_INPUT`,
`TBD`, `UNKNOWN`, or similar placeholders are not valid scientific values and
MUST NOT be hashed into an apparently complete production object.

---

## 2. Controlling identity and authority rules

### 2.1 Existing Carbon grammar is controlling

All B-02A identities SHALL reuse the public A3 grammar already owned by
`carbon.registry`:

- `ChallengeKey` is the exact immutable pair of canonical `challenge_id` and
  exact `version`;
- logical identifiers use `validate_canonical_identifier` and its lowercase
  ASCII grammar;
- versions use `validate_version` and its bounded path-safe token grammar;
  and
- content digests use the only current Carbon digest grammar,
  `sha256:` followed by exactly 64 lowercase hexadecimal characters.

B-02A MUST NOT create a second Challenge identity, canonical identifier,
version-token, SHA-256, or generic serialization grammar. The current
implementation SHALL call or wrap the current public A3 validators and SHALL
reconstruct exact owned values rather than trust subclassed or aliased input.

### 2.2 Authority is external to authored content

An authored contract's or realized-case record's bytes answer: “what exact
semantics/content is pinned?” A reference answers: “which exact bytes?” A loader result answers: “which bytes
were verified, parsed, reconstructed, and obtained through which controlled
origin?” Qualification answers: “which evidence and human decisions apply?”
LIVE answers: “does A3's current gate allow this exact complete graph?” These
questions MUST remain separate.

No authored object or reference contains a `qualified`, `live`,
`fixture_origin`, `approved`, `production`, or equivalent authority Boolean.
A caller-supplied label MUST NOT confer provenance or authority. Qualification
and LIVE state remain external, exact-pinned, and controlled by their owning
systems.

### 2.3 Immutable prospective history

Every material semantic change creates a new exact object version and content
digest. Historical references always resolve by exact kind, Challenge key,
logical ID, version, canonicalization profile, and digest. There is no
evidence-bearing `latest` lookup, in-place semantic mutation, alias to newer
bytes, retroactive repair, or silent reinterpretation.

An optional `supersedes` edge:

- is an exact same-kind reference;
- points to an older, independently retrievable object;
- MUST NOT form a cycle;
- is prospective metadata inside the new object's identity;
- does not revoke, overwrite, qualify, or reinterpret the predecessor; and
- does not transfer the predecessor's provenance or authority.

Descriptions, UI labels, comments, source paths, registry locations, load
times, current checkout state, and other mutable display metadata are outside
the authored object's identity. A normative scientific statement must be an
identity-bearing clause or an exact content-addressed owner reference, not an
untracked comment.

---

## 3. Common exact value vocabulary

The B-02A implementation SHALL expose exact nominal types rather than an
untyped dictionary API. The following vocabulary fixes the schema meaning;
it does not select scientific values.

| Name | Exact contract |
|---|---|
| `CanonicalId` | Exact built-in `str`; current A3 canonical-identifier grammar; no normalization or subclass. |
| `VersionToken` | Exact built-in `str`; current A3 version grammar; no normalization or subclass. |
| `TaggedSha256` | Exact built-in `str`; current A3 `sha256:<64 lowercase hex>` grammar. |
| `Utf8Text` | Exact built-in `str`; Unicode scalar values only; already NFC; strict UTF-8; no NUL, surrogate, C0, or C1 control; non-NFC input rejects rather than normalizes. |
| `Bool` | Exact built-in `bool`; never accepted through an integer path. |
| `Int64` | Exact built-in `int`, excluding `bool` and subclasses; range `[-2^63, 2^63-1]`. |
| `UInt64` | Exact built-in `int`, excluding `bool` and subclasses; range `[0, 2^64-1]`. |
| `PositiveUInt64` | `UInt64` strictly greater than zero. |
| `FiniteFloat64` | Exact built-in binary64 `float`, excluding integer, Boolean, subclass, NaN, and infinity. Accepted zero is stored and encoded as canonical positive `0.0`; v0.1 defines no signed-zero scientific field. |
| `ClosedTuple[T]` | Exact built-in tuple of exact `T`; order is semantic unless the field explicitly declares set semantics; nested mutable aliases reject or are defensively reconstructed. |
| `RequiredBinding[T]` | Exact `T`; missing/null is invalid. |
| `ApplicabilityBinding[T]` | Closed tagged union `BOUND(T)` or `NOT_APPLICABLE(reason_ref)`; absence, null, and a free-text reason are invalid. |
| `PinnedOwnerRef<K>` | Exact nominal owner-specific ref with kind `K`, scope binding, canonical ID, exact version, and `TaggedSha256`; no path, URI, checkout, load time, or authority label. |

`PinnedOwnerRef<K>` is a specification shorthand, not a new generic public
runtime type. Later code SHALL use distinct nominal types for operating
envelope, claim scope, unit, semantic clause, representation, geometry,
rights profile, generator, evidence campaign, audit evidence, censoring
policy, statistical qualification requirement, and other owner-specific
references. Each reuses A3 identifier/version/digest validation.

### 3.1 Common top-level identity envelope

Every top-level B-02A identity object has these identity-bearing closed fields. The numbers
document the schema; canonical record encoding sorts exact field-name/value
pairs as defined in §4 rather than relying on presentation or insertion order.

| # | Field | Exact type | Rule |
|---:|---|---|---|
| 1 | `object_kind` | closed exact literal | One of the six literals in §3.2; exact nominal object type must agree. |
| 2 | `schema_version` | `VersionToken` | Exact authored schema version; v0.1 selects `1.0` for this working implementation profile. |
| 3 | `canonicalization_profile` | exact literal | `carbon_scientific_authoring_canonical_v1`; no implicit default. |
| 4 | `challenge_key` | exact A3 `ChallengeKey` | Reconstructed from exact built-in strings; no subclass. |
| 5 | `object_id` | `CanonicalId` | Logical identity within the exact Challenge version. |
| 6 | `object_version` | `VersionToken` | Semantic/content version; not a mutable revision counter. |
| 7 | `supersedes` | `ApplicabilityBinding[SameKindRef]` | `NOT_APPLICABLE` for the first version or exact predecessor ref; acyclic and the same Challenge, object kind, and logical object ID. Cross-Challenge and cross-object-ID supersession are forbidden in v1. |

The content digest is not stored inside its own authored bytes. It is computed
over the complete canonical document and stored in the corresponding ref.

### 3.2 Closed object kinds and reference types

| Authored exact type | `object_kind` literal | Corresponding exact ref |
|---|---|---|
| `PhysicalSystemSpec` | `physical_system_spec` | `PhysicalSystemSpecRef` |
| `CandidateOutputContract` | `candidate_output_contract` | `CandidateOutputContractRef` |
| `InstanceDistributionContract` | `instance_distribution_contract` | `InstanceDistributionContractRef` |
| `SamplingPlan` | `sampling_plan` | `SamplingPlanRef` |
| `TrainingSupportContract` | `training_support_contract` | `TrainingSupportContractRef` |
| `CanonicalChallengeCase` | `canonical_challenge_case` | `CanonicalChallengeCaseRef` |

Every ref is a distinct final nominal type. Shared layout does not permit
cross-kind substitution. Its exact closed fields are:

| # | Field | Exact type | Rule |
|---:|---|---|---|
| 1 | `object_kind` | closed literal | Must equal the ref's nominal kind. |
| 2 | `challenge_key` | exact A3 `ChallengeKey` | Exact Challenge family/version. |
| 3 | `object_id` | `CanonicalId` | Must equal the loaded object's logical ID. |
| 4 | `object_version` | `VersionToken` | Must equal the loaded object's semantic version. |
| 5 | `schema_version` | `VersionToken` | Must equal the loaded object's schema version. |
| 6 | `canonicalization_profile` | exact literal | Must identify the exact digest-producing procedure. |
| 7 | `content_digest` | `TaggedSha256` | SHA-256 of the complete domain-separated canonical bytes. |

`InstanceDistributionContractRef` additionally contains
`expected_population_role` as field 8. A consuming object MUST load the
referent and prove that the loaded role equals this field; caller text is not
sufficient. `CanonicalChallengeCaseRef` additionally contains field 8
`disclosure_class`, restricted to `INTERNAL` or `PROTECTED`. A raw case ref is
never a public/miner-safe identifier. Its `disclosure_class` MUST exactly equal
the loaded case object's identity-bearing `disclosure_class`; a caller cannot
upgrade, downgrade, or recompute that class independently.

Exact ref equality requires the exact nominal ref type and equality of every
field. Ref equality is never Python object identity, a path comparison, a
logical ID without a version/digest, or digest alone.

### 3.3 Loader result and origin separation

A later loader SHALL accept an externally expected exact ref plus a bounded
byte source. It SHALL:

1. read bounded regular-file or trusted-store bytes through a secure owner
   path;
2. verify the externally expected digest against exact bytes before parsing;
3. reject an unknown canonicalization profile or object kind;
4. parse the closed schema with duplicate/unknown/missing-field rejection;
5. reconstruct fresh exact nominal nested values;
6. recompute the internal ref from the object and require exact equality with
   the externally expected ref; and
7. return a separate non-caller-constructible `LoadedAuthoringArtifact`.

`LoadedAuthoringArtifact` binds:

- the expected and recomputed exact ref;
- the verified canonical bytes or an immutable verified-byte view;
- the fresh exact authored object;
- a trusted structural `AuthoringOrigin`;
- exact source/audit provenance; and
- exact `ApplicabilityBinding[QualificationEvidenceBundleRef]` for external
  qualification evidence, without copying authority into the top-level
  object; absence/null is invalid and `NOT_APPLICABLE` requires an exact owner
  reason.

`AuthoringOrigin` is a closed nominal union issued only by controlled loader
or registry capabilities. Its exact variants are:

- `FIXTURE(fixture_registration_ref, source_provenance_refs)`, where the
  registration ref is an exact owner-issued fixture-registration ref and the
  provenance tuple is nonempty;
- `DRAFT(draft_authority_ref, source_provenance_refs)`, where the exact owner
  ref identifies the bounded draft authority and the provenance tuple is
  nonempty; or
- `REGISTERED(registration_ref, authority_evidence_refs,
  source_provenance_refs)`, where all three bindings are exact and both tuples
  are nonempty.

The variant tag and every payload field are structural. A missing, unknown,
unloadable, revoked, role-mismatched, or unverified evidence ref yields no
registered origin.

A public constructor from a Boolean, string, mapping, filename, or caller
assertion MUST NOT create these authority-bearing origins. Origin propagates
through the complete loaded dependency graph. A controlled loader emits a
closed `AuthoringGraphOrigin` containing the root ref, the sorted exact
dependency refs, each verified per-artifact origin-evidence ref, the computed
graph-origin tag, and an exact composition-audit ref. The join is fixed:

1. any `FIXTURE` node produces `FIXTURE_DERIVED`;
2. otherwise any `DRAFT`, missing, unknown, unresolved, revoked, or unverified
   node produces `DRAFT_OR_UNRESOLVED`; and
3. `REGISTERED_GRAPH` is possible only when every reachable node is
   `REGISTERED`, every evidence binding verifies, and the controlled registry
   capability issues the composition result.

For B-02A v1, “complete loaded dependency graph” means an exact composition
manifest rather than directed ownership by one authored object. The manifest
contains one distinguished `root_ref` and a sorted, duplicate-free set of all
other required top-level refs. A controlled resolver MUST load every manifest
member by exact ref, MUST require every declared top-level dependency to be a
manifest member, and MUST reject an omitted dependency, an undeclared loaded
node, a cross-Challenge node, or a node outside the root's connected component
when dependency edges are considered undirected. Undirected connectivity is
structural: peer contracts such as training support and an official
SamplingPlan may connect through their shared candidate/physical pins without
either contract acquiring semantic ownership of the other. A caller Boolean,
an unbound extra ref, or root-only reachability cannot establish completeness.
The exact root and complete sorted member set are fingerprint inputs. This
check establishes identity/completeness only; it does not establish scientific
adequacy or qualification.

### 3.4 Exact scientific-authoring graph fingerprint

The v1 fingerprint is computed only from the exact capability-issued
`AuthoringGraphOrigin` after exact-ref loading, manifest completeness,
same-Challenge membership, declared-dependency containment, undirected
connectivity, the closed loaded-graph validator, applicable external-owner
semantic verification, and controlled structural-origin composition have all
passed. It MUST NOT be computed from a caller mapping, incomplete load,
logical identifier, or completeness assertion.

The fingerprint input is the closed canonical record type
`authoring_graph_origin` with exactly `composition_audit_ref`,
`dependency_refs`, `graph_origin`, `origin_evidence_refs`, and `root_ref`.
Dependency and origin-evidence refs use canonical set-like tuples: duplicates
reject and members sort by complete canonical encoded bytes. Record fields sort
by UTF-8 field-name bytes. Every top-level ref retains its exact nominal type,
Challenge key, object kind, logical ID/version, schema version, profile,
digest, and population-role or disclosure-class discriminator where
applicable. Owner refs retain exact kind, scope, identity/version, and digest;
origin-evidence refs use kind `authoring_origin_evidence`, and the audit ref
uses kind `origin_composition_audit`.

The exact digest is:

```text
"sha256:" + lowercase_hex(SHA256(
    b"carbon.scientific-authoring.graph-fingerprint.v1\x00"
    + encode_value(authoring_graph_origin_record)
))
```

`encode_value` is the closed v1 canonical-value encoding without top-level
document framing. The fingerprint binds the distinguished root, complete
duplicate-free dependency set, joined graph-origin tag, complete
origin-evidence set, and composition-audit ref. Challenge identity is embedded
in every top-level ref rather than inferred from ambient state. Changing any
bound ref, nominal discriminator, origin, origin evidence, or audit creates a
different fingerprint. The procedure depends on no Python `repr`, object
identity, insertion order, locale, path, clock, process state, or ambient
environment.

Hashing, copying, renaming, re-registering, superseding, or reconstructing
does not cleanse fixture origin. Neither `DRAFT_OR_UNRESOLVED` nor an absent
composition result can enter A3's LIVE qualification path.

Revocation and supersession are prospective events. An exact immutable
revocation/supersession record may block a new graph composition or future
LIVE use, but MUST NOT rewrite the origin, pins, qualification state, or result
recorded for an earlier evidence event. Historical resolution loads the exact
then-current refs and separately reports any later revocation event; it never
retroactively mutates the historical record.

The loaded result is not the authored contract, a runtime realization, a
qualification decision, or a LIVE record. Separate loads MUST NOT share
caller-mutable nested state.

---

## 4. Prospective schema-local canonical bytes

Carbon currently has schema-local A4, A5, and A7 identity procedures but no
public generic serializer suitable for B-02A. The B-02A implementation SHALL
therefore implement only the following schema-local profile. It SHALL NOT
import or relabel another owner's private encoder.

### 4.1 Profile and document framing

The exact profile identifier is
`carbon_scientific_authoring_canonical_v1`. A complete top-level identity
document is:

```text
ASCII("carbon.scientific-authoring.canonical.v1")
0x00
TEXT(object_kind)
TEXT(schema_version)
RECORD(the complete top-level object as closed sorted field-name/value pairs)
```

The ASCII header bytes above, including the single NUL terminator, are exact.
The object kind supplies domain separation. A digest is exactly
`"sha256:" + lowercase_hex(SHA256(complete_document))` and is validated by
the existing A3 digest grammar. The framed `object_kind` and `schema_version`
MUST exactly equal common record fields 1 and 2; any mismatch rejects.

Auxiliary immutable evidence records defined by this contract use this
separate exact framing so their digest is not self-referential:

```text
ASCII("carbon.scientific-authoring.derived-evidence.v1")
0x00
TEXT(record_type)
TEXT(schema_version)
RECORD(the complete derived record, which contains no content_digest field)
```

Only `CanonicalCaseDisposition`, `CensoringRecord`, and
`RealizedValidEvidenceRecord` use that derived-evidence framing in v1. Each has
a separate exact nominal ref containing `record_type`, `schema_version`, exact
`canonicalization_profile`, and the `TaggedSha256` of the complete framed
bytes. The framing grants no
authoring, evidence, qualification, or LIVE capability.

A canonical document is at most 16,777,216 bytes. Any `TEXT` or `BYTES`
payload is at most 65,535 bytes, any tuple contains at most 65,535 entries,
and nesting depth is at most 64. These are engineering safety bounds proposed
for review, not scientific sample sizes or population limits.

### 4.2 Primitive encodings

Every value starts with one exact one-byte tag:

| Tag | Value | Following bytes |
|---:|---|---|
| `0x00` | null, only inside a closed union payload that explicitly permits it | none |
| `0x01` | exact Boolean false | none |
| `0x02` | exact Boolean true | none |
| `0x03` | `Int64` | exactly 8-byte big-endian two's-complement integer |
| `0x04` | `UInt64` | exactly 8-byte big-endian unsigned integer |
| `0x05` | `FiniteFloat64` | exactly 8-byte big-endian IEEE-754 binary64; non-finite rejects; every zero encodes as positive-zero bits |
| `0x06` | `TEXT` | 4-byte big-endian byte length followed by strict UTF-8 bytes |
| `0x07` | `BYTES` | 4-byte big-endian length followed by exact bytes |
| `0x08` | ordered tuple | 4-byte big-endian item count followed by each canonical value in semantic order |
| `0x09` | closed record | `TEXT(record_type)`, 4-byte field count, then every `TEXT(field_name)` and canonical value pair sorted by the field name's strict UTF-8 bytes |
| `0x0A` | closed tagged union | `TEXT(exact_union_tag)` followed by the one schema-required canonical payload |
| `0x0B` | exact nominal ref | `TEXT(ref_type)` followed by its closed sorted-field `RECORD` |

`TEXT` uses exact Unicode scalar values that are already NFC. Encoding or
decoding an unpaired surrogate, invalid UTF-8, NUL, C0/C1 control, or non-NFC
text rejects. The implementation MUST NOT silently normalize Unicode.
Identifier and version fields additionally pass the stricter existing A3
ASCII validators.

Logical schema values map to primitives exactly as follows:

- `CanonicalId`, `VersionToken`, `TaggedSha256`, `Utf8Text`, and every closed
  ASCII literal encode as `TEXT` after their exact validators succeed;
- `ChallengeKey` encodes as `RECORD` with fixed ASCII record type
  `challenge_key` and exactly the fields `challenge_id: CanonicalId` and
  `version: VersionToken`;
- an exact nominal top-level or owner ref encodes with tag `0x0B`, its fixed
  ASCII schema `ref_type`, and its closed record; and
- no enum ordinal, Python enum/class/module name, display name, or implicit
  default participates in canonical bytes.

Boolean never enters integer or float encoding. Integer and float are never
coerced. Positive and negative integers, integer and float, Boolean and
integer, and distinct Unicode sequences are distinct. Negative zero is the
only numerical normalization in v1 and is explicitly canonical positive zero.

### 4.3 Records, unions, and collections

Every record type and field name is a fixed ASCII schema literal, never a
Python class/module name or caller string. Every field listed in a closed
record is present exactly once. Field names are identity-bearing `TEXT`, must
already satisfy the current A3 canonical-identifier grammar, and are sorted by
their strict UTF-8 bytes before encoding. The encoder emits the field count,
then each `TEXT(field_name)`/value pair. Optionality is represented by an explicit tagged
`BOUND`/`NOT_APPLICABLE` union, never field absence or null. Duplicate field
names, non-increasing encoded field-name order, unknown record types/fields,
unknown union tags, extra values, missing values, or an incorrect field count
reject. The closed schema registry in §4.5 fixes every subordinate record
type, field set, union tag, and payload.

Ordered tuples preserve order. A field declared set-like SHALL reject
duplicate semantic members, sort members by their complete canonical bytes,
and then encode the sorted tuple. Authored B-02A schemas SHALL NOT use an
unbounded or insertion-ordered mapping. When a subordinate keyed collection
is required, it is a tuple of closed entry records with unique canonical IDs;
set-like entry collections sort by canonical entry bytes.

### 4.4 Determinism and versioning

Canonical bytes MUST NOT depend on Python `repr`, class/module names, object
identity, subclass behavior, mapping insertion order, locale, timezone,
filesystem path, source URI, current time, current checkout, process ID,
thread schedule, hash-randomization seed, ambient environment variable,
installed-package location, host endianness, or network state.

The profile is prospective and versioned. Changing a tag, bound, text policy,
field-name ordering, field meaning, numerical representation, or domain header
requires a new profile and object version. Historical bytes and digests remain
retrievable and are never silently re-encoded under a newer profile.

### 4.5 Closed schema and union registry

This registry is normative for v1. The exact top-level record field sets are
the common envelope in §3.1 plus the object-specific table for that type in
§5.2, §5.3, §6.2, §7, §8, or §9.1. Their fixed ASCII `record_type` is their
`object_kind` literal. Top-level refs use the corresponding
`<object_kind>_ref` as both fixed `ref_type` and record type, with the exact
fields in §3.2 and only the stated role/disclosure extension. No other
top-level type, field, or extension is admitted.

The notation `record_type(field: Type, ...)` below declares the complete field
set; presentation order is not encoding order. `SET[T]` means a set-like tuple
sorted by complete member canonical bytes. `SEQ[T]` means an ordered tuple.
`EMPTY` is the closed record `empty_payload` with zero fields. Zero-payload
union variants always encode their tag followed by that `EMPTY` record; they
never use null or omit the payload.

Common exact records and refs are:

- `challenge_key(challenge_id: CanonicalId, version: VersionToken)`;
- each nominal `PinnedOwnerRef<K>` uses fixed kind-specific `ref_type` K and
  `owner_ref(content_digest: TaggedSha256, object_id: CanonicalId,
  object_version: VersionToken, ref_kind: literal K, scope_binding:
  OwnerScopeBinding)`; fields that name an owner-ref kind admit only that
  nominal K even when layouts match;
- `PinnedOwnerRef<evidence_binding_authority>` is the exact authority identity
  used only by the non-serializable B-04/history consumption adapter for a
  `case_evidence_binding`; it is an external registry pin and does not itself
  confer reference qualification, scientific qualification, or LIVE status;
- `not_applicable_payload(reason_ref:
  PinnedOwnerRef<applicability_reason>)`;
- `authoring_graph_origin(composition_audit_ref:
  PinnedOwnerRef<origin_composition_audit>, dependency_refs:
  SET[TopLevelObjectRef], graph_origin: GraphOriginLiteral,
  origin_evidence_refs: SET[PinnedOwnerRef<authoring_origin_evidence>],
  root_ref: TopLevelObjectRef)`; and
- `derived_record_ref(canonicalization_profile: literal
  carbon_scientific_authoring_derived_evidence_v1, content_digest:
  TaggedSha256, record_type: literal, schema_version: VersionToken)`,
  instantiated as three distinct final nominal
  ref types only for the derived records named in §4.1.

Physical/candidate subordinate records are:

- `axis_contract(axis_id: CanonicalId, extent: AxisExtent,
  semantic_role_ref: PinnedOwnerRef<semantic_clause>, unit_ref:
  PinnedOwnerRef<unit>)`;
- `value_field_contract(admissibility_refs:
  SET[PinnedOwnerRef<semantic_clause>], field_id: CanonicalId,
  geometry_binding: ApplicabilityBinding[PinnedOwnerRef<geometry_domain>],
  nonfinite_policy: literal REJECT, precision_contract: SET[PrecisionLiteral],
  presence: Presence, representation_ref: PinnedOwnerRef<representation>,
  semantic_role_ref: PinnedOwnerRef<semantic_clause>, shape_contract:
  SEQ[axis_contract], unit_ref: PinnedOwnerRef<unit>)`;
- `assumption_clause(applicability: ApplicabilityBinding[
  PinnedOwnerRef<applicability>], assumption_id: CanonicalId, authority_ref:
  PinnedOwnerRef<scientific_authority>, semantic_ref:
  PinnedOwnerRef<semantic_clause>)`;
- `boundary_region_clause(applicability: ApplicabilityBinding[
  PinnedOwnerRef<applicability>], causal_input_binding:
  ApplicabilityBinding[CanonicalId], condition_semantic_ref:
  PinnedOwnerRef<semantic_clause>, geometry_region_ref:
  PinnedOwnerRef<geometry_region>, region_clause_id: CanonicalId, unit_ref:
  PinnedOwnerRef<unit>)` and
  `boundary_condition_contract(clauses: SEQ[boundary_region_clause])`;
- `initial_state_clause(applicability: ApplicabilityBinding[
  PinnedOwnerRef<applicability>], causal_input_binding:
  ApplicabilityBinding[CanonicalId], geometry_domain_ref:
  PinnedOwnerRef<geometry_domain>, state_clause_id: CanonicalId,
  state_semantic_ref: PinnedOwnerRef<semantic_clause>, time_origin_ref:
  PinnedOwnerRef<semantic_clause>)` and
  `initial_condition_contract(clauses: SEQ[initial_state_clause])`;
- `time_contract(endpoint_inclusion_semantic_ref:
  PinnedOwnerRef<semantic_clause>, horizon_binding:
  ApplicabilityBinding[PinnedOwnerRef<semantic_clause>], mode: TimeMode,
  time_coordinate_binding: ApplicabilityBinding[value_field_contract],
  time_unit_ref: PinnedOwnerRef<unit>)`;
- `candidate_input_binding(candidate_field_id: CanonicalId,
  physical_field_id: CanonicalId, relation: CandidateInputRelation)`;
- `candidate_output_binding(candidate_field_id: CanonicalId,
  physical_quantity_id: CanonicalId, relation: CandidateOutputRelation,
  semantic_equivalence_ref: PinnedOwnerRef<semantic_equivalence>)`;
- `condition_input_binding(candidate_field_id: CanonicalId,
  condition_clause_id: CanonicalId, relation: CandidateInputRelation)`; and
- `time_horizon_binding(candidate_field_ids: SEQ[CanonicalId],
  endpoint_equivalence_ref: PinnedOwnerRef<semantic_equivalence>,
  horizon_equivalence_ref: PinnedOwnerRef<semantic_equivalence>,
  time_coordinate_equivalence_ref: PinnedOwnerRef<semantic_equivalence>)`.

Population/support subordinate records are:

- `support_contract(boundary_semantics_ref:
  PinnedOwnerRef<support_boundary>, failure_outcome: literal REJECT,
  membership_decision_ref: PinnedOwnerRef<membership_decision>,
  membership_rule_ref: PinnedOwnerRef<membership_rule>,
  physical_support_ref: PinnedOwnerRef<physical_support>,
  representation_support_ref: PinnedOwnerRef<representation_support>)`;
- `weighting_payload(estimand_scope_ref: PinnedOwnerRef<estimand_scope>,
  normalization_semantics_ref: PinnedOwnerRef<weight_normalization>,
  proposal_population_binding:
  ApplicabilityBinding[InstanceDistributionContractRef], target_population_ref:
  InstanceDistributionContractRef, weighting_role: WeightingRole,
  weighting_rule_ref: PinnedOwnerRef<weighting_rule>)`;
- `downstream_population_consumer(consumer_contract_ref:
  PinnedOwnerRef<downstream_population_consumer_contract>, owner:
  DownstreamPopulationOwner)`;
- `stratum_contract(applicability_ref: PinnedOwnerRef<applicability>,
  hierarchy_binding: ApplicabilityBinding[CanonicalId], membership_rule_ref:
  PinnedOwnerRef<membership_rule>, stratum_id: CanonicalId)`;
- `stratification_contract(assignment_rule_ref:
  PinnedOwnerRef<stratum_assignment>, basis_population_role: PopulationRole,
  disclosure_contract:
  disclosure_contract, hierarchy_semantics_ref:
  PinnedOwnerRef<stratum_hierarchy>, relation: StratificationRelation,
  strata: SET[stratum_contract], stratification_id: CanonicalId,
  unassigned_member_rule_ref: PinnedOwnerRef<stratum_unassigned_rule>)`;
- `exclusion_contract(applicable_claim_ref: PinnedOwnerRef<claim_scope>,
  audit_semantics_ref: PinnedOwnerRef<audit_semantics>, exclusion_id:
  CanonicalId, membership_rule_ref: PinnedOwnerRef<membership_rule>,
  scientific_authority_ref: PinnedOwnerRef<scientific_authority>)`;
- `disclosure_contract(aggregation_policy_ref:
  PinnedOwnerRef<aggregation_policy>, internal_field_ids: SET[CanonicalId],
  protected_field_ids: SET[CanonicalId], public_field_ids: SET[CanonicalId],
  release_policy_ref: PinnedOwnerRef<release_policy>)`;
- `source_material_binding(membership_proof_ref:
  PinnedOwnerRef<membership_proof>, permitted_use_ref:
  PinnedOwnerRef<permitted_use>, provenance_ref: PinnedOwnerRef<provenance>,
  rights_ref: PinnedOwnerRef<rights_profile>, source_material_ref:
  PinnedOwnerRef<source_material>, source_role_ref:
  PinnedOwnerRef<source_material_role>)`; and
- `training_membership_contract(admission_rule_ref:
  PinnedOwnerRef<membership_rule>, failure_outcome: literal REJECT,
  physical_support_ref: PinnedOwnerRef<physical_support>,
  representation_support_ref: PinnedOwnerRef<representation_support>)`.

Sampling subordinate records are:

- `stratum_allocation(allocation: Allocation, primary_stratum_id: CanonicalId,
  selection_stratum_binding: ApplicabilityBinding[CanonicalId])`;
- `stratified_allocation_contract(allocation_total_semantics_ref:
  PinnedOwnerRef<allocation_total_semantics>, allocations:
  SET[stratum_allocation], apportionment_rule_ref:
  PinnedOwnerRef<apportionment_rule>, overlap_accounting_ref:
  PinnedOwnerRef<overlap_accounting>, primary_population_ref:
  InstanceDistributionContractRef, primary_stratification_id: CanonicalId,
  selection_population_ref: InstanceDistributionContractRef,
  selection_stratification_id: CanonicalId, stratum_mapping_ref:
  PinnedOwnerRef<stratum_mapping>, tie_rule_ref: PinnedOwnerRef<tie_rule>)`;
- `duplicate_policy(near_duplicate_rule_ref:
  PinnedOwnerRef<duplicate_rule>, physical_duplicate_rule_ref:
  PinnedOwnerRef<duplicate_rule>, repeated_observation_rule_ref:
  PinnedOwnerRef<duplicate_rule>, replacement_duplicate_rule_ref:
  PinnedOwnerRef<duplicate_rule>, representation_duplicate_rule_ref:
  PinnedOwnerRef<duplicate_rule>)`;
- `registered_replacement_payload(accounting_rule_ref:
  PinnedOwnerRef<replacement_accounting>, denominator_effect_ref:
  PinnedOwnerRef<denominator_effect>, maximum_attempt_rule_ref:
  PinnedOwnerRef<maximum_attempt_rule>, policy_ref:
  PinnedOwnerRef<replacement_policy>, triggers: SET[ReplacementTrigger],
  replacement_selection_law_ref: PinnedOwnerRef<replacement_selection_law>,
  stratum_treatment_ref: PinnedOwnerRef<replacement_stratum_treatment>,
  weight_effect_ref: PinnedOwnerRef<weight_effect>)`;
- `finite_evidence_design(base_evidence_requirement_ref:
  PinnedOwnerRef<base_evidence_requirement>, base_intended_count:
  PositiveUInt64, budget_binding:
  ApplicabilityBinding[PinnedOwnerRef<evidence_budget>], count_unit_ref:
  PinnedOwnerRef<sampling_unit>, design_mode: FiniteDesignMode,
  extension_ceiling_binding: ApplicabilityBinding[
  PinnedOwnerRef<extension_ceiling>], heuristic_stop_outcome:
  literal EVIDENCE_DEFERRED, insufficiency_reason:
  literal INSUFFICIENT_EVIDENCE, insufficiency_state:
  literal INDETERMINATE, plan_change_rule:
  literal NEW_VERSION_REQUIRED)`; and
- `prospective_stopping_extension_policy(candidate_outcome_access_binding:
  CandidateOutcomeAccessBinding, coverage_qualification_binding:
  ApplicabilityBinding[PinnedOwnerRef<coverage_qualification>],
  extension_rule_binding:
  ApplicabilityBinding[PinnedOwnerRef<extension_rule>], interim_look_binding:
  ApplicabilityBinding[PinnedOwnerRef<interim_look_rule>],
  modification_authority_ref: PinnedOwnerRef<modification_authority>,
  sequential_allocation_binding:
  ApplicabilityBinding[PinnedOwnerRef<sequential_allocation_rule>],
  stopping_rule_ref: PinnedOwnerRef<stopping_rule>)`.

Case/evidence subordinate records are:

- `related_population_binding(population_ref:
  InstanceDistributionContractRef, relationship_ref:
  PinnedOwnerRef<population_relationship>)`;
- `generated_case_source(generation_event_ref:
  PinnedOwnerRef<generation_event>, generator_ref: PinnedOwnerRef<generator>)`,
  `observed_case_source(observation_source_ref:
  PinnedOwnerRef<observation_source>)`, `experimental_case_source(
  experiment_source_ref: PinnedOwnerRef<experiment_source>)`,
  `industrial_case_source(industrial_source_ref:
  PinnedOwnerRef<industrial_source>)`, `analytic_case_source(
  analytic_construction_ref: PinnedOwnerRef<analytic_construction>)`, and
  `mms_case_source(verification_campaign_ref:
  PinnedOwnerRef<evidence_campaign>, verification_construction_ref:
  PinnedOwnerRef<verification_construction>)`;
- `public_case_fact_binding(fact_kind: PublicCaseFactKind,
  public_value_ref: PinnedOwnerRef<public_case_fact>)`;
- `protected_case_identity_projection(audit_evidence_refs:
  SET[PinnedOwnerRef<audit_evidence>], case_ref: CanonicalChallengeCaseRef,
  intended_slot_ref: PinnedOwnerRef<protected_intended_slot>,
  issuance_ref: PinnedOwnerRef<projection_issuance>, payload_ref:
  PinnedOwnerRef<protected_case_payload>, realized_stratum_binding:
  ApplicabilityBinding[CanonicalId], replacement_linkage:
  ApplicabilityBinding[PinnedOwnerRef<protected_replacement_lineage>],
  schema_version: VersionToken)`;
- `internal_case_identity_projection(case_ref: CanonicalChallengeCaseRef,
  evidence_campaign_binding: ApplicabilityBinding[
  PinnedOwnerRef<evidence_campaign>], issuance_ref:
  PinnedOwnerRef<projection_issuance>, primary_population_ref:
  InstanceDistributionContractRef, sampling_plan_binding:
  ApplicabilityBinding[SamplingPlanRef], schema_version: VersionToken,
  service_scope_ref: PinnedOwnerRef<internal_service_scope>)`;
- `public_case_identity_projection(challenge_key: ChallengeKey,
  disclosure_policy_ref: PinnedOwnerRef<disclosure_policy>, issuance_ref:
  PinnedOwnerRef<projection_issuance>, opaque_public_handle:
  PinnedOwnerRef<opaque_public_case_handle>, public_fact_bindings:
  SET[public_case_fact_binding], schema_version: VersionToken)`; and
- `case_evidence_binding(applicability_refs:
  SET[PinnedOwnerRef<applicability>], authoritative_case_ref:
  CanonicalChallengeCaseRef, claim_scope_ref: PinnedOwnerRef<claim_scope>,
  disclosure_contract: disclosure_contract,
  downstream_use_restrictions: SET[PinnedOwnerRef<restriction>],
  evidence_artifact_ref: PinnedOwnerRef<evidence_artifact>,
  evidence_campaign_ref: PinnedOwnerRef<evidence_campaign>, evidence_role:
  EvidenceRole, policy_qualification_binding: ApplicabilityBinding[
  PinnedOwnerRef<reference_qualification_policy>], provenance_refs:
  SET[PinnedOwnerRef<provenance>], public_projection_binding:
  ApplicabilityBinding[public_case_identity_projection],
  query_observation_provenance:
  SET[PinnedOwnerRef<query_observation_provenance>], role_population_ref:
  InstanceDistributionContractRef)`.

Derived-record and state/provenance payload schemas are:

- `evidence_scope_binding(evidence_campaign_binding:
  ApplicabilityBinding[PinnedOwnerRef<evidence_campaign>],
  intended_estimand_or_reporting_ref:
  PinnedOwnerRef<intended_estimand_or_reporting>,
  measurement_applicability_binding:
  ApplicabilityBinding[PinnedOwnerRef<measurement_applicability>],
  observation_population_binding:
  ApplicabilityBinding[InstanceDistributionContractRef],
  query_population_binding:
  ApplicabilityBinding[InstanceDistributionContractRef])`;
- `valid_case_payload(applicability_evidence_ref:
  PinnedOwnerRef<applicability_evidence>, membership_evidence_ref:
  PinnedOwnerRef<membership_evidence>)`;
- `excluded_case_payload(assessment_ref:
  PinnedOwnerRef<exclusion_assessment>, exclusion_contract_ref:
  PinnedOwnerRef<exclusion_contract>, inclusion_probability_accounting_ref:
  PinnedOwnerRef<inclusion_probability_accounting>,
  prospective_screening_design_ref: PinnedOwnerRef<screening_design>)`;
- `generation_failure_payload(accounting_ref:
  PinnedOwnerRef<generation_failure_accounting>,
  distribution_conformance_ref:
  PinnedOwnerRef<distribution_conformance>, failure_evidence_ref:
  PinnedOwnerRef<generation_failure>, source_ref: PinnedOwnerRef<case_source>)`;
- `replacement_decision(accounting_evidence_ref:
  PinnedOwnerRef<replacement_accounting>, decision: ReplacementDecisionKind,
  lineage_binding:
  ApplicabilityBinding[PinnedOwnerRef<protected_replacement_lineage>],
  policy_binding: ReplacementPolicyBinding, sampling_plan_ref:
  SamplingPlanRef, trigger_binding: ApplicabilityBinding[ReplacementTrigger])`;
- `fixture_origin_payload(fixture_registration_ref:
  PinnedOwnerRef<fixture_registration>, source_provenance_refs:
  SET[PinnedOwnerRef<provenance>])`, `draft_origin_payload(
  draft_authority_ref: PinnedOwnerRef<draft_authority>,
  source_provenance_refs: SET[PinnedOwnerRef<provenance>])`, and
  `registered_origin_payload(authority_evidence_refs:
  SET[PinnedOwnerRef<authority_evidence>], registration_ref:
  PinnedOwnerRef<authoring_registration>, source_provenance_refs:
  SET[PinnedOwnerRef<provenance>])`;
- `canonical_case_disposition(actor_policy_authority_ref:
  PinnedOwnerRef<policy_authority>, attempt_commitment_binding:
  ApplicabilityBinding[PinnedOwnerRef<protected_attempt_commitment>],
  audit_evidence_refs: SET[PinnedOwnerRef<audit_evidence>],
  canonicalization_profile: literal
  carbon_scientific_authoring_derived_evidence_v1, case_ref_binding:
  ApplicabilityBinding[CanonicalChallengeCaseRef], case_state: CaseState,
  disclosure_contract: disclosure_contract, downstream_use_restrictions:
  SET[PinnedOwnerRef<restriction>], evidence_scope: evidence_scope_binding,
  intended_evidence_unit_ref: PinnedOwnerRef<protected_intended_evidence_unit>,
  primary_population_ref: InstanceDistributionContractRef,
  replacement_decision: replacement_decision, sampling_plan_ref:
  SamplingPlanRef, schema_version: VersionToken, state_payload:
  CaseStatePayload)`;
- `censoring_record(accounting_binding:
  PinnedOwnerRef<censoring_accounting>, actor_authority_ref:
  PinnedOwnerRef<censoring_authority>, audit_evidence_refs:
  SET[PinnedOwnerRef<audit_evidence>], canonicalization_profile: literal
  carbon_scientific_authoring_derived_evidence_v1, censoring_reason:
  CensoringReason, downstream_use_restrictions:
  SET[PinnedOwnerRef<restriction>], evidence_campaign_binding:
  ApplicabilityBinding[PinnedOwnerRef<evidence_campaign>], evidence_scope:
  evidence_scope_binding,
  intended_evidence_unit_ref: PinnedOwnerRef<protected_intended_evidence_unit>,
  missingness_adjustment_binding:
  ApplicabilityBinding[PinnedOwnerRef<missingness_adjustment>], population_ref:
  InstanceDistributionContractRef, query_observation_provenance:
  SET[PinnedOwnerRef<query_observation_provenance>], replacement_decision:
  replacement_decision, sampling_plan_ref:
  SamplingPlanRef, schema_version: VersionToken, trigger_failure_binding:
  CensoringTrigger)`;
- `realized_valid_evidence_record(accounting_evidence_ref:
  PinnedOwnerRef<realized_evidence_accounting>, canonicalization_profile:
  literal carbon_scientific_authoring_derived_evidence_v1, challenge_key:
  ChallengeKey, censoring_policy_ref: PinnedOwnerRef<censoring_policy>,
  complete_unit_manifest_ref: PinnedOwnerRef<protected_unit_manifest>,
  construction_audit_refs: SET[PinnedOwnerRef<audit_evidence>],
  construction_authority_ref: PinnedOwnerRef<accounting_authority>,
  denominator_policy_ref: PinnedOwnerRef<denominator_policy>,
  disclosure_contract: disclosure_contract, disposition_refs:
  SET[CanonicalCaseDispositionRef], distribution_conformance_evidence_ref:
  PinnedOwnerRef<distribution_conformance>, downstream_use_restrictions:
  SET[PinnedOwnerRef<restriction>], evidence_scope: evidence_scope_binding,
  evidence_weight_binding: ApplicabilityBinding[
  InstanceDistributionContractRef], intended_estimand_or_reporting_ref:
  PinnedOwnerRef<intended_estimand_or_reporting>,
  missingness_adjustment_binding: ApplicabilityBinding[
  PinnedOwnerRef<missingness_adjustment>], official_proposal_binding:
  ApplicabilityBinding[InstanceDistributionContractRef],
  primary_population_ref: InstanceDistributionContractRef,
  sampling_plan_ref: SamplingPlanRef, schema_version: VersionToken,
  selection_population_ref: InstanceDistributionContractRef,
  sensitivity_analysis_binding: ApplicabilityBinding[
  PinnedOwnerRef<sensitivity_analysis>], target_population_binding:
  ApplicabilityBinding[InstanceDistributionContractRef])`.

The derived evidence records' complete fields appear in §9.3 and §11. Their
corresponding refs are separate and never embedded in their own digested
record. Any subordinate record or union not in this registry or an exact
top-level field table is unknown and rejects.

The closed unions are:

- `OwnerScopeBinding`: `CHALLENGE(ChallengeKey)` or `GLOBAL(EMPTY)`;
- `TopLevelObjectRef`: `PHYSICAL_SYSTEM(PhysicalSystemSpecRef)`,
  `CANDIDATE_OUTPUT(CandidateOutputContractRef)`,
  `INSTANCE_DISTRIBUTION(InstanceDistributionContractRef)`,
  `SAMPLING_PLAN(SamplingPlanRef)`,
  `TRAINING_SUPPORT(TrainingSupportContractRef)`, or
  `CANONICAL_CASE(CanonicalChallengeCaseRef)`;
- `ApplicabilityBinding[T]`: `BOUND(T)` or
  `NOT_APPLICABLE(not_applicable_payload)`;
- `AllowedConsumer`: `SAMPLING_PLAN(SamplingRole)`,
  `CANONICAL_CASE(CasePopulationUse)`, `CASE_EVIDENCE(EvidenceRole)`,
  `REALIZED_EVIDENCE_DERIVATION(EMPTY)`, or
  `DOWNSTREAM_OWNER(downstream_population_consumer)`;
- `AxisExtent`: `FIXED(PositiveUInt64)`,
  `SYMBOLIC(symbolic_extent(axis_id: CanonicalId, constraint_ref:
  PinnedOwnerRef<axis_constraint>))`, or
  `OWNER_CONSTRAINT(PinnedOwnerRef<axis_constraint>)`;
- `Presence`: `REQUIRED(EMPTY)` or `CONDITIONALLY_REQUIRED(
  PinnedOwnerRef<applicability>)`;
- `TimeMode`: exact literal `STEADY` or `TRANSIENT` encoded as `TEXT`;
- `CandidateInputRelation`: `IDENTITY(EMPTY)`,
  `STRUCTURAL_PACK(PinnedOwnerRef<representation_adapter>)`, or
  `REPRESENTATION_ADAPTER(PinnedOwnerRef<representation_adapter>)`;
- `CandidateOutputRelation`: `IDENTITY(EMPTY)`,
  `STRUCTURAL_UNPACK(PinnedOwnerRef<representation_adapter>)`, or
  `REPRESENTATION_ADAPTER(PinnedOwnerRef<representation_adapter>)`;
- `LawSemantics`: `PROBABILITY_LAW(probability_law_payload(base_measure_ref:
  PinnedOwnerRef<base_measure>, law_ref: PinnedOwnerRef<probability_law>,
  normalization_claim_ref: PinnedOwnerRef<normalization_claim>))`,
  `FINITE_ENUMERATION(finite_enumeration_payload(member_set_ref:
  PinnedOwnerRef<member_set>, multiplicity_semantics_ref:
  PinnedOwnerRef<multiplicity_semantics>))`,
  `SET_MEMBERSHIP_ONLY(PinnedOwnerRef<no_prevalence_claim>)`, or
  `NOT_A_PROBABILITY_LAW(PinnedOwnerRef<non_probability_reason>)`;
- `WeightingSemantics`: `NOT_APPLICABLE(not_applicable_payload)` or
  `WEIGHTING(weighting_payload)`;
- `StratificationRelation`: `DISJOINT_EXHAUSTIVE(EMPTY)`,
  `DISJOINT_NONEXHAUSTIVE(PinnedOwnerRef<nonexhaustive_semantics>)`, or
  `OVERLAP_ALLOWED(PinnedOwnerRef<overlap_semantics>)`;
- `Allocation`: `COUNT(PositiveUInt64)`, `FRACTION(fraction_allocation(
  exact_sum_semantics_ref: PinnedOwnerRef<allocation_sum_semantics>, fraction:
  FiniteFloat64, zero_allocation_binding: ApplicabilityBinding[
  PinnedOwnerRef<zero_allocation_authority>]))`, or
  `OWNER_RULE(PinnedOwnerRef<allocation_rule>)`; a fraction MUST be in closed
  range `[0.0, 1.0]`, and exactly zero is valid only when its zero-allocation
  binding is `BOUND`;
- `ReplacementPolicy`: `NEVER(EMPTY)` or
  `ON_REGISTERED_TRIGGERS(registered_replacement_payload)`;
- `ReplacementTrigger`: `CENSORED(CensoringReason)`,
  `GENERATION_FAILURE(PinnedOwnerRef<replacement_eligible_generation_failure_reason>)`,
  or `EXCLUDED(PinnedOwnerRef<prospective_exclusion_contract>)`; `VALID`,
  candidate failure, and a failure outside the exact evidence/source scope are
  not replacement triggers;
- `CandidateOutcomeAccessBinding`:
  `CANDIDATE_OUTCOMES_PROHIBITED(PinnedOwnerRef<blinding_policy>)` or
  `REGISTERED_ADAPTIVE(candidate_adaptive_access(coverage_qualification_ref:
  PinnedOwnerRef<coverage_qualification>, sequential_rule_ref:
  PinnedOwnerRef<sequential_allocation_rule>))`;
- `PermittedGeneratorBinding`: `PERMITTED(SET[PinnedOwnerRef<generator>])`,
  whose tuple MUST be nonempty, or
  `NONE(PinnedOwnerRef<no_generator_reason>)`;
- `CaseSourceBinding`: `GENERATED(generated_case_source)`,
  `OBSERVED(observed_case_source)`, `EXPERIMENTAL(experimental_case_source)`,
  `INDUSTRIAL(industrial_case_source)`, `ANALYTIC(analytic_case_source)`, or
  `MANUFACTURED_SOLUTION(mms_case_source)`;
- `EvidenceRole`: `ANALYTIC(EMPTY)`, `SEMI_ANALYTIC(EMPTY)`,
  `MANUFACTURED_SOLUTION_VERIFICATION(EMPTY)`, `NUMERICAL(EMPTY)`,
  `EXPERIMENTAL(EMPTY)`, `INDUSTRIAL(EMPTY)`, or
  `REGISTERED_HYBRID(PinnedOwnerRef<hybrid_evidence_role>)`;
- `CaseStatePayload`: `VALID(valid_case_payload)`,
  `CENSORED(CensoringRecordRef)`, `EXCLUDED(excluded_case_payload)`, or
  `GENERATION_FAILURE(generation_failure_payload)`;
- `CensoringTrigger`: `REFERENCE(PinnedOwnerRef<reference_failure>)`,
  `OBSERVATION(PinnedOwnerRef<observation_failure>)`,
  `MEASUREMENT(PinnedOwnerRef<measurement_failure>)`,
  `EXPERIMENT(PinnedOwnerRef<experiment_integrity_event>)`, or
  `EVIDENCE_ACQUISITION_INFRASTRUCTURE(
  infrastructure_censoring_trigger(acquisition_operation_ref:
  PinnedOwnerRef<evidence_acquisition_operation>, infrastructure_failure_ref:
  PinnedOwnerRef<infrastructure_failure>))`; the subtype must match §11;
- `ReplacementDecisionKind`: exact `PROHIBITED`, `PERMITTED`, or
  `REQUIRED_BY_POLICY` encoded as `TEXT`;
- `ReplacementPolicyBinding`: `PLAN_NEVER(EMPTY)` or
  `REGISTERED_POLICY(PinnedOwnerRef<replacement_policy>)`;
- `AuthoringOrigin`: `FIXTURE(fixture_origin_payload)`,
  `DRAFT(draft_origin_payload)`, or
  `REGISTERED(registered_origin_payload)`; and
- `GraphOriginLiteral`: exact `FIXTURE_DERIVED`, `DRAFT_OR_UNRESOLVED`, or
  `REGISTERED_GRAPH` encoded as `TEXT`.

`SamplingRole` is exactly `OFFICIAL_EVALUATION`, `STRESS`, `PRACTICE`,
`PRODUCT_QUALIFICATION`, `VERIFICATION`, or `EVIDENCE_CAMPAIGN`.
`CasePopulationUse` is exactly `PRIMARY`, `RELATED`, `QUERY`, or `OBSERVATION`.
`DownstreamPopulationOwner` is exactly `B_03_GENERATION`, `B_04_REFERENCE`,
`B_05_MEASUREMENT`, `B_06_DOSSIER`, or `B_07R_RESEARCH`; the tag alone confers
no authority without the pinned `consumer_contract_ref`.
`PrecisionLiteral`, `WeightingRole`, `FiniteDesignMode`, `PublicCaseFactKind`,
`PublicPlanFactKind`, `ProtectedPlanFieldKind`, every population/sampling/
censoring/state code, and all fixed policy values are closed ASCII `TEXT`
enums exactly where their owning section lists them.
`FiniteDesignMode` is exactly `FIXED` or `REGISTERED_SEQUENTIAL`. Adding any
enum member, field, record, ref type, or union tag requires a new
schema/profile version and prospective review.

---

## 5. Physical system and candidate causal contract

`PhysicalSystemSpec` defines the physical job. `CandidateOutputContract`
defines the exact candidate-facing causal inputs and required outputs for that
job. The candidate contract points to the physical contract; the physical
contract does not point back, so their content identities remain acyclic.

Neither object proves that the job is scientifically adequate, qualified, or
LIVE. Both require exact claim-scope and operating-envelope owner references.
If those human-owned references or any required physical semantics are
missing, production authoring rejects.

### 5.1 Common subordinate value records

Every causal input and requested output uses an exact `ValueFieldContract`:

| # | Field | Exact type | Rule |
|---:|---|---|---|
| 1 | `field_id` | `CanonicalId` | Unique within its owning tuple. |
| 2 | `semantic_role_ref` | exact semantic-clause owner ref | Defines the physical meaning; a display name is insufficient. |
| 3 | `representation_ref` | exact representation owner ref | Pinned representation grammar; no Python class/path. |
| 4 | `unit_ref` | exact unit owner ref | Required even when an exact dimensionless-unit ref applies. |
| 5 | `shape_contract` | ordered tuple of `AxisContract` | Exact rank and ordered axes; scalar uses the explicit empty tuple. |
| 6 | `precision_contract` | nonempty set-like tuple of closed literals | Literals are `BOOL`, `INT64`, `FLOAT32`, `FLOAT64`, `UTF8`, `BYTES`, or `STRUCTURED_REF`; no implicit widening/coercion. |
| 7 | `geometry_binding` | `ApplicabilityBinding[GeometryDomainRef]` | Exact geometry/domain association or exact reason for inapplicability. |
| 8 | `presence` | closed union | `REQUIRED` or `CONDITIONALLY_REQUIRED(applicability_ref)`; unconstrained optional input is forbidden. |
| 9 | `admissibility_refs` | set-like tuple of exact semantic refs | Nonempty where constraints exist; does not embed unapproved values. |
| 10 | `nonfinite_policy` | exact literal `REJECT` | Candidate and authored numeric values never accept NaN/infinity. |

An `AxisContract` contains unique `axis_id`, exact semantic-role ref, unit ref,
and an extent union:

- `FIXED(PositiveUInt64)`;
- `SYMBOLIC(CanonicalId, constraint_ref)`; or
- `OWNER_CONSTRAINT(constraint_ref)`.

The contract does not choose a grid, resolution, shape, or precision. A real
authored object must contain owner-supplied exact values or refs; a missing
value does not become `SYMBOLIC` automatically.

The following subordinate records are also exact and content-bearing:

- `AssumptionClause`: unique `assumption_id`, normative semantic ref,
  applicability binding, and exact owner-authority ref;
- `BoundaryConditionContract`: ordered boundary-region clauses, each with
  geometry-region ref, condition-semantic ref, causal-input binding, unit ref,
  and applicability;
- `InitialConditionContract`: ordered state-field clauses with semantic ref,
  causal-input binding, geometry/domain ref, time-origin semantic ref, and
  applicability;
- `TimeContract`: exact mode `STEADY` or `TRANSIENT`; time-coordinate value
  contract; horizon semantic ref; endpoint-inclusion semantic ref; and exact
  time unit. A steady job uses explicit `NOT_APPLICABLE` time-coordinate and
  horizon bindings rather than omitted fields; and
- `ClaimScopeRef` and `OperatingEnvelopeRef`: distinct nominal exact owner
  refs. Equal prose or support does not make them interchangeable.

### 5.2 `PhysicalSystemSpec`

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `governing_job_ref` | exact semantic owner ref | Names the physical/engineering job and context. |
| 9 | `governing_law_refs` | nonempty ordered tuple of exact semantic refs | Governing equations/laws and coupled-system semantics; exact order is normative. |
| 10 | `assumptions` | set-like tuple of `AssumptionClause` | Every assumption is explicit, uniquely identified, applicable, and authority-bound. |
| 11 | `causal_inputs` | nonempty ordered tuple of `ValueFieldContract` | Complete physical causal input vocabulary; duplicate IDs reject. |
| 12 | `required_physical_quantities` | nonempty ordered tuple of `ValueFieldContract` | Physical quantities the job requires, independent of a candidate encoding. |
| 13 | `geometry_domain_ref` | exact geometry/domain owner ref | Coordinate system, topology, dimensions, domain, and region semantics. |
| 14 | `boundary_conditions` | exact `BoundaryConditionContract` | Complete boundary semantics and causal bindings. |
| 15 | `initial_conditions` | exact `InitialConditionContract` | Complete initial-state semantics and causal bindings. |
| 16 | `time_contract` | exact `TimeContract` | Steady/transient role, time coordinate, horizon, endpoints, and units. |
| 17 | `operating_envelope_ref` | exact `OperatingEnvelopeRef` | Pinned claimed support/envelope; not inferred from a generator. |
| 18 | `claim_scope_ref` | exact `ClaimScopeRef` | Exact scientific/context-of-use claim; not a marketing label. |
| 19 | `missing_input_policy` | exact literal `REJECT` | No ambient, historical, generator, or example default. |

All physical causal inputs must be present through their declared required or
conditional rules. A conditionally required input may be absent only when its
exact applicability contract proves inapplicability. An unknown, missing,
extra, aliased, renamed, unit-incompatible, shape-incompatible, or silently
defaulted causal input rejects.

Every `BoundaryRegionClause` and `InitialStateClause` whose `applicability` is
`BOUND` MUST carry a `BOUND` `causal_input_binding` naming exactly one declared
`PhysicalSystemSpec.causal_inputs.field_id`. An inapplicable clause MUST NOT
bind a causal input. Within each family, two applicable clauses MUST NOT reuse
the same physical source. A bound boundary clause's `unit_ref` MUST equal its
resolved source `ValueFieldContract.unit_ref`. Every initial-state clause's
`geometry_domain_ref`, including an inapplicable clause, MUST equal the
enclosing `PhysicalSystemSpec.geometry_domain_ref`. Unknown, missing, reused,
inapplicable, unit-substituted, or domain-substituted bindings reject.

The spec contains no generator implementation, solver, reference-selection
policy, measurement, score, seed, official draw, candidate architecture,
qualification state, or LIVE state.

### 5.3 `CandidateOutputContract`

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `physical_system_ref` | exact `PhysicalSystemSpecRef` | Pins the governing physical job. |
| 9 | `candidate_inputs` | nonempty ordered tuple of `ValueFieldContract` | Authoritative candidate-facing input vocabulary; every referenced candidate input ID resolves here exactly once. |
| 10 | `causal_input_bindings` | ordered tuple of `CandidateInputBinding` | Total binding from every declared physical causal input to a declared candidate input. |
| 11 | `required_outputs` | nonempty ordered tuple of `ValueFieldContract` | Exact candidate outputs, semantic quantities, units, shape, representation, and precision. |
| 12 | `physical_output_bindings` | nonempty ordered tuple of `CandidateOutputBinding` | Total, exact binding from every required physical quantity to exactly one candidate output. |
| 13 | `candidate_representation_ref` | exact representation owner ref | Top-level candidate I/O protocol/representation. |
| 14 | `geometry_domain_ref` | exact geometry/domain owner ref | MUST exactly equal `PhysicalSystemSpec.geometry_domain_ref` in v1. |
| 15 | `boundary_input_bindings` | ordered tuple of `ConditionInputBinding` | Shows where every applicable boundary condition enters a declared candidate input. |
| 16 | `initial_input_bindings` | ordered tuple of `ConditionInputBinding` | Shows where every applicable initial condition enters a declared candidate input. |
| 17 | `time_horizon_binding` | exact `TimeHorizonBinding` | Preserves physical time coordinate, horizon, endpoint, and unit semantics through declared candidate input IDs. |
| 18 | `operating_envelope_ref` | exact `OperatingEnvelopeRef` | Must exactly equal the physical spec's ref unless a new physical spec version authorizes a different envelope. |
| 19 | `claim_scope_ref` | exact `ClaimScopeRef` | Must exactly equal the physical spec's claim scope. |
| 20 | `missing_or_extra_policy` | exact literal `REJECT` | Missing, null, duplicate, unknown, or extra causal inputs/outputs reject. |
| 21 | `malformed_output_policy` | exact literal `CANDIDATE_FORMAT_FAILURE` | Shape, unit, representation, precision, and non-finite output violations remain candidate-format failure, not scientific evidence. |

`CandidateInputBinding` contains exact physical `field_id`, exact declared
candidate `field_id`, and a closed relation:

- `IDENTITY`;
- `STRUCTURAL_PACK(adapter_contract_ref)`; or
- `REPRESENTATION_ADAPTER(adapter_contract_ref)`.

An adapter may change encoding only. It MUST NOT change physical reality,
units, causal meaning, geometry, domain, boundary/initial conditions, time,
horizon, or claim scope. Every declared physical causal input appears
exactly once as a source binding; duplicate or missing source IDs reject.

For every causal-input, boundary-input, initial-input, and physical-output
relation, source and target `ValueFieldContract` values MUST be exactly equal
in `semantic_role_ref`, `unit_ref`, `geometry_binding`, `presence`,
`admissibility_refs`, and `nonfinite_policy`. `IDENTITY` additionally requires
exact equality of `representation_ref`, `shape_contract`, and
`precision_contract`. The binding names independently authored source and
target `field_id` values; those IDs need not be equal. Apart from those IDs, a
non-identity input relation may differ only in the three encoding-owned fields
and MUST bind its exact representation-adapter
owner ref. A non-identity output relation may differ only in representation or
shape; `precision_contract` remains exactly equal because an adapter cannot
weaken, strengthen, or reinterpret an output precision claim.

Every `candidate_field_id` in causal, boundary, initial, or time/horizon
bindings MUST resolve to exactly one member of `candidate_inputs`. Every
declared physical causal input, applicable boundary clause, applicable initial clause, and
time/horizon component appears exactly once as a source, and every declared
candidate input is targeted exactly once across those binding families. V1
forbids two source bindings from sharing a candidate input ID; its
`STRUCTURAL_PACK` relation can only pack the internally structured components
of one source `ValueFieldContract`. Cross-source multiplexing requires a new
prospective contract/profile version. Orphan, duplicate-target, cross-family
collision, or unresolved candidate input IDs reject.

Every physical causal input has exactly one `CandidateInputBinding`, regardless
of conditional runtime presence. Every applicable boundary `region_clause_id`
and initial `state_clause_id` has exactly one corresponding
`ConditionInputBinding`; an inapplicable clause has none. The condition binding
resolves the clause's exact physical causal-input source and targets one
declared candidate input. Across causal, boundary, initial, and time/horizon
binding families, every candidate input is targeted exactly once. Duplicate or
cross-family targets, omitted applicable clauses, extra condition bindings, and
unknown source or target IDs reject.

V1 requires exact equality of the candidate and physical geometry/domain refs.
It defines no geometry/domain adapter relation. A later proposal that needs one
must add an identity-bearing field and new version; a prose claim of
equivalence is insufficient.

`CandidateOutputBinding` contains the exact physical quantity `field_id`, the
exact candidate output `field_id`, an exact semantic-equivalence owner ref,
and a closed relation `IDENTITY`, `STRUCTURAL_UNPACK(adapter_contract_ref)`, or
`REPRESENTATION_ADAPTER(adapter_contract_ref)`. Every member of
`PhysicalSystemSpec.required_physical_quantities` appears exactly once as a
source and every member of `CandidateOutputContract.required_outputs` appears
exactly once as a target. Missing, duplicate, substituted, extra, or
unregistered-derived output bindings reject. An adapter may change only
representation/packing; quantity meaning, units, geometry/domain, time and
horizon semantics, precision claims, and claim scope remain equivalent under
the exact owner ref. A scientifically meaningful subset or derived quantity
therefore requires a new ratified physical/candidate contract version rather
than an implicit omission or transformation.

Candidate format conformance does not establish physical correctness,
measurement success, reference adequacy, scientific qualification, or score.
This object contains no B-02B candidate assembly/compiler behavior and no B-05
measurement, tolerance, threshold, evidence weight, or Score Pack field.

#### Exact transient-time SciML owner seam

For a transient pair, `SciMLTimeEquivalenceAuthority` MUST implement the
positional-only operation
`verify_transient_time_equivalence(TransientTimeEquivalenceRequest) ->
TransientTimeEquivalenceVerification`. The exact final request contains only
`physical_system_ref`, `candidate_output_ref`, `physical_time_contract`,
`candidate_time_horizon_binding`, and `candidate_input_contracts`. These are
respectively the exact physical/candidate refs, complete exact physical
`TimeContract`, exact candidate `TimeHorizonBinding`, and complete ordered
candidate-input tuple. The
refs share one exact Challenge key; the physical contract is `TRANSIENT`; each
candidate input is an exact `ValueFieldContract` with a unique ID; and every
time/horizon candidate field resolves in that tuple.

The exact final result has exactly `request` and `component_bindings`; it echoes
the complete request and carries exactly three ordered
`TransientTimeComponentBinding` values: `TIME_COORDINATE`, `HORIZON`, and
`ENDPOINT`. Each binds one distinct candidate field, its exact semantic-role
ref, and the corresponding exact time-coordinate, horizon, or endpoint
equivalence ref from the requested `TimeHorizonBinding`. The three candidate
IDs MUST cover the binding's complete candidate-field set exactly once.
Missing authority, wrong or subclassed result, stale or altered request,
missing/reordered component, repeated/substituted candidate field,
semantic-role mismatch, or equivalence-ref mismatch fails the affected graph
closed. This external SciML result supplies a required engineering composition
decision; it records no physical truth and confers no qualification or LIVE
authority.

### 5.4 Burgers example maturity

A fixed-viscosity Burgers record may later exist only as an explicitly labeled
fixture or as a human-ratified exact physical-system version. The current
MQ-001 recommendation, including `nu = 5e-3`, is not a valid production
default. A physical parameter is represented either as an exact owner-ratified
assumption or as an explicit candidate causal input; a generator, open pull
request, historical range, or example cannot choose between those meanings.

---

## 6. Population semantics and `InstanceDistributionContract`

Carbon distinguishes at minimum:

```text
P(x)  target/workload scope and any law-authorized prevalence claim
Q(x)  official proposal or finite-exam sampling law
w(x)  evidence/score weighting semantics
```

`w(x)` is not necessarily a probability distribution. The
`InstanceDistributionContract` name denotes the closed family of
population-related scientific semantics; its role tag determines whether the
object is a population, proposal law, or weighting contract.

### 6.1 Closed population roles

The exact `population_role` literals are:

- `TARGET_WORKLOAD_P`;
- `OFFICIAL_PROPOSAL_Q`;
- `EVIDENCE_WEIGHT_W`;
- `TRAINING_SUPPORT` is **not** allowed here and belongs only to
  `TrainingSupportContract`;
- `STRESS`;
- `PRACTICE`;
- `PRODUCT_QUALIFICATION`;
- `DEPLOYMENT`;
- `QUERY`;
- `OBSERVATION`;
- `EVIDENCE_CAMPAIGN`.

Later compiler-owned `R_strategy` is not a population role and MUST NOT be
accepted in this enum.

### 6.2 Exact fields

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `physical_system_ref` | exact `PhysicalSystemSpecRef` | Governing physical job. |
| 9 | `candidate_output_ref` | exact `CandidateOutputContractRef` | Candidate causal/output contract to which this role applies. |
| 10 | `population_role` | closed literal from §6.1 | Exact semantics; no caller alias. |
| 11 | `owning_claim_scope_ref` | exact `ClaimScopeRef` | Scientific claim this role owns or supports. |
| 12 | `target_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Required and role-checked for every role derived from or contrasted with `P`; prohibited for `P` itself. |
| 13 | `proposal_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Required for `w` when weighting depends on `Q`; otherwise explicit inapplicability. |
| 14 | `support_contract` | exact `SupportContract` | Membership universe, support constraints, and boundary behavior. |
| 15 | `law_semantics` | closed `LawSemantics` union | Probability/proposal/set semantics; exact owner refs, never sampling-code behavior. |
| 16 | `weighting_semantics` | closed `WeightingSemantics` union | Required only for `EVIDENCE_WEIGHT_W`; explicit inapplicability otherwise. |
| 17 | `stratification_binding` | `ApplicabilityBinding[StratificationContract]` | Named collection-level partition/overlap/hierarchy semantics, or exact reason no stratification applies; actual strata remain owner input. |
| 18 | `applicability_refs` | nonempty set-like tuple of exact applicability refs | Claim/context/query applicability. When no additional applicability condition exists, the tuple contains one exact owner-issued no-additional-applicability ref; empty, omitted, null, or caller text rejects. |
| 19 | `exclusions` | set-like tuple of `ExclusionContract` | Prospective exact exclusions; never post-hoc removal of difficult cases. |
| 20 | `rights_profile_ref` | exact rights-profile owner ref | Owner-issued rights/permissions; not agent-authored legal prose. |
| 21 | `permitted_use_refs` | nonempty set-like tuple of exact permitted-use owner refs | Uses allowed by the exact rights profile; B-02A does not invent a legal/use vocabulary. |
| 22 | `restrictions` | set-like tuple of exact restriction refs | Retention, disclosure, reuse, publication, cross-customer, exclusivity, or other restrictions. |
| 23 | `disclosure_contract` | exact `DisclosureContract` | Public/internal/protected authored fields and aggregation limits. |
| 24 | `allowed_consumers` | nonempty `SET[AllowedConsumer]` | Closed contract-kind/role capabilities from §4.5. An unknown tag, enum value, missing pinned downstream contract, or unlisted consumer rejects. |
| 25 | `population_provenance` | nonempty set-like tuple of exact provenance refs | Source type, selection mechanism, observation period, missingness, uncertainty, maturity, and limitations. |

`SupportContract` contains a content-addressed membership-rule ref, physical
and representation support refs, boundary-inclusion semantics, proof or
decision procedure ref, and explicit failure outcome. A generator version,
parameter range, seed family, storage location, or observed dataset is not a
membership rule unless the exact owner-ratified support contract says so.

`LawSemantics` is exactly one of:

- `PROBABILITY_LAW(base_measure_ref, law_ref,
  normalization_claim_ref)`;
- `FINITE_ENUMERATION(member-set-ref, multiplicity_semantics_ref)`;
- `SET_MEMBERSHIP_ONLY(no_prevalence_claim_ref)`; or
- `NOT_A_PROBABILITY_LAW(reason_ref)`.

`P` may carry an owner-ratified probability law, finite enumeration, or
explicit set-only semantics appropriate to its claim. A set-only P owns only
support/membership: it confers no workload prevalence, expectation, frequency,
or target-risk authority. `Q` used by any executable plan MUST carry a complete
`PROBABILITY_LAW` or `FINITE_ENUMERATION` with exact multiplicity/selection
semantics. Set-only Q cannot execute a plan, define inclusion probabilities,
or become proposal frequency through runtime behavior. `w` requires
`NOT_A_PROBABILITY_LAW` here and an exact `WeightingSemantics` payload. B-02A
chooses none of the actual refs or values.

`WeightingSemantics` is either explicit `NOT_APPLICABLE(reason_ref)` or:

```text
WEIGHTING(
    weighting_role,
    estimand_scope_ref,
    weighting_rule_ref,
    normalization_semantics_ref,
    target_population_ref,
    proposal_population_binding,
)
```

The nested target/proposal refs MUST equal fields 12/13. Sampling frequency,
stratum allocation, retained-case frequency, or empirical prevalence MUST NOT
be used to infer `w`.

`weighting_role` is exactly `DESIGN_INCLUSION_CORRECTION`,
`SCIENTIFIC_EVIDENCE_WEIGHT`, or `REPORTING_WEIGHT`. A B-05 Score Pack may
later bind an exact w under its own authority, but a B-02A weighting-role tag
is not itself a metric, tolerance, threshold, aggregation policy, or score.
Equal weights, unit weights, `P = Q`, or raw averaging are never implicit; if
scientifically intended they require an exact owner-authored w and estimand.

### 6.3 Closed population-role field matrix

The following matrix closes fields 12, 13, 15, and 16. `NA` means an exact
`NOT_APPLICABLE(reason_ref)`, never absence. Where a cell says `BOUND-or-NA`,
the authored claim selects exactly one branch and the exact reason is
identity-bearing.

| role | target binding | proposal binding | allowed `LawSemantics` | `WeightingSemantics` |
|---|---|---|---|---|
| `TARGET_WORKLOAD_P` | `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `OFFICIAL_PROPOSAL_Q` | exact `BOUND(P)` | `NA` | executable probability or finite enumeration; set-only is non-executable and cannot enter a plan | `NA` |
| `EVIDENCE_WEIGHT_W` | exact `BOUND(P)` | exact `BOUND(Q)` when design-dependent, otherwise `NA` under the estimand owner | `NOT_A_PROBABILITY_LAW` | exact `WEIGHTING` |
| `STRESS` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `PRACTICE` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `PRODUCT_QUALIFICATION` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `DEPLOYMENT` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `QUERY` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `OBSERVATION` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |
| `EVIDENCE_CAMPAIGN` | `BOUND(P)` or `NA` | `NA` | probability, finite enumeration, or set-only | `NA` |

No `InstanceDistributionContract` is a post-hoc realized-evidence object.
Every role above is prospectively authored. Section 11 defines a separate,
capability-created `RealizedValidEvidenceRecord` after execution.

### 6.4 Strata, exclusions, applicability, rights, and disclosure

Each `StratumContract` contains a unique canonical stratum ID, exact membership
ref, applicability ref, and parent/hierarchy binding. Collection properties
live only on its enclosing `StratificationContract`, whose exact relation is:

- `DISJOINT_EXHAUSTIVE`;
- `DISJOINT_NONEXHAUSTIVE`; or
- `OVERLAP_ALLOWED` with an exact overlap-semantics ref.

The contract distinguishes a public stratum definition from a protected
realized stratum assignment. A public field or aggregate MUST NOT reveal
protected exam composition. Small-cell suppression, aggregation, and release
rules come from the exact disclosure contract, not ad hoc caller choice.

Each `ExclusionContract` contains `exclusion_id`, `membership_rule_ref`,
`scientific_authority_ref`, `applicable_claim_ref`, and
`audit_semantics_ref`. Its claim ref MUST be an exact `claim_scope` owner ref
and MUST equal the enclosing population's `owning_claim_scope_ref`. A same-label
or differently versioned claim is not interchangeable. Duplicate exact
exclusions and duplicate exclusion IDs reject. An exclusion is prospective,
claim-scoped authoring; it is not censoring, retry, generator failure,
reference failure, candidate failure, or infrastructure failure.

Rights are explicit. Common source, customer relationship, storage, access,
or commercial optimization does not imply ownership or permission. Unknown
rights, provenance, permitted use, or restriction state rejects the affected
real/production binding.

### 6.5 Role invariants

- `P` owns target/workload scope. It owns prevalence only when its exact law
  authorizes prevalence; set-only P owns membership only. `Q` MUST bind exact
  P and gains no prevalence authority.
- `w` MUST bind exact P and MUST bind exact Q whenever design-dependent, as
  closed by §6.3; it is never inferred from sample frequency. An exact
  inapplicability reason is not an implicit P = Q or unit-weight claim.
- Stress, practice, product-qualification, deployment, query, observation, and
  evidence-campaign roles are distinct exact identities even if they overlap.
- A derived `RealizedValidEvidenceRecord` is not an
  `InstanceDistributionContract` and MUST NOT replace or reinterpret intended
  P, Q, w, denominators, or population authority.
- A shared support, PDE name, governing law, parameter range, generator, seed
  family, physical case, representation, query source, storage source, or data
  row does not imply shared population identity, role, claim, prevalence,
  weighting, rights, or authority.
- A role may be referenced only by the exact consumers allowed in field 24;
  the consumer loads and checks the role rather than trusting the ref name.

---

## 7. `TrainingSupportContract` and reserved `R_strategy`

Training support defines what Challenge-owned material a later construction
policy may use. It is not `P`, `Q`, `w`, stress, official evaluation,
deployment, product qualification, query/observation, or a realized evidence
population.

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `physical_system_ref` | exact `PhysicalSystemSpecRef` | Physical job whose training support is bounded. |
| 9 | `candidate_output_ref` | exact `CandidateOutputContractRef` | Candidate causal/output contract. |
| 10 | `membership_contract` | exact support/membership record | Complete admission semantics for training material. |
| 11 | `physical_invariant_refs` | nonempty set-like tuple of exact semantic refs | Physical invariants every admitted member must satisfy. |
| 12 | `representation_invariant_refs` | nonempty set-like tuple of exact semantic refs | Representation fidelity/shape/unit/domain invariants. |
| 13 | `permitted_source_materials` | set-like tuple of `SourceMaterialBinding` | Exact source IDs/versions/digests and provenance requirements. |
| 14 | `permitted_generators` | exact `PermittedGeneratorBinding` | `PERMITTED` with a nonempty set-like tuple of exact generator refs, or `NONE` with an exact owner reason; absence and an unexplained empty tuple reject. |
| 15 | `rights_profile_ref` | exact rights-profile owner ref | Exact data and material rights. |
| 16 | `permitted_use_refs` | nonempty set-like tuple of exact permitted-use owner refs | Construction/training/research uses only as granted; no caller label grants a use. |
| 17 | `restrictions` | set-like tuple of exact restriction refs | Retention, redistribution, publication, pretraining, adaptation, licensing, exclusivity, or other constraints. |
| 18 | `provenance_requirements` | nonempty set-like tuple of exact provenance refs | Required source, selection, processing, and rights evidence. |
| 19 | `disclosure_contract` | exact `DisclosureContract` | Public/internal/protected support facts. |
| 20 | `unknown_or_invalid_policy` | exact literal `REJECT` | Unknown provenance/rights, membership failure, physical failure, or representation failure is not admitted. |

`SourceMaterialBinding` contains distinct source-material ref, exact
source-role owner ref, membership proof ref, provenance ref, rights ref, and permitted-use
binding. Source access or reconstructibility does not imply permission.

Support membership establishes only membership in this exact training
support. It creates no prevalence, proposal, weighting, stress, evaluation,
evidence, qualification, or LIVE claim.

### 7.1 B-02B ownership of `R_strategy`

`R_strategy` is reserved for the exact canonical
`ResolvedTrainingSamplingPolicy` that B-02B's later compiler will materialize,
together with its later exact `TrainingSamplingPolicyRef`. B-02A does not
define, instantiate, compile, or implement either type.

A later `R_strategy`:

- operates only inside one exact Challenge-owned
  `TrainingSupportContractRef` and MUST bind its exact version/digest;
- cannot redefine, substitute for, or claim authority over `P`, `Q`, `w`,
  stress, practice, product qualification, deployment, query/observation,
  evidence campaigns, realized evidence, or official evaluation;
- binds no official entropy, seed, protected case, protected draw, hidden
  stratum realization, or official draw;
- cannot select reference evidence, truth assets, measurements, gates,
  thresholds, scorer controls, qualification criteria, or Score Pack values;
- cannot expand rights, permitted sources, physical support, or
  representation support; and
- gains reproducibility only—not scientific authority—from determinism,
  content addressing, or reconstructibility.

A Strategy field, compiler result, generator argument, or runtime plan that
presents `R_strategy` where any official population/ref is required MUST fail
exact-type and exact-role validation.

---

## 8. `SamplingPlan`

`SamplingPlan` is the prospective finite-evidence design for one exact
sampling role. An `OFFICIAL_EVALUATION` plan binds P and Q. Stress, practice,
product-qualification, verification, and evidence-campaign plans bind their
own exact primary and selection populations instead; they do not acquire P/Q
authority. Every plan keeps evidence weighting separate. No plan defines
target prevalence, reference truth, measurement, score, or statistical
sufficiency after observing results.

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `sampling_role` | closed literal | `OFFICIAL_EVALUATION`, `STRESS`, `PRACTICE`, `PRODUCT_QUALIFICATION`, `VERIFICATION`, or `EVIDENCE_CAMPAIGN`; no alias. |
| 9 | `primary_population_ref` | role-checked `InstanceDistributionContractRef` | Population whose claim the plan directly samples; exact role fixed by §8.1. |
| 10 | `selection_population_ref` | role-checked `InstanceDistributionContractRef` | Exact sampling/proposal law for this plan role; exact role fixed by §8.1. |
| 11 | `target_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact P relation where §8.1 requires or allows it; never inherited authority. |
| 12 | `official_proposal_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact Q only for `OFFICIAL_EVALUATION`; explicit inapplicability otherwise. |
| 13 | `evidence_weight_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact `EVIDENCE_WEIGHT_W` bound to its declared populations, or explicit owner reason for no weighting. |
| 14 | `query_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact `QUERY` role where queries are sampled. |
| 15 | `observation_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact `OBSERVATION` role where observations are sampled. |
| 16 | `evidence_campaign_binding` | `ApplicabilityBinding[EvidenceCampaignRef]` | Required for verification/campaign plans; otherwise explicit binding or inapplicability under §8.1. |
| 17 | `intended_estimand_or_reporting_ref` | exact statistics/B-05 owner ref | Always-bound intended estimand, evidence use, or explicitly non-aggregating reporting contract; B-02A does not define its values. |
| 18 | `finite_evidence_design` | exact `FiniteEvidenceDesign` | Sampling/analysis unit, fixed or registered-sequential mode, base evidence, intended counts/budget, extension ceiling, and fail-closed terminal outcomes. |
| 19 | `full_design_law_ref` | exact statistics owner ref | Defines how the base selection law and every plan control compose into the complete finite-design/inclusion law. |
| 20 | `stratified_allocation_binding` | `ApplicabilityBinding[StratifiedAllocationContract]` | Exact selection/reporting strata, crosswalk, allocation, overlap, apportionment, and tie semantics, or exact reason unstratified. |
| 21 | `query_observation_allocation_binding` | `ApplicabilityBinding[QueryObservationAllocationRef]` | Exact query count, observation count, repeated-observation, and conditional allocation semantics. |
| 22 | `reference_fidelity_allocation_binding` | `ApplicabilityBinding[ReferenceFidelityAllocationRef]` | Exact prospective allocation among reference-fidelity roles; no B-04 qualification policy is defined here. |
| 23 | `replication_dependence_policy_ref` | exact statistics owner ref | Sampling/analysis units, clusters, replication, repeated measures, and dependence accounting. |
| 24 | `uncertainty_resolution_objectives_binding` | `ApplicabilityBinding[StatisticsObjectiveRef]` | Exact prospectively owned uncertainty/resolution objective or reason inapplicable; no threshold selected here. |
| 25 | `tail_resolution_objectives_binding` | `ApplicabilityBinding[StatisticsObjectiveRef]` | Exact tail/rare-regime objective or reason inapplicable. |
| 26 | `minimum_subgroup_objectives_binding` | `ApplicabilityBinding[StatisticsObjectiveRef]` | Exact subgroup/stratum objective or reason inapplicable. |
| 27 | `draw_order_semantics_ref` | exact statistics owner ref | Ordered/unordered, randomization, and allocation execution semantics without seeds/draws. |
| 28 | `stopping_extension_policy` | exact `ProspectiveStoppingExtensionPolicy` | Registered stopping, extension, interim-look, sequential-allocation, modification, and candidate-outcome-blinding rules. |
| 29 | `replacement_policy` | exact closed `ReplacementPolicy` | Eligible state/reason, draw law, lineage, stratum, attempt ceiling, denominator, and weighting consequences. |
| 30 | `duplicate_policy` | exact `DuplicatePolicy` | Physical, representation, near-, repeated-observation, and replacement duplicate definitions/treatment. |
| 31 | `inclusion_policy_ref` | exact statistics/science owner ref | Prospective inclusion and sampling-frame screening rules. |
| 32 | `exclusion_policy_ref` | exact statistics/science owner ref | Must agree with bound populations and full design; no post-hoc easy-case filtering. |
| 33 | `censoring_policy_ref` | exact censoring-policy owner ref | Allowed reasons/triggers, scoped evidence units, authorities, accounting, missingness, replacement, and disclosure. |
| 34 | `public_authored_facts` | set-like tuple of exact `PublicPlanFactKind` | Safe plan fact kinds; never realized draws or protected composition. |
| 35 | `protected_realization_fields` | set-like tuple of exact `ProtectedPlanFieldKind` | Closed protected realization field kinds. |
| 36 | `statistical_qualification_requirements_ref` | exact statistics owner ref | Evidence required later to qualify adequacy; B-02A selects no threshold. |
| 37 | `plan_provenance_refs` | nonempty set-like tuple of exact provenance refs | Scientific/statistical authority, registration, derivation, limitations, and rights provenance. |
| 38 | `insufficient_or_failure_policy` | exact literal `NON_SETTLING_FAIL_CLOSED` | Invalid refs, support gaps, impossible allocation, heuristic stop, exhausted budget/replacement, or insufficient realized evidence do not invent science. |

`PublicPlanFactKind` is exactly `SAMPLING_ROLE`,
`PRIMARY_POPULATION_PUBLIC_REF`, `SELECTION_POPULATION_PUBLIC_REF`,
`INTENDED_ESTIMAND_OR_REPORTING_PUBLIC_REF`, `BASE_INTENDED_COUNT`,
`FINITE_DESIGN_MODE`, `PUBLIC_STATISTICAL_OBJECTIVES`, or
`PUBLIC_POLICY_REFS`. The disclosure contract may release a subset and may
further suppress a value; it cannot add a kind.

`ProtectedPlanFieldKind` is exactly `DRAW_IDENTITY`, `SLOT_IDENTITY`,
`ENTROPY`, `SEED`, `REALIZED_STRATUM`, `DRAW_ORDER`,
`REPLACEMENT_LINEAGE`, or `PROTECTED_COMPOSITION`. A field declared public
cannot carry a value from this enum.

### 8.1 Closed sampling-role binding matrix

Every row below is exact. A ref role outside the row rejects.

| `sampling_role` | `primary_population_ref` | `selection_population_ref` | target binding | official Q binding | campaign binding |
|---|---|---|---|---|---|
| `OFFICIAL_EVALUATION` | exact `TARGET_WORKLOAD_P` | exact `OFFICIAL_PROPOSAL_Q` that binds the same P | `BOUND` to the same P | `BOUND` to the same Q | explicit `BOUND` or owner-ratified `NOT_APPLICABLE` |
| `STRESS` | exact `STRESS` | exact `STRESS` contract with the prospective stress-selection law | `BOUND` to the related P | `NOT_APPLICABLE` | explicit `BOUND` or owner-ratified `NOT_APPLICABLE` |
| `PRACTICE` | exact `PRACTICE` | exact `PRACTICE` contract with the practice-selection law | exact `BOUND(P)` or `NOT_APPLICABLE(reason_ref)` under the practice claim | `NOT_APPLICABLE` | explicit `BOUND` or owner-ratified `NOT_APPLICABLE` |
| `PRODUCT_QUALIFICATION` | exact `PRODUCT_QUALIFICATION` | exact `PRODUCT_QUALIFICATION` contract with its selection law | exact `BOUND(P)` or `NOT_APPLICABLE(reason_ref)` under the product claim | `NOT_APPLICABLE` | required exact `BOUND` |
| `VERIFICATION` | exact `EVIDENCE_CAMPAIGN` verification population | the same or another exact `EVIDENCE_CAMPAIGN` verification-selection contract | `NOT_APPLICABLE`; verification gains no target authority | `NOT_APPLICABLE` | required exact `BOUND` to the verification campaign |
| `EVIDENCE_CAMPAIGN` | exact `EVIDENCE_CAMPAIGN` population | the same or another exact `EVIDENCE_CAMPAIGN` selection contract | exact `BOUND(P)` or `NOT_APPLICABLE(reason_ref)` only as the campaign claim states; no authority transfer | `NOT_APPLICABLE` | required exact `BOUND` |

For every row, the loaded selection contract's support and law semantics must
cover the plan's exact primary role as prospectively authored and must be an
executable probability law or finite enumeration, never set-only. Q is the
base/conditional proposal component; the plan's exact `full_design_law_ref`
plus allocation, query/observation, reference-fidelity, replacement,
duplicate, dependence, and stopping fields define the complete finite design
and inclusion law. Any evidence or weighting consumer MUST bind the exact
`SamplingPlanRef`, not Q or w alone.

The `evidence_weight_binding` is independently `BOUND` only to a w contract
whose allowed consumers, estimand, and population refs exactly admit this plan
and full design. An official-evaluation plan that supports an aggregate
estimand or score requires exact w even when P equals Q or weights are equal.
`NOT_APPLICABLE` is permitted only when the always-bound
`intended_estimand_or_reporting_ref` proves either (a) the use is
non-aggregating or (b) a non-official role-specific reporting/aggregation
contract completely defines the primary population, reporting quantity,
denominator, and any reporting coefficient without claiming P, Q, w, B-05
score, or official-exam authority. This second branch may serve verification,
stress, practice, product, or campaign reporting on its own exact role; it is
not an `EVIDENCE_WEIGHT_W` substitute. No row may infer unit weights or use raw
sample frequency as a coefficient. No non-official row may cast its selection
contract to Q or use Q to acquire official-exam authority.

#### Exact statistics owner seam

`StatisticsDesignAuthority` MUST implement the positional-only operation
`verify_statistics_design(StatisticsDesignVerificationRequest) ->
StatisticsDesignVerification`. The exact final request contains only the exact
fields `sampling_plan_ref`, `sampling_plan`, `primary_population`,
`selection_population`, `target_population`, `official_proposal`, and
`evidence_weight`. The latter three are optional resolved exact populations;
the primary and selection populations are always resolved exactly. The ref
MUST equal `sampling_plan.to_ref()`;
primary/selection refs MUST equal their plan pins; and each optional object is
present if and only if its corresponding plan binding is `BOUND`, with an exact
matching ref. The complete plan transitively binds the estimand/reporting ref,
full-design ref, allocations, stopping, replacement, duplicate, inclusion,
exclusion, censoring, query, observation, campaign, and every other finite-
design control; these are not separately omittable request fields.

The exact final result contains only fields `request` and `authorization`: the
exact reconstructed request and one closed `StatisticsDesignAuthorization`.
It MUST echo the complete request.
When w is bound, only `EXACT_W_ADMITTED` is compatible. An unweighted
`OFFICIAL_EVALUATION` plan admits only
`NO_W_NONAGGREGATING_AUTHORIZED`. An unweighted non-official plan admits
`NO_W_NONAGGREGATING_AUTHORIZED` or
`NO_W_NONOFFICIAL_REPORTING_AUTHORIZED`. Missing authority, wrong/subclassed
result, stale or changed echo, optional-population substitution, or
role-incompatible authorization fails the affected graph closed. The result
does not confer scientific qualification, evidence sufficiency, or LIVE
authority.

`StratifiedAllocationContract` binds exact primary and selection populations,
their named `StratificationContract` IDs, an exact reporting/design stratum
crosswalk, and a set-like tuple of `StratumAllocation`. Each allocation has an
exact primary stratum, exact selection-stratum applicability, and a closed
allocation union:

- `COUNT(PositiveUInt64)`;
- `FRACTION(fraction in [0.0, 1.0], exact_sum_semantics_ref,
  zero_allocation_binding)`; or
- `OWNER_RULE(allocation_rule_ref)`.

Zero fraction requires an exact zero-allocation authority; positive fractions
require explicit total, integer apportionment, rounding, and tie semantics.
Overlap and hierarchy accounting lives at collection level. Production
counts/fractions/rules are mandatory human/statistics inputs. This document
supplies no values.

`ReplacementPolicy` is one of:

- `NEVER(EMPTY)`; or
- `ON_REGISTERED_TRIGGERS(policy_ref, trigger-set,
  replacement-selection-law-ref, stratum-treatment-ref,
  maximum-attempt-rule-ref, accounting-rule-ref, denominator-effect-ref,
  weight-effect-ref)`.

Each trigger is one exact pair: `CENSORED(reason)`,
`GENERATION_FAILURE(typed_reason_ref)`, or prospectively authorized
`EXCLUDED(exclusion_contract_ref)`. An independent state set and reason set
whose cross-product is ambiguous rejects. `VALID`, candidate failure, and a
reference/infrastructure event outside the exact censoring scope cannot trigger
replacement. There is no opaque owner-policy escape hatch; the owner ref and
all mandatory structural fields coexist in the registered payload.

Every derived `ReplacementDecision` binds the exact `SamplingPlanRef`, a
closed `ReplacementPolicyBinding`, exact trigger applicability, protected
lineage applicability, and accounting evidence. Cross-validation is exact:

- plan `NEVER` requires `PLAN_NEVER`, decision `PROHIBITED`, and
  `NOT_APPLICABLE` trigger and lineage;
- plan `ON_REGISTERED_TRIGGERS` requires `REGISTERED_POLICY` whose ref exactly
  equals the inline payload's policy ref;
- `PERMITTED` or `REQUIRED_BY_POLICY` requires a `BOUND` trigger matching the
  exact state/reason/scope and plan trigger set; and
- a claimed executed replacement requires `BOUND` distinct lineage, while an
  unexecuted permitted/requisite attempt uses an exact not-applicable/failure
  reason and accounting evidence.

Any plan/policy/trigger/decision/lineage/accounting mismatch rejects. An
arbitrary owner ref cannot authorize a decision that the exact plan forbids.

`DuplicatePolicy` separately specifies exact physical duplicates,
representation duplicates, near-duplicates, repeat observations, and
replacement-generated duplicates. Registered-trigger replacement additionally
pins eligible state/reason pairs, replacement selection law, distinct lineage,
stratum treatment, attempt ceiling, and denominator/weight effects. An opaque
owner policy cannot omit those fields. Duplicate or replacement handling
cannot silently change P, Q, w, the denominator, or intended count.

`FiniteEvidenceDesign` declares the exact sampling/analysis unit and is either
`FIXED` or `REGISTERED_SEQUENTIAL`. It always carries a positive owner-supplied
base intended count and complete base-evidence requirement. Fixed design makes
extension ceiling/budget inapplicable. Registered sequential design requires
exact maximum budget/extension ceiling and the complete stopping/extension
policy. A heuristic stop yields exact evidence state `EVIDENCE_DEFERRED`;
budget exhaustion or unmet base/coverage requirements yields state
`INDETERMINATE` with reason `INSUFFICIENT_EVIDENCE`. Changing a
count, budget, rule, objective, allocation, or admissible information requires
a new prospective SamplingPlan version. Candidate outcomes cannot drive an
adaptation unless `CandidateOutcomeAccessBinding` is exact
`REGISTERED_ADAPTIVE` and its separately owned, prospectively registered
coverage-qualification and sequential-rule refs verify. Otherwise the plan
MUST carry `CANDIDATE_OUTCOMES_PROHIBITED(blinding_policy_ref)`; no implicit
default is accepted. Fixed mode requires inapplicable budget, extension,
interim-look, sequential-allocation, and coverage-qualification bindings.
Registered-sequential mode requires all of them to be exact and bound.

The mode/candidate-information matrix is closed:

| `design_mode` | outcome-access binding | budget/extension/interim/sequential/coverage bindings | timing rule |
|---|---|---|---|
| `FIXED` | exact `CANDIDATE_OUTCOMES_PROHIBITED` | every binding is exact `NOT_APPLICABLE`; stopping means completion of the fixed base design | no candidate-performance access may alter scheduling, selection, stopping, or evidence state |
| `REGISTERED_SEQUENTIAL` with outcome prohibition | exact `CANDIDATE_OUTCOMES_PROHIBITED` | every binding is exact `BOUND` and admitted by `full_design_law_ref` | only declared non-candidate information may drive the registered rule |
| `REGISTERED_SEQUENTIAL` with adaptive access | exact `REGISTERED_ADAPTIVE` | every binding is exact `BOUND`; the nested coverage and sequential refs MUST exactly equal the policy fields and be admitted by `full_design_law_ref` | candidate-performance access begins only after the complete base-evidence predicate verifies |

Before complete base evidence, forecasts or screening results may affect
scheduling only under an exact non-candidate rule. They can yield
`EVIDENCE_DEFERRED`; they cannot issue a scientific denial, adverse score,
qualification failure, or silent design amendment. Every invalid matrix
branch, nested/outer ref mismatch, or pre-base candidate access rejects.

### 8.2 Intended versus realized evidence

The following counts and identities remain distinct:

```text
intended plan slots
attempted draws
successfully generated canonical cases
applicable/eligible cases
excluded cases
censored cases
realized valid-evidence cases
replacement cases and attempts
```

The authored SamplingPlan contains only prospective rules. It never contains
a realized draw, seed, hidden stratum assignment, exam order, replacement
chain, or protected case identity. Those belong to protected realization and
audit records. Public aggregates follow the disclosure contract and MUST NOT
reveal protected composition through granularity or differencing.

An executable plan cannot exist with missing finite-design values, required
strata/allocation/crosswalks, complete selection law, estimand/reporting use,
dependence/replication policy, query/observation or reference-fidelity
allocation, stopping/extension policy, role-required bindings, censoring
policy, or other mandatory scientific inputs. An objective may be inapplicable
only through an exact identity-bearing reason. A fixture may later exercise
the schema but cannot become official through copying or relabeling.

---

## 9. Canonical physical case and closed disposition model

`CanonicalChallengeCase` is one immutable, content-addressed,
representation-neutral physical-realization record upstream of
candidate/model-family materialization. B-02A prospectively authors its schema;
an actual case record is produced only by a controlled generation,
observation, experimental, industrial, analytic, or MMS realization capability.
It is neither a human-authored scientific contract nor a mutable runtime
object, and its creation grants no qualification. It is not required to be a
tensor, mesh, graph, file, or solver configuration. A representation adapter
may change encoding while preserving exact physical reality and provenance.

Once created, a case is immutable. A later reference, candidate, measurement,
or infrastructure event MUST NOT mutate it. The closed `valid`, `censored`,
`excluded`, and `generation failure` semantics therefore live in a separate
immutable `CanonicalCaseDisposition` bound to the intended plan slot and, when
one exists, the exact case ref.

### 9.1 `CanonicalChallengeCase` exact fields

In addition to common fields 1–7, the exact closed fields are:

| # | Field | Exact type | Responsibility |
|---:|---|---|---|
| 8 | `physical_system_ref` | exact `PhysicalSystemSpecRef` | Governing physical job. |
| 9 | `candidate_output_ref` | exact `CandidateOutputContractRef` | Candidate causal/output view. |
| 10 | `primary_population_ref` | role-checked `InstanceDistributionContractRef` | Exact role under which this case was intended. |
| 11 | `related_population_bindings` | set-like tuple of `RelatedPopulationBinding` | Each role-checked ref carries an exact relationship owner ref; P/Q/stress/practice/query/observation/campaign relationships are never inferred from a shared ref. |
| 12 | `sampling_plan_binding` | `ApplicabilityBinding[SamplingPlanRef]` | Exact finite plan or owner reason for no plan. |
| 13 | `case_source` | exact `CaseSourceBinding` | Closed generated, observed, experimental, industrial, analytic, or manufactured-solution source with exact provenance; no seed or runtime handle. |
| 14 | `case_representation_ref` | exact representation owner ref | Canonical physical representation identity. |
| 15 | `physical_payload_ref` | exact protected payload/artifact ref | Content-addressed physical inputs, geometry, parameters, BC/IC, forcing, and requested query/horizon content. |
| 16 | `query_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact `QUERY` role where applicable. |
| 17 | `observation_population_binding` | `ApplicabilityBinding[InstanceDistributionContractRef]` | Exact `OBSERVATION` role where applicable. |
| 18 | `evidence_campaign_binding` | `ApplicabilityBinding[EvidenceCampaignRef]` | Exact campaign identity when the case is campaign-bound. |
| 19 | `intended_slot_binding` | `ApplicabilityBinding[ProtectedIntendedSlotRef]` | Non-public link to SamplingPlan slot/draw provenance, or exact reason no finite plan applies; contains no raw entropy in this object. |
| 20 | `prospective_censoring_policy_binding` | `ApplicabilityBinding[CensoringPolicyRef]` | Plan-bound policy that would govern later censoring; not an event or outcome. |
| 21 | `applicability_bindings` | set-like tuple of exact applicability refs | Exact claim, measurement-domain, query, and representation applicability. |
| 22 | `disclosure_class` | exact literal `INTERNAL` or `PROTECTED` | Identity-bearing raw-case disclosure class; MUST equal field 8 of the recomputed ref. |
| 23 | `disclosure_contract` | exact `DisclosureContract` | Public/internal/protected identity and field projections. |
| 24 | `case_provenance_refs` | nonempty set-like tuple of exact provenance refs | Physical construction and source provenance, excluding protected entropy itself. |

The exact refs loaded through fields 8–20 must agree on Challenge key,
physical system, candidate contract, role, plan, campaign, and disclosure
class. A logical ID, generator assertion, or caller role string cannot replace
that graph validation.

The primary population and every related population MUST resolve to a
population whose role is not `EVIDENCE_WEIGHT_W`. An `AllowedConsumer` entry
naming `CANONICAL_CASE` cannot override this prohibition. w is an evidence or
reporting coefficient contract bound through the exact SamplingPlan and
statistics seam; it is never a physical-case, source, or related-case
population. Using w as either case population rejects before consumer
authorization is considered.

The immutable case record contains no candidate output, reference result,
measurement, score, gate, qualification state, or disposition event. Its
protected intended-slot and payload bindings are not public identity.

### 9.2 Exact identity projections

The B-02A implementation SHALL provide distinct final nominal projection
types and controlled factories. Each is a closed versioned record:

| Projection | Exact fields |
|---|---|
| `ProtectedCaseIdentityProjection` | `schema_version`, raw exact `case_ref`, protected `payload_ref`, protected `intended_slot_ref`, `realized_stratum_binding`, `replacement_linkage`, nonempty exact `audit_evidence_refs`, and exact `issuance_ref`. |
| `InternalCaseIdentityProjection` | `schema_version`, raw exact `case_ref`, exact `primary_population_ref`, `sampling_plan_binding`, `evidence_campaign_binding`, `service_scope_ref`, and `issuance_ref`. |
| `PublicCaseIdentityProjection` | `schema_version`, exact `challenge_key`, A4/protocol-issued `opaque_public_handle`, exact `disclosure_policy_ref`, exact `issuance_ref`, and a set-like tuple of `PublicCaseFactBinding`. The policy ref MUST equal the case disclosure contract's exact release-policy ref. |

`PublicCaseFactBinding.fact_kind` is exactly one of
`PHYSICAL_SYSTEM_CONTRACT`, `CANDIDATE_OUTPUT_CONTRACT`,
`PRIMARY_POPULATION_ROLE`, `CASE_REPRESENTATION`, or
`EVIDENCE_CAMPAIGN_APPLICABILITY`, and its value is an exact public-safe owner
ref. The disclosure/issuance policy may release a subset; it cannot add a new
kind. Adding any projection field or fact kind requires a new projection
schema version.

Protected/internal projections MUST NOT imply public/miner accessibility or
qualification. Internal projections MUST NOT contain seed/entropy bytes,
permit public serialization, or allow unrestricted logging. Public projections
MUST NOT contain a raw case digest/ref, reversible draw/slot ID, seed, entropy,
hidden stratum, exam position, replacement chain, protected population
composition, protected generator input, or reconstruction-sensitive
identifier.

The public handle MUST NOT be a truncation, reversible encryption, or direct
hash of the protected case/draw identity unless A4/security separately owns
and qualifies that derivation. B-02A defines only the projection seam. A
caller-supplied audience flag MUST NOT redact a raw object; only an exact
controlled projection factory may produce the public nominal type.

Projection construction MUST use a package-internal `CaseProjectionAuthority`
backed by an explicit `CaseProjectionRegistryAuthority`. The registry operation
`verify_case_projection(*, authority_ref, case_ref, projection)` returns an
exact `CaseProjectionVerificationEcho`. Its request binds the exact
`projection_issuance` authority ref, exact case ref, and exact nominal
protected, internal, or public projection; the projection's `issuance_ref`
MUST equal the authority ref. The echo contains exactly those three fields and
MUST match their nominal types and complete values.

A Boolean, raw callback, mapping, tuple, subclass, different authority, case,
projection kind, or one-field-modified projection does not authorize issuance.
Public, internal, and protected factories first enforce their local case,
disclosure, and payload bindings and then require this exact pairing echo. A
raw callable cannot serve as the registry authority, and the package-internal
adapter is not a public authority-minting API. This trusted in-process seam is
not a signature, credential, durable receipt, authentication mechanism,
scientific qualification, security acceptance, or LIVE authority; the A4 or
protocol owner remains responsible for its protected, durable,
revocation-aware issuance record.

The raw content-addressed `CanonicalChallengeCaseRef` is therefore internal or
protected. Content addressing does not imply public disclosure.

### 9.3 `CanonicalCaseDisposition`

The disposition is an immutable, evidence-use-scoped loader/runtime record,
not one of the six top-level identity objects and not a mutable property of the physical
case. Its fixed record type is `canonical_case_disposition`; its exact closed
fields are:

| # | Field | Exact type and rule |
|---:|---|---|
| 1 | `schema_version` | exact `VersionToken` for this derived record. |
| 2 | `canonicalization_profile` | exact literal `carbon_scientific_authoring_derived_evidence_v1`. |
| 3 | `intended_evidence_unit_ref` | exact protected ref to plan slot plus campaign/query/observation/measurement-or-evidence-use scope. |
| 4 | `sampling_plan_ref` | exact `SamplingPlanRef`. |
| 5 | `primary_population_ref` | exact role-checked population ref. |
| 6 | `evidence_scope` | exact `EvidenceScopeBinding` containing campaign, query, observation, intended estimand/reporting, and measurement/applicability refs. |
| 7 | `case_state` | exact `VALID`, `CENSORED`, `EXCLUDED`, or `GENERATION_FAILURE`. |
| 8 | `case_ref_binding` | `ApplicabilityBinding[CanonicalChallengeCaseRef]` with state-checked shape. |
| 9 | `attempt_commitment_binding` | `ApplicabilityBinding[ProtectedAttemptCommitmentRef]` with state-checked shape. |
| 10 | `state_payload` | exact `CaseStatePayload` union defined below. |
| 11 | `actor_policy_authority_ref` | exact owner ref; no free-text actor. |
| 12 | `replacement_decision` | exact `ReplacementDecision` plus policy binding. |
| 13 | `audit_evidence_refs` | nonempty set-like tuple of exact audit refs. |
| 14 | `downstream_use_restrictions` | nonempty set-like tuple of exact restriction refs. |
| 15 | `disclosure_contract` | exact `DisclosureContract`. |

The record contains no digest field. Its distinct final
`CanonicalCaseDispositionRef` has exactly `record_type`, `schema_version`,
`canonicalization_profile`, and `content_digest` as specified in §4.1.
`EvidenceScopeBinding` prevents a
missing reference or observation for one campaign/measurement/estimand from
globally censoring the physical case or unrelated evidence uses.

Closed states are:

| State | Exact meaning and required shape |
|---|---|
| `VALID` | A usable physical case exists, exact refs load, schema and representation are valid, and the case satisfies the scope's bound membership/applicability contract. Exact case ref and `VALID(valid_case_payload)` are required; attempted-only commitment is inapplicable. This says nothing about candidate success, reference adequacy, qualification, or LIVE. |
| `CENSORED` | A valid case exists but exact downstream reference/observation/evidence for this intended evidence unit is unavailable or unusable under its prospective policy. Exact case ref and `CENSORED(CensoringRecordRef)` are required. The physical case may remain usable in another scope; this unit remains in intended accounting. |
| `EXCLUDED` | A prospective registered exclusion or non-membership rule applies. `EXCLUDED(excluded_case_payload)` binds the exact exclusion and assessment. A post-draw exclusion is permitted only by an exact preregistered sampling-frame/screening design with inclusion-probability, denominator, and weighting accounting; otherwise an out-of-support generated draw is distribution-conformance/generation failure and non-settling. Exactly one of case ref or attempt commitment is applicable according to whether realization preceded assessment. |
| `GENERATION_FAILURE` | No usable canonical physical case was produced for the intended slot because the exact source's scientific/domain construction or distribution-conformance step failed. Case ref is inapplicable; protected attempt commitment and `GENERATION_FAILURE(generation_failure_payload)` are required. It is not candidate failure, reference failure, infrastructure failure, exclusion, or censoring. |

`CaseStatePayload` is closed: `VALID` carries exact membership and
applicability evidence refs; `CENSORED` carries an exact
`CensoringRecordRef`; `EXCLUDED` carries exact exclusion-contract,
assessment, prospective-screening, and inclusion-probability/accounting refs;
and `GENERATION_FAILURE` carries exact source/generator, typed failure,
distribution-conformance, and accounting refs. Every other tag/payload or
state-shape combination rejects.

Malformed authoring, reference/pin failure, generator infrastructure failure,
candidate failure, reference/truth failure, measurement failure, and general
infrastructure failure are separate exact error/result types outside this
four-state enum. They MUST NOT be coerced into a scientific state. A candidate
failure after a valid case does not change the case disposition. A failed
reference cannot become candidate score zero.

---

## 10. Evidence roles and manufactured-solution separation

One canonical physical case may bind evidence from multiple roles without
transferring authority among them. B-02A defines the identity seam only;
B-04 later owns reference/truth policy, adequacy, qualification, uncertainty,
disagreement, applicability, and runner behavior.

### 10.1 `CaseEvidenceBinding`

Each immutable binding contains:

1. authoritative exact internal/protected `CanonicalChallengeCaseRef`;
2. `ApplicabilityBinding[PublicCaseIdentityProjection]` as a derived
   disclosure view only;
3. exact closed `evidence_role`;
4. exact `EvidenceCampaignRef` and version/digest;
5. exact role-checked verification/evidence-population ref;
6. exact evidence artifact ref;
7. exact claim-scope and applicability refs;
8. exact query/observation provenance bindings;
9. exact B-04-owned policy/qualification binding or explicit inapplicability;
10. exact provenance and disclosure contract; and
11. exact downstream-use restrictions.

The public projection never substitutes for authoritative case identity and
cannot be used to join, recompute, or resolve the raw case ref. A public-only
consumer receives the projection through a controlled view; the protected
binding remains in the authoritative internal record.

Closed evidence roles are:

- `ANALYTIC`;
- `SEMI_ANALYTIC`;
- `MANUFACTURED_SOLUTION_VERIFICATION`;
- `NUMERICAL`;
- `EXPERIMENTAL`;
- `INDUSTRIAL`; and
- `REGISTERED_HYBRID(hybrid_role_ref)`.

`REGISTERED_HYBRID` requires a prospectively reviewed exact owner ref. A
free-form label or runtime mixture cannot create a hybrid role.

A serialized `case_evidence_binding` remains an authored claim. Consumption or
registration requires a trusted in-process adapter around a separately owned
B-04/history authority pinned by
`PinnedOwnerRef<evidence_binding_authority>`. The authority returns an exact
immutable echo of the artifact, authoritative case, role, campaign,
role-population, claim, applicability, query/observation provenance,
qualification-policy binding, provenance, disclosure, and use restrictions.
Any one-field substitution rejects. This adapter is not authentication,
signature verification, B-04 qualification policy, or a durable authority
implementation; those remain separately owned.

Qualification state is external to the case and binding. Equal case refs,
physical jobs, equations, representations, generators, or artifacts do not
transfer authority between evidence roles.

### 10.2 Manufactured solutions and verification campaigns

Every MMS or other implementation-verification campaign carries a distinct
`EvidenceCampaignRef` and a role-checked verification/evidence-population
identity. MMS may support implementation verification. It MUST NOT satisfy or
be relabeled as:

- target-population evidence;
- workload prevalence;
- physical-model validation;
- deployment relevance;
- context-of-use evidence;
- product qualification; or
- LIVE exam qualification.

No common code path, manufactured physical case, governing equation,
reference backend, generator, parameter range, or representation weakens this
rule. B-02A does not define B-04's policy for deciding whether any evidence is
qualified.

---

## 11. Censoring, replacement, and realized evidence

Censoring is an observable, policy-bound event. It is never silent deletion.
Every `CENSORED` disposition binds an exact immutable `CensoringRecord` with:

Its fixed record type is `censoring_record`; its exact closed fields are:

| # | Field | Exact requirement |
|---:|---|---|
| 1 | `schema_version` | Exact derived-record `VersionToken`. |
| 2 | `canonicalization_profile` | Exact literal `carbon_scientific_authoring_derived_evidence_v1`. |
| 3 | `intended_evidence_unit_ref` | Exact protected plan-slot plus evidence-use/measurement-scope ref. |
| 4 | `evidence_scope` | Exact `EvidenceScopeBinding`; censoring applies only to this scope. |
| 5 | `censoring_reason` | Exact `CensoringReason` code below. |
| 6 | `trigger_failure_binding` | Exact `CensoringTrigger` typed event ref; original event identity remains intact. |
| 7 | `actor_authority_ref` | Registered actor/policy authority; no free-text actor. |
| 8 | `population_ref` | Exact applicable role/population. |
| 9 | `sampling_plan_ref` | Exact plan governing intended accounting. |
| 10 | `evidence_campaign_binding` | `ApplicabilityBinding[EvidenceCampaignRef]`; MUST equal `evidence_scope.evidence_campaign_binding`, including the exact bound ref or exact inapplicability reason. |
| 11 | `query_observation_provenance` | Exact query/observation refs and provenance. |
| 12 | `replacement_decision` | Exact `ReplacementDecision`, including plan/policy/trigger/lineage/accounting binding. |
| 13 | `accounting_binding` | Exact protected intended/attempted/realized count and safe-aggregate evidence ref. |
| 14 | `missingness_adjustment_binding` | Exact statistics-owner adjustment/sensitivity binding or explicit non-settling inapplicability. |
| 15 | `audit_evidence_refs` | Nonempty set-like tuple of exact audit refs. |
| 16 | `downstream_use_restrictions` | Nonempty set-like tuple of exact restrictions; incomplete provenance is non-settling. |

The record contains no digest field. The distinct final `CensoringRecordRef`
contains only `record_type`, `schema_version`, `canonicalization_profile`, and
`content_digest` under §4.1.

Campaign applicability is scope-local, not presumed. A censoring record whose
campaign binding differs from its `evidence_scope` rejects; a campaign-free
scope uses the same exact `NOT_APPLICABLE` binding in both locations.

The exact `population_ref` must be one of the governing SamplingPlan's bound
primary, selection, P, Q, w, query, or observation refs; an unrelated
same-Challenge population rejects. `OBSERVATION_*` additionally requires the
exact bound observation population and nonempty query/observation provenance.
Any bound query or observation population requires nonempty acquisition
provenance for every censoring reason, while a scope with neither population
bound requires that provenance tuple to be empty.
`MEASUREMENT_*` requires a bound measurement-applicability ref in the exact
evidence scope. `EXPERIMENT_CORRUPTED` requires a bound evidence campaign.
Reference and infrastructure reason eligibility remains owned by the
registered external censoring policy rather than inferred by B-02A.

The v1 reason taxonomy is exactly:

- `REFERENCE_UNAVAILABLE`;
- `REFERENCE_DISPUTED`;
- `REFERENCE_NUMERICAL_FAILURE`;
- `REFERENCE_RESOURCE_LIMIT`;
- `REFERENCE_TIMEOUT`;
- `OBSERVATION_MISSING`;
- `OBSERVATION_TIMEOUT`;
- `MEASUREMENT_UNAVAILABLE`;
- `MEASUREMENT_RESOURCE_LIMIT`;
- `MEASUREMENT_TIMEOUT`;
- `EXPERIMENT_CORRUPTED`; and
- `EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER`.

The trigger matrix is closed:

| Reason family | Only admissible typed trigger |
|---|---|
| `REFERENCE_*` | exact B-04-owned reference event/failure ref with matching subtype |
| `OBSERVATION_*` | exact observation-acquisition event/failure ref with matching subtype |
| `MEASUREMENT_*` | exact B-05-owned measurement-acquisition event/failure ref with matching subtype |
| `EXPERIMENT_CORRUPTED` | exact experiment-integrity event ref |
| `EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER` | exact independent infrastructure failure ref plus exact acquisition operation binding |

A candidate timeout/resource/format/execution failure, generator failure,
distribution-conformance failure, generic orchestrator timeout, or untyped
exception cannot satisfy any censoring trigger. It remains its original typed
candidate/generator/infrastructure result and in intended accounting.

`GENERATOR_FAILURE`, `CANDIDATE_FAILURE`, and `SCIENTIFIC_EXCLUSION` are not
censoring reason codes. They retain their distinct result types.

The exact owner policy decides which reasons apply and whether replacement is
allowed. This contract selects no production policy, attempt limit, or
threshold.

### 11.1 Anti-selection invariants

An evaluator MUST NOT:

- retry until an easier case appears;
- drop a failed/censored attempt from intended denominators or stratum
  accounting without the registered statistical rule;
- treat a replacement as the original case;
- reclassify generation failure as exclusion or censoring;
- relabel a reference/candidate/infrastructure failure as scientific
  evidence;
- infer target prevalence from retained or realized-valid cases;
- expose protected composition through overly granular counts; or
- make any unregistered or out-of-full-design change to Q, w, allocation,
  inclusion, exclusion, replacement, stopping, or extension after seeing
  candidate results.

An exact preregistered, coverage-qualified sequential rule already bound into
the SamplingPlan and `full_design_law_ref` may perform only its declared
allocation/stopping operation using its declared information. It cannot
rewrite P, Q, w, the estimand/reporting contract, the maximum budget, or its
own qualification. Every other candidate-outcome access is prohibited by the
exact binding and remains non-settling.

### 11.2 `RealizedValidEvidenceRecord`

This is a separately typed, capability-created audit/result record, never an
author-created `InstanceDistributionContract`. Its fixed record type is
`realized_valid_evidence_record`; its exact closed fields are:

| # | Field | Exact type and rule |
|---:|---|---|
| 1 | `schema_version` | Exact derived-record `VersionToken`. |
| 2 | `canonicalization_profile` | Exact literal `carbon_scientific_authoring_derived_evidence_v1`. |
| 3 | `challenge_key` | Exact A3 `ChallengeKey`. |
| 4 | `sampling_plan_ref` | Exact plan; the plan's complete finite-design law remains controlling. |
| 5 | `primary_population_ref` | Exact plan-bound population ref. |
| 6 | `selection_population_ref` | Exact plan-bound base selection/proposal ref. |
| 7 | `target_population_binding` | Exact plan-matching P binding or inapplicability. |
| 8 | `official_proposal_binding` | Exact plan-matching Q binding or inapplicability. |
| 9 | `evidence_weight_binding` | Exact plan-matching w binding or inapplicability. |
| 10 | `intended_estimand_or_reporting_ref` | Exact plan-matching estimand/reporting contract. |
| 11 | `evidence_scope` | Exact campaign/query/observation/measurement-or-evidence-use scope. |
| 12 | `disposition_refs` | Nonempty set-like tuple of exact `CanonicalCaseDispositionRef` covering every intended evidence unit in scope. |
| 13 | `complete_unit_manifest_ref` | Exact protected commitment proving no intended unit was silently omitted. |
| 14 | `accounting_evidence_ref` | Exact intended/attempted/generated/eligible/excluded/censored/valid/replacement count and lineage evidence. |
| 15 | `denominator_policy_ref` | Exact statistics owner ref matching the plan and dispositions. |
| 16 | `censoring_policy_ref` | Exact plan-matching policy ref. |
| 17 | `missingness_adjustment_binding` | Exact registered adjustment ref or explicit inapplicability that restricts use to non-settling/raw reporting. |
| 18 | `sensitivity_analysis_binding` | Exact statistics evidence ref or explicit inapplicability with downstream restriction. |
| 19 | `distribution_conformance_evidence_ref` | Exact evidence for generation/screening/exclusion conformance to the full design. |
| 20 | `construction_authority_ref` | Exact controlled accounting capability/authority ref. |
| 21 | `construction_audit_refs` | Nonempty set-like tuple of exact audit refs. |
| 22 | `disclosure_contract` | Exact safe aggregate/protected composition contract. |
| 23 | `downstream_use_restrictions` | Nonempty set-like tuple of exact restriction refs. |

Construction is two-stage and fail closed. First, a separately owned
statistics/history authority returns an exact immutable echo of the complete
intended-unit manifest, SamplingPlan, P/Q/w bindings, estimand/reporting
contract, accounting and denominator/censoring policies, optional registered
adjustments, authority identity, and audit refs. That manifest capability alone
MUST NOT construct `RealizedValidEvidenceRecord`. A second finalization call
must echo the exact complete disposition records and their recomputed refs plus
every exact loaded `CensoringRecord` and recomputed censoring ref linked by a
`CENSORED` disposition. Missing, extra, substituted, stale, tampered, or
fabricated disposition/censor records reject. The resulting non-serializable
finalization capability is pinned to that one exact composition; reusing it
with an altered composition rejects. This is trusted in-process composition,
not authentication, signature verification, or the separately owned durable
statistics/history implementation.

The record contains no digest field. Its distinct final
`RealizedValidEvidenceRecordRef` contains only `record_type`,
`schema_version`, `canonicalization_profile`, and `content_digest` under §4.1.
Construction is available
only after verifying the exact plan, every intended evidence-unit commitment,
every disposition/ref, protected accounting, and policy pins. An author or
caller cannot create or edit it post hoc. It describes what evidence remained
for one exact scope; it does not become P or Q, rewrite w or denominators,
transfer applicability to another measurement/estimand, authorize silent
missingness adjustment, or confer sufficiency/qualification/LIVE authority.

---

## 12. Exact validation and cross-object consistency

B-02A constructors, parsers, loaders, and projection factories SHALL
fail closed. Error types/codes must be stable and non-echoing where input may
contain protected material.

### 12.1 Global exact-type and malformed-input rules

The implementation MUST reject:

- a wrong exact top-level or nested nominal type;
- a subclass where an exact Carbon type is required;
- Boolean supplied as integer or number;
- integer supplied as float or float supplied as integer without exact schema
  authorization;
- string/numeric/enum coercion;
- unknown, extra, duplicate, or missing fields;
- unknown object kinds, ref kinds, union tags, enum values, roles, or states;
- empty required IDs, versions, refs, clauses, tuples, or text;
- duplicate IDs, causal inputs, outputs, axes, strata, refs, set members, or
  allocation entries;
- malformed A3 identifiers/versions/digests;
- invalid UTF-8, unpaired surrogates, forbidden controls, or non-NFC text;
- NaN, infinity, an out-of-range integer, or a noncanonical zero after
  construction;
- shape/rank/dimension, precision, unit, geometry, domain, BC/IC, time, or
  horizon inconsistency;
- wrong ref kind, role, Challenge key, object ID, version, schema,
  canonicalization profile, or digest;
- a digest mismatch, byte tamper, or parse before digest verification;
- a supersession cycle, cross-kind edge, missing predecessor, or historical
  alias; cross-Challenge or cross-object-ID supersession also rejects;
- untrusted provenance/rights/qualification/fixture labels; and
- unresolved mandatory human scientific input in a production or LIVE
  authoring path.

### 12.2 Cross-object rules

The complete loaded graph MUST also reject:

- a candidate contract that omits/reinterprets a physical causal input,
  required physical output, or disagrees on units, geometry/domain, BC/IC,
  time/horizon, envelope, or claim;
- a distribution or support bound to the wrong physical/candidate contract;
- Q without its exact P binding;
- w without exact matrix-required P/Q bindings, an official aggregate design
  without an exact compatible w, a no-w plan without its exact non-aggregating
  or non-official role-reporting authority, a non-official reporting contract
  that claims P/Q/w/score authority, or w/coefficient inferred from observed
  frequency;
- training support in a P/Q/w/evaluation field;
- `R_strategy` in any population, evidence-weight, official plan, official
  draw, reference, measurement, gate, or score field;
- population identity inferred from common support, PDE, generator, seed,
  range, representation, storage, or source rows;
- an empty/omitted applicability set, an unknown `AllowedConsumer` tag or enum,
  a missing pinned downstream-consumer contract, or use by a consumer absent
  from the population's exact `allowed_consumers` set;
- a set-only Q or otherwise incomplete selection law in an executable plan;
- a SamplingPlan with a role-matrix mismatch, estimand/full-design mismatch,
  unknown stratum, missing crosswalk, inconsistent count/budget, impossible
  allocation, invalid fraction/apportionment, or uncovered sampling unit;
- missing or ambiguous dependence, replication, query/observation allocation,
  reference-fidelity allocation, stopping/extension, duplicate, replacement,
  exclusion, censoring, denominator, or weighting behavior;
- a query/observation/campaign role mismatch, including a censoring record
  whose `evidence_campaign_binding` is not exactly equal to its evidence
  scope's campaign binding;
- MMS or another evidence role relabeled into a different authority;
- a `CaseEvidenceBinding` whose exact claim-scope ref differs from its
  physical/candidate/population/campaign claim graph, even when generic
  applicability refs overlap;
- a case state with incompatible case/attempt/reason payload;
- a raw protected case ref accepted by a public surface;
- case-ref disclosure class different from the loaded case, a public
  projection substituted for authoritative case identity, or protected case
  identity accepted by a public surface;
- fixture-origin cleansing through content addressing or reconstruction; and
- an object, ref, case, evidence binding, or loader result treating itself as
  qualified or LIVE.

### 12.3 Equality, immutability, and mutation isolation

Authored objects, refs, loader results, subordinate records, and projections
are final exact nominal types. Equality requires exact type and exact field
equality. Content objects additionally require equality of their recomputed
exact ref. Subclass comparison, coercive comparison, logical-ID-only equality,
and Python object identity are forbidden.

Construction and loading defensively reconstruct all nested exact values.
Mutating caller input after construction cannot change an object; mutating a
returned mutable view is impossible; and loading twice cannot create shared
mutable state. Hash/equality behavior remains stable for the object's life.

### 12.4 Historical retrieval and prospective change

Every evidence-bearing consumer resolves exact historical refs. A new object,
profile, law, envelope, claim, population, SamplingPlan, support, rights
profile, generator, case representation, or policy applies prospectively. A
bug fix that changes semantic bytes creates a new version/digest and does not
rescore or reinterpret historical evidence silently.

The current A3 store remains its owner's lifecycle store. Because its non-LIVE
draft/fixture records may be replaced under owner rules, it is not silently
declared B-02A's immutable history store. Working decisions B-02A-D7 and
B-02A-D8 select a separate append-only exact-ref history/origin store and an
A3-owned fail-closed verifier seam without changing this ownership boundary.

---

## 13. Fixture provenance and A3 LIVE boundary

Fixtures may exercise shape, type validation, identity, canonicalization,
digest pinning, loading, equality, immutability, supersession, projection,
failure, and integration. They do not exercise or establish real scientific
truth.

Structural origin rules are:

1. origin is issued/verified by a controlled loader/registry capability, not
   by a caller Boolean/string/field;
2. fixture origin propagates through every exact ref load and composed graph;
3. a graph containing any fixture physical-system contract, population,
   SamplingPlan, training-support contract, canonical case, subordinate owner
   ref, or reference remains fixture-derived;
4. hashing, pinning, copying, renaming, superseding, re-registering, or
   reconstructing cannot cleanse fixture origin;
5. missing provenance or an unresolved graph is non-production and
   non-LIVE; and
6. only A3's independently controlled current qualification/LIVE gate may
   assess a complete exact non-fixture graph.

### 13.1 A3 exact graph pins and verifier seam

A3 `ChallengeRecord` and `QualificationManifest` each carry
`scientific_authoring_graph_fingerprint: TaggedSha256 | None`. Optionality is
only a stored-schema compatibility boundary. A legacy or fixture record may
omit the field or encode `null` and remain parseable; stable serialization
emits both names under A3's existing sorted-key JSON rules. Unknown fields,
non-string non-null values, subclasses, uppercase or untagged digests,
whitespace, and alternate algorithms reject. Parse compatibility does not
backfill a pin, rewrite history, or confer production compatibility.

Every production assessment, `can_go_live` result, activation, and
effective-LIVE revalidation requires: (1) the record pin; (2) the qualification
manifest pin when the independently mandatory manifest is present; (3)
byte-for-byte equality of those pins; (4) invocation of the configured
`ScientificAuthoringVerifier` with the exact reconstructed `ChallengeKey` and
common fingerprint; and (5) an exact result echo reporting an eligible graph.
If the manifest is absent, the existing qualification gate fails separately.
If either pin is absent, malformed, or mismatched, A3 fails closed and does not
ask a verifier to invent one. A legacy record stored as `live` without the pins
remains parseable but is not effectively LIVE.

The verifier operation is exactly:

```text
verify_scientific_authoring(
    challenge_key: ChallengeKey,
    expected_graph_fingerprint: TaggedSha256,
    /,
) -> ScientificAuthoringEligibility
```

It is a configured registry capability, never a per-request Boolean or
self-asserted qualification field. The exact final result has
`challenge_key`, `graph_fingerprint`, `graph_origin`, exact built-in Boolean
`complete` and `revoked`, and a tuple of closed
`ScientificAuthoringReason` values. A3 reconstructs the exact result type,
rejects subclasses/mappings/duck types, and requires exact Challenge-key and
fingerprint echoes. Results for another Challenge, another graph under the
same key, or a stale pin are ineligible.

The reason tuple is derived in fixed order: `GRAPH_INCOMPLETE` when incomplete;
then `GRAPH_FIXTURE_DERIVED` for `FIXTURE_DERIVED`, otherwise
`GRAPH_DRAFT_OR_UNRESOLVED` for `DRAFT_OR_UNRESOLVED`; then `GRAPH_REVOKED`
when revoked. The graph is structurally eligible only when complete, origin is
`REGISTERED_GRAPH`, not revoked, and reasons is empty. A provider cannot choose
an inconsistent reason tuple. Missing provider, provider exception, malformed
result, echo mismatch, incomplete/fixture/draft/unresolved/revoked graph, or
substitution fails closed through stable non-sensitive reasons without echoing
exception text or untrusted values.

The store-backed B-02A verifier independently reconstructs and validates the
exact requested graph. Failure before an exact graph exists yields incomplete
draft/unresolved state without exception detail. If a graph resolves but its
computed fingerprint differs, the result reports the computed fingerprint in
incomplete draft/unresolved state; A3's exact echo check then rejects it. This
blocks substitution even within one Challenge key. The explicit fixture-mode
diagnostic path neither invokes nor bypasses this production gate, changes
lifecycle state, nor activates LIVE.

### 13.2 A3 ownership ceiling

The fingerprint/verifier result is a necessary authoring-structure condition,
never sufficient for LIVE. It creates or satisfies none of A3's independent
Challenge binding, qualification mode/slots, artifact/digest checks,
backbone/backend bindings, human qualification decision, lifecycle transition,
or activation authority. It mutates no registry record and establishes no
scientific truth, reference/measurement qualification, evidence sufficiency,
security acceptance, network/commercial/production qualification, or LIVE
authority.

A3 owns the verifier protocol/result grammar, persisted pins, production gate,
lifecycle, activation, and effective-LIVE revalidation. B-02A owns authored
objects, immutable loading/history, exact manifest resolution, structural
origin composition, and graph-fingerprint computation. A3 imports no
`carbon.authoring`; the dependency remains one-way from B-02A to A3 public
identity, digest, and verifier contracts. No label, Boolean, pin alone,
provider availability, reconstructibility, or matching digest crosses that
boundary.

Tests SHALL prove directly that no fixture-authored
`PhysicalSystemSpec`, `CandidateOutputContract`,
`InstanceDistributionContract`, `SamplingPlan`, `TrainingSupportContract`,
`CanonicalChallengeCase`, or corresponding ref can satisfy A3's LIVE gate or
create official scientific authority.

A fixture result cannot create an official exam, evidence, score, rank,
frontier event, publication authority, product qualification, settlement,
network weight, emission, launch state, commercial validation, or production
qualification.

---

## 14. Ownership and downstream seams

| Owner/consumer | B-02A supplies | B-02A explicitly does not own |
|---|---|---|
| B-02B | Exact authored refs, candidate causal/output boundary, training-support membership/rights boundary, and reserved `R_strategy` seam | Candidate assembly, ParameterCatalog, compiler, `ResolvedTrainingSamplingPolicy`, `TrainingSamplingPolicyRef`, seeds, or draws |
| B-03 | Physical/candidate/population/plan/case contracts and generator identity/ref seam | Generator implementation, request/result runtime API, replay, real values, runtime disposition production, or generator qualification |
| B-04 | Case/evidence-role/campaign/population/artifact identity and authority-separation seams | ReferencePolicy, TruthAsset, solver selection, qualification, uncertainty, disagreement, applicability decisions, runners, or MMS adequacy |
| B-05 | Candidate outputs, case/evidence bindings, and distinct w ref | MeasurementContract, estimand, weights, thresholds, gates, evidence eligibility, Score Pack values, or scoring |
| B-06 | Complete exact authored graph and provenance inputs | D1–D12 dossier evidence, qualification judgments, or manifest conclusions |
| B-07R | Public-safe projection requirements and population/authority boundaries | Research architecture ratification, service behavior, rights decisions, or prior/practice policy |
| B-07S | Semantic objects/ref inputs to later wire design | Exact service wire, operation encoding, error schema, lifecycle, bounds, or protocol canonicalization |
| A3 | Exact current Challenge identity/version/digest primitives, exact authoring-graph fingerprint, and configured verifier input | Registry lifecycle, qualification slots/decisions, activation authority, or any claim that the authoring check alone is sufficient for LIVE |
| A4 | Protected/public case projection seam | Entropy, seed derivation, official draws, commitments, opaque-handle derivation, or security qualification |
| Business/rights owners | Exact rights-profile references and fail-closed use | Legal conclusions, ownership, licensing, confidentiality, publication, reuse, or exclusivity decisions |

No layer certifies itself. A generator does not define the population, a
candidate does not define the official exam, a scorer does not define P/Q, a
fixture does not define science, and B-02A does not qualify its own objects.

### 14.1 Implementation package decision

Working decision B-02A-D6 selects `carbon.authoring` as a new canonical role
package after reconciling:

- `.agent/CODE_AUTHORITY.toml` and machine enforcement;
- ownership versus the existing registry/schema/evaluation/qualification/
  audit roots;
- a one-way dependency on only the standard library and minimal public A3
  primitives;
- exact public/internal/protected exports;
- immutable history/storage ownership;
- package and wheel inclusion;
- import-graph tests; and
- clean installed-wheel, outside-tree imports.

`carbon/challenges`, `carbon/data`, and `carbon/physics` remain retired. Empty
reserved packages are not available merely because they exist. The bounded
implementation adds `carbon.authoring`, its code-authority entry, and its
tests. It adds no dependency and changes no package metadata, lock, workflow,
environment, archive, or retired namespace.

---

## 15. Required B-02A implementation test matrix

This section controls the current bounded implementation and final review. A
listed test becomes evidence only when it runs successfully on the exact
candidate; no test result creates qualification or LIVE authority.

### 15.1 Construction and exact nominal types

Tests SHALL cover every top-level identity object, ref, subordinate record, loader
result, provenance union, case projection, evidence binding, and disposition:

- exact valid top-level and nested construction;
- rejection of every subclass at authority-bearing boundaries;
- Boolean-versus-integer and Boolean-versus-float rejection;
- integer/float/string/enum coercion rejection;
- unknown, extra, duplicate, and missing field rejection in every authoring
  adapter and loader;
- unknown object kind, ref type, population role, evidence role, state, union
  tag, enum, and literal rejection;
- duplicate object/field/axis/stratum/ref/set/allocation ID rejection;
- wrong exact nested tuple/entry/ref type rejection; and
- no caller construction of trusted origin or public/protected projection
  capability.

### 15.2 Malformed identifiers, Unicode, numerics, and field constraints

Tests SHALL cover:

- empty, overlong, non-ASCII, wrong-case, path-like, control-bearing, or
  otherwise invalid A3 identifiers and versions;
- invalid digest prefix, case, length, alphabet, and mismatch;
- malformed UTF-8, unpaired surrogates, NUL/C0/C1 controls, and non-NFC text;
- NaN, positive/negative infinity, wrong numeric type, out-of-range
  `Int64`/`UInt64`, and canonical positive-zero behavior;
- invalid rank, shape, axis, precision, unit, geometry/domain, BC/IC,
  time/horizon, causal-input, and output combinations;
- empty required tuples/refs/clauses and invalid conditional presence; and
- non-settling behavior when a mandatory human scientific or rights value is
  unresolved.

### 15.3 Canonicalization and hash pins

Tests SHALL include independent golden encoders/vectors proving:

- exact header, object-kind domain separation, primitive tags, record type,
  strict field-name ordering,
  union tags, lengths, big-endian integers/binary64, and profile bounds;
- identical semantic input produces identical bytes/digest across clean
  processes;
- mapping/authoring insertion order, locale, timezone, path, current time,
  environment variables, current checkout, hash seed, and object identity do
  not change bytes;
- Boolean/integer/float, tuple order, Unicode, and positive-zero edge vectors
  remain exact;
- set-like tuples sort by canonical bytes and reject duplicates;
- exact-at-limit and over-limit document, `TEXT`/`BYTES`, tuple-count, and
  nesting-depth vectors;
- truncated, overdeclared, noncanonical, or trailing lengths/counts reject,
  and a bounded reader rejects before attacker-sized allocation;
- a one-byte tamper, wrong kind, wrong Challenge key, wrong ID/version/schema/
  profile, or wrong digest fails;
- digest verification occurs before parse/object construction;
- reference round trips reproduce exact nominal refs;
- internal/recomputed ref must equal the externally expected ref; and
- neither Python `repr` nor an owner-private A4/A5/A7 serializer participates.

Filesystem-backed loader tests SHALL also reject symlinks, directories,
devices/special files, source-swap races, short reads, growth after bound
checking, and a trusted-store result whose bytes change between verification
and construction.

### 15.4 Equality, immutability, and mutation isolation

Tests SHALL prove:

- exact-type equality and inequality by every identity/content field;
- logical-ID-only, subclass, coercive, and Python-object-identity equality do
  not apply;
- top-level and nested values are immutable;
- mutating constructor source containers cannot change an object;
- separate loads do not alias mutable state;
- returned bytes/views and loader results do not permit mutation of stored
  identity; and
- hash/equality remain stable for the object's life.

### 15.5 Supersession and historical identity

Tests SHALL prove:

- valid same-kind prospective supersession;
- cross-kind, cross-Challenge, cross-object-ID, missing-predecessor, and cycle
  rejection;
- exact historical version/digest retrieval;
- no `latest` reinterpretation or old-ref resolution to new bytes;
- a new canonicalization profile or semantic version preserves historical
  bytes/evidence; and
- fixture provenance and authority do not transfer or cleanse through
  supersession.

### 15.6 Physical/candidate cross-contract tests

Tests SHALL prove:

- complete binding of every applicable physical causal input;
- exact resolution of every causal/BC/IC/time candidate field ID through the
  authoritative `candidate_inputs` tuple;
- complete one-to-one binding of every required physical quantity to every
  candidate output;
- missing, duplicated, renamed, reinterpreted, silently defaulted, or extra
  causal input rejection;
- orphan candidate inputs, unresolved IDs, duplicate targets, cross-family
  target collisions, and v1 cross-source packing rejection;
- missing, duplicated, substituted, extra, or unregistered-derived output
  binding rejection;
- exact unit, representation, shape/rank, precision, geometry/domain, BC/IC,
  time/horizon, envelope, and claim agreement;
- exact v1 candidate/physical geometry-domain ref equality and rejection of a
  caller-asserted or unregistered adapter relation;
- adapter encoding cannot change physical semantics;
- missing/extra/malformed candidate output is typed candidate-format failure;
  and
- candidate format validity creates no scientific/measurement/score claim.

### 15.7 Population, support, and `R_strategy` confusion rejection

Tests SHALL attempt every invalid substitution and prove rejection:

- P as Q, P as w, Q as P/prevalence, Q as w, and w as a probability law;
- sampling frequency/allocation/retained frequency as target prevalence or
  evidence weight;
- training support as P, Q, w, stress, official evaluation, product,
  deployment, query, observation, campaign, or realized evidence;
- `R_strategy` as P, Q, w, TrainingSupportContract, SamplingPlan, official
  population/draw, reference selection, measurement, gate, or scorer control;
- stress, practice, product-qualification, deployment, query, observation, and
  evidence-campaign role substitution, plus rejection of
  `REALIZED_VALID_EVIDENCE` as an authored population role;
- shared support, PDE, range, generator, seed family, case representation,
  storage, or data source as population identity/authority;
- every valid and invalid branch of the §6.3 population-role matrix and §8.1
  SamplingPlan role matrix;
- Q without exact P, executable-law, and full-plan binding; set-only Q in an
  executable plan; set-only P used for prevalence/expectation/target-risk;
- w without exact matrix-required P/Q/estimand/full-design agreement, or
  no-weighting used for an official aggregating estimand;
- non-official role-specific aggregation accepted only through its exact
  reporting contract with no P/Q/w/score authority, and rejection of raw
  frequency or implicit coefficients in that branch;
- unknown rights, provenance, membership, source, permitted use, or
  restriction state;
- empty applicability, an unknown `AllowedConsumer` tag/role/owner, or a
  downstream-owner tag without its exact pinned consumer contract; and
- consuming a population through an object/role not in its exact
  `allowed_consumers` contract.

### 15.8 Sampling, query/observation, censoring, and realized evidence

Tests SHALL cover:

- exact query- and observation-population binding;
- exact evidence-campaign binding, including exact equality between each
  censoring record's campaign applicability binding and its evidence scope;
- exact intended estimand/reporting and evidence-use/measurement scope binding;
- unknown stratum, wrong primary/selection partition, missing crosswalk,
  invalid allocation/fraction/zero authority, inconsistent counts/budgets,
  impossible allocation, apportionment/tie, and
  non-exhaustive/overlap/hierarchy-policy failures;
- exact dependence, replication, query/observation allocation,
  reference-fidelity allocation, uncertainty/tail/minimum-subgroup objective,
  and sampling/analysis-unit bindings;
- fixed and registered-sequential design branches, base-evidence requirement,
  stopping/extension/interim-look/max-budget/sequential-allocation controls,
  candidate-outcome access/prohibition, heuristic-stop `EVIDENCE_DEFERRED`,
  exhausted-budget `INDETERMINATE`/`INSUFFICIENT_EVIDENCE`, coverage-
  qualification, and new-version-on-amendment behavior;
- every mode/outcome-access matrix branch, nested/outer coverage/sequential/
  full-design ref equality, complete-base-evidence gating, and rejection of
  pre-base candidate-performance access or scientific denial;
- exact physical, representation, near-, repeated-observation, and replacement
  duplicate policy;
- intended-slot, attempted-draw, generated, eligible, excluded, censored,
  valid-evidence, and replacement accounting;
- exclusion versus censoring and generation failure versus censoring;
- generated, observed, experimental, industrial, analytic, and MMS case-source
  variants with exact provenance and no source-to-evidence-role transfer;
- post-draw exclusion only under exact preregistered screening and inclusion-
  probability/accounting semantics; otherwise out-of-support generation is a
  non-settling distribution-conformance/generation failure;
- required censoring reason, typed trigger, actor/policy authority,
  population, plan, campaign, query/observation, replacement, accounting,
  audit, and downstream restrictions;
- silent retry/drop/easy-case selection rejection;
- candidate/resource/timeout/format failures rejected from every censoring
  trigger, with each reference/observation/measurement/experiment/
  acquisition-infrastructure trigger accepted only by its exact reason family;
- replacement retaining distinct identity and protected lineage;
- replacement reason/state eligibility, draw law, stratum preservation,
  attempt ceiling, denominator, and weight-effect enforcement;
- exact NEVER/registered policy-binding versus decision/trigger/lineage/
  accounting shapes, including plan-ref and inline-policy-ref mismatch
  rejection;
- insufficient realized evidence remaining non-settling;
- public aggregates obeying disclosure/aggregation controls and not revealing
  protected composition; and
- capability-only `RealizedValidEvidenceRecord` construction from a complete
  intended-unit manifest and exact dispositions, with scope-specific
  missingness/denominator/sensitivity bindings; and
- realized evidence never replacing P/Q, silently changing w/denominators, or
  transferring applicability among evidence uses.

### 15.9 Evidence roles and MMS

Tests SHALL cover every closed evidence role and prove:

- two roles on the same canonical case retain distinct campaign/population/
  applicability/authority;
- evidence bound to one exact claim scope cannot be cast, copied, or reused as
  evidence for another claim scope because applicability text overlaps;
- no evidence role inherits qualification from another;
- a hybrid role is unavailable without a prospectively registered exact ref;
- MMS cannot load, cast, alias, or be relabeled as target/workload prevalence,
  physical-model validation, deployment, context-of-use, product
  qualification, or LIVE exam evidence; and
- B-04-owned qualification remains external and cannot be manufactured by a
  B-02A binding.

### 15.10 Public/protected identity non-disclosure

Tests SHALL prove that public types, serialization, logs, errors,
exceptions, `repr`, equality, copying, generic mapping conversion, and
introspection expose no:

- raw protected case ref/digest where correlation or reconstruction is
  possible;
- reversible draw/slot identity;
- seed or entropy;
- hidden stratum realization;
- exam order or replacement chain;
- protected population composition; or
- reconstruction-sensitive generator input or payload ref.

Internal/protected refs MUST fail exact-type checks at public/miner surfaces.
An invalid audience request fails closed. The public opaque handle must be
nonreversible under the separately owned A4/security contract.

Tests SHALL also tamper the case object's `disclosure_class`, case-ref class,
projection schema/fact kind/disclosure/issuance binding, and authoritative
case-ref/public-projection pairing independently. Every mismatch rejects; a
public projection can never satisfy the authoritative case-ref field.

### 15.11 Fixture inability to satisfy LIVE

Tests SHALL prove that:

- provenance comes from a controlled structural origin, not a Boolean or
  label;
- every origin variant requires its exact registration/authority/provenance
  evidence, and the graph join produces fixture-derived, draft/unresolved, or
  registered only under the closed rules;
- fixture taint propagates through refs, loading, composition, cases,
  projections, and supersession;
- copying, hashing, renaming, reconstructing, or re-registering does not
  cleanse fixture origin;
- every fixture-authored physical-system contract, candidate contract,
  population, SamplingPlan, training support, canonical case, and ref fails
  A3's LIVE qualification path; and
- a fixture creates no official evidence, score, frontier, settlement,
  network weight, emission, product, commercial, or production authority.

Historical-origin tests SHALL prove that a later immutable revocation blocks
new use without rewriting an earlier exact origin/qualification/evidence
record.

### 15.12 Packaging and dependency direction

For the implemented B-02A-D6 package/path decision, acceptance tests SHALL
cover:

- exact ordered public exports and absence of protected/private convenience
  types;
- source import-graph and one-way dependency direction;
- `.agent/CODE_AUTHORITY.toml` enforcement for the authorized implementation
  change;
- absence of retired packages and undeclared/heavy optional dependencies;
- build of a clean wheel;
- install of that wheel in a fresh environment;
- isolated `python -I` import of each public B-02A module outside the source
  tree; and
- complete repository bootstrap, doctor, CPU, invariant, quality,
  package/wheel, code-authority, and diff-hygiene CI.

---

## 16. Closed non-conflation ledger

The following identities and states MUST remain distinct even when they share
content or provenance:

| Must remain distinct | Rule |
|---|---|
| authored contract or immutable realization record / exact ref / loaded result / trusted origin / qualification / mutable runtime event | No layer inherits another layer's authority or mutability. |
| P / Q / w / TrainingSupportContract / `R_strategy` | P/Q/w use closed role-tagged objects and expected-role-checked refs; TrainingSupport and later `R_strategy` are distinct exact types. Every cross-role substitution rejects. |
| target / stress / practice / product-qualification / deployment | Overlap is not identity or claim transfer. |
| target / query / observation / evidence campaign / realized valid evidence | Each owns a different scientific question and provenance. |
| support / population measure / sampling allocation / evidence weighting | Shared support does not imply equal law, prevalence, allocation, or weight. |
| physical-system conformance / candidate format validity / candidate scientific outcome | Each returns a distinct typed result. |
| generator determinism / distribution conformance / reference correctness / exam qualification | Evidence for one cannot satisfy another. |
| canonical case / evidence role / evidence qualification | Same case does not transfer evidence authority. |
| MMS verification / target or physical validation / deployment or product evidence | Relabeling is forbidden. |
| valid / censored / excluded / generation failure | Closed state shapes and evidence differ. |
| generation / reference / candidate / measurement / infrastructure failure | No coercion into another failure or a scientific zero. |
| retry or replacement / original intended slot | Replacement remains a new linked identity and cannot disappear from accounting. |
| public opaque case handle / internal or protected case identity | Public surfaces cannot reconstruct or correlate protected exam state. |
| fixture / draft / registered origin / qualified / LIVE | A caller label, digest, or reconstruction cannot promote maturity. |
| scientific / security / network / commercial / production qualification | Each is independently owned and presently unearned. |
| score or rank / frontier event / settlement or emission authority | No B-02A object creates any of these states. |

---

## 17. Unresolved human inputs, final review gate, and earned maturity

The following remain explicit human/owner inputs:

- the first real `PhysicalSystemSpec` and `CandidateOutputContract`, including
  whether viscosity or any other quantity is an assumption or causal input;
- official claim scope and operating envelope;
- real P, Q, w, intended estimands/reporting uses, support, stratification,
  exclusions, applicability, and provenance;
- production sampling/analysis units, base counts and sequential budgets,
  allocations/crosswalks, dependence/replication, query/observation and
  reference-fidelity allocations, uncertainty/tail/subgroup objectives,
  stopping/extension and candidate-outcome-access rules, duplicate/
  replacement/exclusion/censoring/missingness/denominator/sensitivity policy,
  and statistical sufficiency/coverage evidence;
- real TrainingSupportContract contents, sources, generators, rights,
  permitted uses, restrictions, retention, reuse, publication, and
  exclusivity;
- B-04/B-05/B-06 reference, measurement, scoring, and qualification decisions;
- any registered hybrid evidence role;
- security-owned opaque public case-handle construction; and
- scientific, statistics, security, rights, qualification, LIVE, launch,
  production, settlement, weight, and emission decisions owned outside B-02A.

Missing inputs keep real/production authoring unavailable. They do not permit
a default from planning prose, a fixture, an open pull request, historical
code, a generator, shared data, empirical sample frequency, or agent judgment.
They also do not block unrelated exact schema, fixture, validation,
canonicalization, history, loader, projection, or fail-closed integration work.

The working contract and implementation become an accepted B-02A repository
result only after:

1. independent SciML/physics review of the final exact
   physical/candidate/population/evidence-role implementation and contract;
2. independent statistics review of the final exact P/Q/w, strata, sampling,
   censoring, replacement, and intended-versus-realized evidence semantics;
3. independent protocol review of the final exact identity,
   canonicalization, provenance, failure, disclosure, fixture, history, A3,
   package, and downstream boundaries;
4. resolution of every blocking finding and review thread;
5. required exact-head CI and repository validation; and
6. normal merge with the reviewed tree preserved.

No affirmative lead response or silence gate is a precondition to bounded
implementation. An observed `CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` pauses
the affected change. The first B-02A Definition-of-Done checkbox remains
incomplete until its final-review and normal-merge clauses are satisfied.
The current PR #60 candidate maturity is:

```text
SPECIFIED: AGENT-SELECTED WORKING CONTRACT
IMPLEMENTED: BOUNDED CANDIDATE; FINAL REVIEW AND NORMAL MERGE PENDING
TESTED (B-02A implementation): BOUNDED CANDIDATE; EXACT-HEAD CANONICAL CI,
INDEPENDENT REVIEW, AND NORMAL MERGE PENDING
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE / LAUNCH / FRONTIER / PRODUCT / SETTLEMENT / CHAIN / WEIGHT / EMISSION
AUTHORITY: NO
```

---

*Carbon authors one exact scientific job, keeps population and evidence roles
separate, and binds every realization prospectively. Reproducibility proves
identity; only independent evidence and human authority can qualify meaning.*
