# Candidate Assembly and Strategy Compiler Contract

**Version:** 0.1<br>
**Status:** AGENT-SELECTED WORKING CONTRACT<br>
**Ticket:** B-02B<br>
**Authority class:** bounded engineering contract only<br>
**Depends on:** A2, B-02A, and B-07R<br>
**Maturity ceiling:** no scientific, security, product, LIVE, network, or
production qualification

This contract gives executable meaning to the ratified four-field Strategy v1
envelope without accepting participant code or participant-defined
construction graphs. It defines immutable Challenge-bound catalogs, a fixed
outer assembly contract, a deterministic semantic compiler, a resolved
training-only sampling policy, and one exact construction plan. Human owners
still supply every real catalog value, physical applicability claim, component,
training policy, environment, and qualification decision.

The normative compilation law is:

```text
exact accepted Strategy v1 and its exact StrategyHash
+ exact ChallengeKey
+ exact CandidateAssemblyContract
+ exact ParameterCatalog
+ exact B-02A authoring refs
+ exact CompilerIdentity
+ exact dependency, environment, backbone, and component pins

-> one exact ResolvedTrainingSamplingPolicy and reference
-> one exact canonical ResolvedConstructionPlan and reference

or

-> one typed fail-closed CompileRejected result and no partial output
```

No consumer mode, entropy domain, seed, draw, official case, resource-policy
verdict, scientific result, or score enters that law.

---

## 1. Authority reconciliation and bounded scope

### 1.1 Controlling owners

- A2 owns the inert Strategy v1 envelope and `dry_validate`. Its exact top-level
  fields remain `schema_version`, `challenge_id`, `backbone`, and `parameters`.
- A7 owns the already-deployed persistent Strategy identity semantics. Its
  existing `carbon.strategy.identity.v1` framing, digest, golden vectors, and
  public `StrategyHash` type remain authoritative.
- A3 owns `ChallengeKey`, canonical identifier/version grammar, and LIVE
  eligibility. Strategy v1 names only the Challenge family; the compiler binds
  the exact Challenge version supplied out of band.
- B-02A owns scientific-authoring refs, `TrainingSupportContract`, exact scalar
  primitives, canonical value encoding, content-digest grammar, and immutable
  prospective history.
- B-07R owns the `P` / `Q` / `w` / `R_strategy` separation and the rule that
  practice and official-shaped execution share construction semantics but not
  authority or randomness.
- B-02B owns candidate assembly, catalog semantics, semantic compilation,
  resolved training-policy identity, resolved-plan identity, component
  compatibility, and policy-agnostic static resource metadata.
- B-02C alone owns resource ceilings, admission, enforcement, operational
  rails, and resource-policy receipts.
- B-07S owns wire parsing and must reject duplicate JSON object members before
  materializing a Python dictionary. B-07F owns the later fixture-official
  adapter. Neither is implemented here.

### 1.2 KEEP / WRAP / REPAIR / REPLACE disposition

| Surface | Disposition | Contract consequence |
|---|---|---|
| A2 `dry_validate` and four-field Strategy v1 | KEEP | Validate one detached hostile-input snapshot exactly once; do not widen A2. |
| A3 `ChallengeKey` and identifier/version/digest grammar | KEEP | Reuse exact types and validators. |
| B-02A refs, scalar validators, canonical values, and tagged SHA-256 | WRAP | Construction adds only a domain-separated closed document frame and adapters. |
| A7 private Strategy capture/hash implementation | REPAIR + WRAP | Extract the exact A7-owned algorithm to public `carbon.fees.strategy_identity`; keep compatibility wrappers and byte/type equality. |
| `carbon.backbones` runtime registry | KEEP, not consulted | Catalog pins are inert data; compiler performs no dynamic lookup or model construction. |
| `Strategy_Schema.md` v1.1 proposal and retired prototype code | REPLACE as authority | They remain non-authoritative design input and are not ported. |

The A7 identity extraction is a code-location repair, not a new identity. The
public A7-owned seam must preserve the exact header, binary framing,
ordering, signed-zero behavior, hash values, bounded capture behavior, and A7
golden tests. `StrategyHash` remains defined in `carbon.fees.model` and the
existing `carbon.fees.StrategyHash` remains the exact same class, never a
wrapper or subclass.

### 1.3 Package and dependency direction

The implementation owner is the new standard-library-only package
`carbon.construction`:

```text
carbon.construction
  -> carbon.schema.strategy
  -> carbon.authoring
  -> carbon.registry identity primitives
  -> carbon.fees.strategy_identity (A7-owned accepted snapshot/hash seam)

carbon.fees
  -/> carbon.construction
```

`carbon.schema`, `carbon.authoring`, `carbon.registry`, and `carbon.fees` must
not import `carbon.construction`. The explicit A7 Strategy-identity submodule
is the only permitted fees dependency; construction must not use fee policy,
the fee ledger, submission lifecycle, or A7 service/store APIs.
`carbon.construction` must not import backends, seeding, scoring, cards,
TrainEval, MCP, B-02C policy, or any optional dependency. No `pyproject.toml`
dependency change is authorized.

Python executes `carbon.fees.__init__` before an explicit fees submodule. The
implementation must therefore test the real transitive import graph and prove
that construction remains installable without optional dependencies. Existing
eager A7 root imports do not grant construction semantic use of cards,
scoring, seeding, submission services, or fee policy; any future lazy-root
refactor is outside B-02B unless required to keep the current core import
contract green.

---

## 2. Canonical identity and reference law

### 2.1 Reused primitives

Construction uses the exact A3/B-02A lowercase ASCII identifier, bounded
version token, strict NFC text, exact Boolean, signed/unsigned 64-bit integer,
finite binary64, positive-zero, tuple bound, and `sha256:<64 lowercase hex>`
rules. It uses B-02A canonical value encoders and tagged SHA-256 rather than
creating another scalar or hashing grammar.

B-02A canonical Float64 maps both zeros to positive zero, while the deployed A7
Strategy identity distinguishes their binary encodings. Therefore B-02B
rejects negative zero before canonical construction encoding. It never silently
normalizes negative zero, NaN, infinity, text, a unit, a version, or a value.

### 2.2 Construction document frame

Construction canonical documents use the profile
`carbon_construction_canonical_v1` and header
`carbon.construction.canonical.v1\0`. The header and closed record adapters are
B-02B domain separation; all scalar, tuple, record, nominal-ref, text, and
digest encodings reuse B-02A's exact implementation. Decoders reject unknown
fields, missing fields, wrong field order/schema, trailing bytes, noncanonical
values, subclasses, aliases, and digest mismatch before returning an object.

### 2.3 Long-lived authored references

`CandidateAssemblyContractRef` and `ParameterCatalogRef` are distinct exact,
frozen, slotted nominal types with these fields in this order:

```text
challenge_key
object_id
object_version
schema_version
canonicalization_profile
content_digest
```

They reuse B-02A top-level-ref field grammar but are not added to B-02A's
closed six-kind registry. Their `content_digest` covers the referenced
object's complete canonical bytes, excluding the digest itself.

### 2.4 Resolved references

`TrainingSamplingPolicyRef` and `ResolvedConstructionPlanRef` are distinct
exact, frozen, slotted content references with:

```text
challenge_key
schema_version
canonicalization_profile
content_digest
```

Resolved values have no mutable logical name, latest pointer, or independent
version. Their digest is their exact identity. Historical exact refs remain
valid when their bytes and dependencies are available; “stale” never means
merely “not latest.”

### 2.5 Acyclic content graph

The exact dependency graph is acyclic:

```text
CandidateAssemblyContract
  -> B-02A authoring refs + fixed backbone/component/pin declarations

ParameterCatalog
  -> CandidateAssemblyContractRef + TrainingSupportContractRef
  -> CompilerIdentity + catalog entries

ResolvedTrainingSamplingPolicy
  -> ParameterCatalogRef + TrainingSupportContractRef + resolved training bindings

ResolvedConstructionPlan
  -> all exact inputs + TrainingSamplingPolicyRef + resolved bindings/resources
```

The assembly contract never points back to the catalog. No object may omit a
semantic dependency to break a content-hash cycle.

---

## 3. Exact identity and pin types

### 3.1 `CompilerIdentity`

`CompilerIdentity` is exact, frozen, and slotted:

```text
compiler_id
compiler_version
implementation_digest
construction_schema_version
canonicalization_profile
```

It identifies executable compiler semantics, not a filesystem location or a
runtime-discovered build. All values are supplied by trusted composition and
validated with the reused identifier/version/digest grammar. A semantic change
requires a new compiler version and implementation digest.

### 3.2 Pins

`ImplementationPin`, `EnvironmentPin`, and `DependencyPin` are separate exact
nominal types. Each contains its canonical id, version, and tagged content
digest. `EnvironmentPin` describes an immutable construction environment only;
it is not MQ-008 reproducibility qualification. Pins contain no path, URI,
package resolver instruction, import string, command, or network endpoint.

`InterfacePin` contains an interface id, version, content digest, and exact
input/output direction. It gives component slots closed structural I/O
identity without claiming physical correctness.

### 3.3 Closed canonical nested-schema registry

This subsection closes every nested value that enters a construction digest.
Field order is exactly the displayed order. Every record is exact, frozen,
slotted, subclass-rejecting, bounded, and defensively reconstructed. Every
union is encoded as the displayed exact tag plus its displayed payload record;
there is no null/omitted-field shorthand. Set-like tuples sort by complete
canonical item bytes and reject duplicates. Ordered semantic tuples retain
their declared order.

The notation `PinnedOwnerRef<K>` means the exact B-02A runtime nominal owner-ref
class for kind `K`, not a generic runtime ref or caller object, with an exact
`ChallengeScope` equal to the enclosing construction object's `ChallengeKey`.
`PortableOwnerRef<K>` means that same exact nominal class with either that
matching `ChallengeScope` or exact `GlobalScope`. No other Challenge scope is
ever admitted. Portable scope is permitted only at the fields explicitly
marked below: unit refs, source-provenance refs, origin-evidence refs, and the
capability-issued origin-composition audit ref. Every other owner ref is
Challenge-scoped. Nested constructors receive the expected Challenge key as
validation context but do not duplicate it into canonical bytes.

#### Pins, targets, and values

```text
ImplementationPin
  implementation_id
  implementation_version
  content_digest

EnvironmentPin
  environment_id
  environment_version
  content_digest

DependencyPin
  dependency_id
  dependency_version
  content_digest

InterfacePin
  interface_id
  interface_version
  content_digest
  direction: INPUT | OUTPUT

ConsumerTarget
  consumer_id
  field_id

SurfaceValue
  value_type: BOOL | INT64 | UINT64 | FLOAT64 |
              CANONICAL_CHOICE | BACKBONE_SELECTOR | COMPONENT_SELECTOR
  value: exact scalar selected by value_type
```

`SurfaceValue` always retains its type tag. `BOOL` accepts only exact Boolean;
the integer tags reject Boolean; `FLOAT64` rejects non-finite and negative
zero; choice/selector tags accept only exact canonical ids.

#### Units, domains, requirements, and ownership

```text
UnitBinding =
  NOT_APPLICABLE
    reason_ref: PinnedOwnerRef<applicability_reason>
  | BOUND
    unit_ref: PortableOwnerRef<unit>

SurfaceDomain =
  BOOLEAN
    allowed_values: nonempty canonical set tuple[bool]
  | INT64_RANGE
    minimum
    maximum
  | UINT64_RANGE
    minimum
    maximum
  | FLOAT64_RANGE
    minimum
    maximum
    lower_inclusive: bool
    upper_inclusive: bool
  | CHOICE
    allowed_ids: nonempty canonical set tuple[canonical id]

SurfaceRequirement =
  REQUIRED
  | EXPLICIT_DEFAULT
    default_value: SurfaceValue

SemanticOwnerBinding =
  ASSEMBLY
    local_target_id
    authority_ref: PinnedOwnerRef<scientific_authority>
  | TRAINING_SUPPORT
    semantic_clause_ref: PinnedOwnerRef<semantic_clause>
    authority_ref: PinnedOwnerRef<policy_authority>

CatalogEntryLifecycle =
  ACTIVE
  | RETIRED_FOR_NEW_COMPILATION
    reason_ref: PinnedOwnerRef<applicability_reason>
    supersession_ref: PinnedOwnerRef<semantic_equivalence>
```

Range construction requires `minimum <= maximum`; Float64 bounds themselves
must be finite positive-zero-canonical values. A value must match both the
entry's exact `SurfaceValueType` and domain variant.

#### Applicability, compatibility, and catalog-role bindings

```text
ApplicabilityRule =
  ALWAYS
    applicability_ref: PinnedOwnerRef<applicability>
  | WHEN_SURFACE_IN
    applicability_ref: PinnedOwnerRef<applicability>
    selector_surface_id
    allowed_values: nonempty canonical set tuple[SurfaceValue]
    not_applicable_reason_ref: PinnedOwnerRef<applicability_reason>

CompatibilityCell =
  VALUE
    value: SurfaceValue
  | NOT_APPLICABLE

CompatibilityRule
  rule_id
  surface_ids: nonempty ordered tuple[canonical surface id]
  allowed_rows: nonempty canonical set tuple[tuple[CompatibilityCell, ...]]
  semantic_clause_ref: PinnedOwnerRef<semantic_clause>

TrainingRandomnessPurpose
  purpose_id
  role_key_label

TrainingLeverBinding =
  NOT_APPLICABLE
    reason_ref: PinnedOwnerRef<applicability_reason>
  | BOUND
    kind: SAMPLING | CURRICULUM | AUGMENTATION
    executable_semantics_ref: PinnedOwnerRef<semantic_clause>
    randomness_purposes:
      canonical set tuple[TrainingRandomnessPurpose]

ComponentSelectionBinding =
  NOT_APPLICABLE
    reason_ref: PinnedOwnerRef<applicability_reason>
  | BOUND
    slot_id
    role: ComponentRole
```

Compatibility row arity must equal `surface_ids` length. Every value cell must
match the named entry's type/domain. All ids/rows are unique. Applicability
selectors and catalog dependencies form one acyclic graph.

#### Static resource records

```text
StaticResourceDimension
  dimension_id
  unit_ref: PortableOwnerRef<unit>

ResourceLookupCase
  selector_value: SurfaceValue
  quantity: UInt64

StaticResourceContribution =
  FIXED
    dimension_id
    unit_ref: PortableOwnerRef<unit>
    quantity: UInt64
    impact_tags: canonical set tuple[canonical id]
  | DISCRETE_LOOKUP
    dimension_id
    unit_ref: PortableOwnerRef<unit>
    selector_surface_id
    cases: nonempty canonical set tuple[ResourceLookupCase]
    impact_tags: canonical set tuple[canonical id]

StaticResourceRequirement
  dimension_id
  unit_ref: PortableOwnerRef<unit>
  quantity: UInt64
  contributing_source_ids: nonempty canonical set tuple[canonical id]
  impact_tags: canonical set tuple[canonical id]
```

Lookup selector values are unique and match the named surface domain. A
contribution dimension/unit must exactly equal one assembly-owned dimension.

#### Construction provenance

```text
ConstructionProvenance =
  FIXTURE
    fixture_registration_ref: PinnedOwnerRef<fixture_registration>
    source_provenance_refs:
      nonempty canonical set tuple[PortableOwnerRef<provenance>]
    origin_evidence_refs:
      nonempty canonical set tuple[PortableOwnerRef<authoring_origin_evidence>]
  | REGISTERED
    authoring_registration_ref: PinnedOwnerRef<authoring_registration>
    source_provenance_refs:
      nonempty canonical set tuple[PortableOwnerRef<provenance>]
    origin_evidence_refs:
      nonempty canonical set tuple[PortableOwnerRef<authoring_origin_evidence>]

AuthoringOriginBinding
  graph_origin: FIXTURE_DERIVED | REGISTERED_GRAPH
  graph_fingerprint
  root_ref: exact B-02A TopLevelObjectRef
  dependency_refs: canonical set tuple[exact B-02A TopLevelObjectRef]
  origin_evidence_refs:
    nonempty canonical set tuple[PortableOwnerRef<authoring_origin_evidence>]
  composition_audit_ref: PortableOwnerRef<origin_composition_audit>
```

`AuthoringOriginBinding` can be constructed only from the exact
capability-issued B-02A `AuthoringGraphOrigin`. `DRAFT_OR_UNRESOLVED` has no
binding variant and therefore rejects.

#### Backbone and component records

```text
BackboneSurfaceContract
  surface_id = "strategy_backbone"
  consumer_target: ConsumerTarget
  options: nonempty canonical set tuple[BackboneOption]

BackboneOption
  selector_token
  backbone_id
  backbone_version
  content_digest
  implementation_pin: ImplementationPin
  environment_pin: EnvironmentPin
  dependency_pins: canonical set tuple[DependencyPin]
  input_interface_pin: InterfacePin(direction=INPUT)
  output_interface_pin: InterfacePin(direction=OUTPUT)
  applicability_ref: PinnedOwnerRef<applicability>
  assumption_refs: canonical set tuple[PinnedOwnerRef<semantic_clause>]
  limitation_refs: canonical set tuple[PinnedOwnerRef<restriction>]
  static_resource_contributions:
    canonical set tuple[StaticResourceContribution]
  resource_impact_tags: canonical set tuple[canonical id]

ComponentSlotContract
  slot_id
  selector_surface_id
  role: ComponentRole
  consumer_target: ConsumerTarget
  input_interface_pin: InterfacePin(direction=INPUT)
  output_interface_pin: InterfacePin(direction=OUTPUT)
  state_policy: STATELESS | FIXED_STATE | TRAINABLE_STATE
  side_effect_policy: NONE
  trainability_boundary: FIXED | TRAINABLE_REGISTERED_STATE
  applicability_ref: PinnedOwnerRef<applicability>
  options: nonempty canonical set tuple[RegisteredComponentOption]
  fallback_policy: FAIL_CLOSED

RegisteredComponentOption
  selector_token
  component_id
  component_version
  content_digest
  role: ComponentRole
  consumer_target: ConsumerTarget
  input_interface_pin: InterfacePin(direction=INPUT)
  output_interface_pin: InterfacePin(direction=OUTPUT)
  state_policy: STATELESS | FIXED_STATE | TRAINABLE_STATE
  side_effect_policy: NONE
  trainability_boundary: FIXED | TRAINABLE_REGISTERED_STATE
  implementation_pin: ImplementationPin
  environment_pin: EnvironmentPin
  dependency_pins: canonical set tuple[DependencyPin]
  applicability_ref: PinnedOwnerRef<applicability>
  assumption_refs: canonical set tuple[PinnedOwnerRef<semantic_clause>]
  limitation_refs: canonical set tuple[PinnedOwnerRef<restriction>]
  static_resource_contributions:
    canonical set tuple[StaticResourceContribution]
  resource_impact_tags: canonical set tuple[canonical id]
  public_falsification_refs: canonical set tuple[PinnedOwnerRef<audit_evidence>]
```

Option role, consumer, interfaces, state, side effects, and trainability must
exactly equal their owning slot. Selector tokens are unique within and across
the assembly's selector surfaces.

#### Catalog entries and resolved records

```text
ParameterCatalogEntry
  surface_id
  input_source: TOP_LEVEL_BACKBONE | PARAMETER_KEY
  consumer_target: ConsumerTarget
  value_type: SurfaceValueType
  unit_binding: UnitBinding
  domain: SurfaceDomain
  dependency_surface_ids: canonical set tuple[canonical surface id]
  applicability: ApplicabilityRule
  requirement: SurfaceRequirement
  compatibility_rule_ids: canonical set tuple[canonical rule id]
  static_resource_contributions:
    canonical set tuple[StaticResourceContribution]
  resource_impact_tags: canonical set tuple[canonical id]
  public_outcome_family_tags: canonical set tuple[canonical id]
  semantic_owner_binding: SemanticOwnerBinding
  lifecycle: CatalogEntryLifecycle
  training_lever_binding: TrainingLeverBinding
  component_slot_binding: ComponentSelectionBinding

ResolvedSurface =
  SELECTED
    surface_id
    consumer_target: ConsumerTarget
    value: SurfaceValue
  | DEFAULTED
    surface_id
    consumer_target: ConsumerTarget
    value: SurfaceValue
  | NOT_APPLICABLE
    surface_id
    consumer_target: ConsumerTarget
    reason_ref: PinnedOwnerRef<applicability_reason>

ResolvedBackboneBinding
  surface_id
  selector_token
  backbone_id
  backbone_version
  content_digest
  implementation_pin: ImplementationPin
  environment_pin: EnvironmentPin
  dependency_pins: canonical set tuple[DependencyPin]
  input_interface_pin: InterfacePin(direction=INPUT)
  output_interface_pin: InterfacePin(direction=OUTPUT)
  applicability_ref: PinnedOwnerRef<applicability>
  assumption_refs: canonical set tuple[PinnedOwnerRef<semantic_clause>]
  limitation_refs: canonical set tuple[PinnedOwnerRef<restriction>]

ResolvedComponentBinding
  slot_id
  selector_surface_id
  selector_token
  component_id
  component_version
  content_digest
  role: ComponentRole
  consumer_target: ConsumerTarget
  input_interface_pin: InterfacePin(direction=INPUT)
  output_interface_pin: InterfacePin(direction=OUTPUT)
  state_policy: STATELESS | FIXED_STATE | TRAINABLE_STATE
  side_effect_policy: NONE
  trainability_boundary: FIXED | TRAINABLE_REGISTERED_STATE
  implementation_pin: ImplementationPin
  environment_pin: EnvironmentPin
  dependency_pins: canonical set tuple[DependencyPin]
  applicability_ref: PinnedOwnerRef<applicability>
  assumption_refs: canonical set tuple[PinnedOwnerRef<semantic_clause>]
  limitation_refs: canonical set tuple[PinnedOwnerRef<restriction>]
  public_falsification_refs: canonical set tuple[PinnedOwnerRef<audit_evidence>]

ResolvedTrainingBinding
  surface_id
  kind: SAMPLING | CURRICULUM | AUGMENTATION
  resolved_value: SurfaceValue
  executable_semantics_ref: PinnedOwnerRef<semantic_clause>
```

The plan stores `resolved_surfaces` in canonical surface-id order,
`resolved_components` in canonical slot-id order, and
`satisfied_compatibility_rule_ids` as a canonical set tuple. Exact resources
are stored separately, so resolved backbone/component records do not duplicate
or recompute their quantities.

---

## 4. Candidate assembly contract

### 4.1 `CandidateAssemblyContract`

This exact, frozen, slotted long-lived object contains:

```text
object_kind = "candidate_assembly_contract"
schema_version = "1.0"
canonicalization_profile = "carbon_construction_canonical_v1"
challenge_key
object_id
object_version
physical_system_ref: PhysicalSystemSpecRef
candidate_output_ref: CandidateOutputContractRef
training_support_ref: TrainingSupportContractRef
backbone_surface: BackboneSurfaceContract
component_slots: tuple[ComponentSlotContract, ...]
resource_dimensions: tuple[StaticResourceDimension, ...]
dependency_pins: tuple[DependencyPin, ...]
environment_pins: tuple[EnvironmentPin, ...]
provenance: ConstructionProvenance
unknown_or_invalid_policy = REJECT
```

The object owns one fixed outer workflow. It exposes selector surfaces but no
participant node, edge, callback, callable, graph, import, or fallback graph.
Its Challenge and all B-02A refs must match exactly. Tuples are bounded,
canonical, duplicate-free, and defensively reconstructed.

### 4.2 Backbone binding

`BackboneSurfaceContract` fixes `surface_id = "strategy_backbone"` and maps
each allowed exact A2 backbone token to one `BackboneOption`. Each option binds:

```text
backbone_id and version
implementation_pin
environment_pin
dependency_pins
input_interface_pin
output_interface_pin
applicability_ref
assumption_refs
limitations
static_resource_contributions
resource_impact_tags
```

The Strategy supplies only the already-A2-valid token. It cannot supply a
module, class, registry entry, implementation ref, or pin.

---

## 5. Closed structural and learned components

### 5.1 Roles

`ComponentRole` is the exact closed v1 enum:

```text
WARM_START
PRECONDITIONER_ACTION
COARSE_CORRECTION
RESIDUAL_CORRECTION
SUBDOMAIN_OPERATOR
NONLINEAR_INITIAL_GUESS
```

The roles are never aliases. Matching I/O shapes do not permit substitution
between roles.

### 5.2 Slot and option contracts

Each `ComponentSlotContract` binds:

```text
slot_id
selector_surface_id
role: ComponentRole
consumer_id
input_interface_pin
output_interface_pin
state_policy: STATELESS | FIXED_STATE | TRAINABLE_STATE
side_effect_policy: NONE
trainability_boundary: FIXED | TRAINABLE_REGISTERED_STATE
applicability_ref
options: tuple[RegisteredComponentOption, ...]
fallback_policy: FAIL_CLOSED
```

Each `RegisteredComponentOption` binds its selector token, component id and
version, content digest, same exact role, consumer, interfaces, state and
side-effect policy, fixed/trainable boundary, implementation pin, environment
pin, dependency pins, applicability and physical-assumption refs, limitations,
static resource contributions, resource-impact tags, and public falsification
refs. Strategy selects an allowed token only. It never supplies one of those
refs or changes the slot.

Fixture v1 permits only `FAIL_CLOSED`. A later fallback is a new assembly
contract version and must bind an exact assembly-owned option, trigger,
acceptance ref, and all resulting plan semantics. Silent fallback and
participant-selected fallback are forbidden.

Component identity, labels, unit tests, falsification refs, or fixture success
have construction authority only. They cannot satisfy measurements or gates,
enter score, qualify the assembled solver/model, activate LIVE, or substitute
for later product/system qualification.

---

## 6. Parameter catalog

### 6.1 `ParameterCatalog`

The exact, frozen, slotted long-lived catalog contains:

```text
object_kind = "parameter_catalog"
schema_version = "1.0"
canonicalization_profile = "carbon_construction_canonical_v1"
challenge_key
object_id
object_version
candidate_assembly_ref: CandidateAssemblyContractRef
training_support_ref: TrainingSupportContractRef
compiler_identity: CompilerIdentity
entries: tuple[ParameterCatalogEntry, ...]
compatibility_rules: tuple[CompatibilityRule, ...]
provenance: ConstructionProvenance
unknown_or_invalid_policy = REJECT
```

The catalog is Challenge-bound and compiler-bound. Construction validates all
defaults, domains, dependencies, target uniqueness, component selectors,
resource dimensions, and rules before it can produce a ref.

Catalog projection onto its exact assembly is bijective and closed:

- exactly one entry has `input_source = TOP_LEVEL_BACKBONE`; it has
  `surface_id = "strategy_backbone"`, the assembly backbone surface's exact
  `consumer_target`, `value_type = BACKBONE_SELECTOR`, `UnitBinding =
  NOT_APPLICABLE`, `requirement = REQUIRED`, no dependencies, `ALWAYS`
  applicability, `SemanticOwnerBinding = ASSEMBLY` targeting that backbone
  surface, and exact `CHOICE.allowed_ids` equality with the assembly's complete
  set of backbone option `selector_token` values;
- each assembly component slot has exactly one selector entry whose
  `input_source = PARAMETER_KEY`, `surface_id`, `consumer_target`,
  `value_type = COMPONENT_SELECTOR`, `SemanticOwnerBinding = ASSEMBLY` with
  `local_target_id = slot_id`, and
  `ComponentSelectionBinding.BOUND(slot_id, role)` exactly equal that slot,
  and whose `CHOICE.allowed_ids` exactly equal the complete selector-token set
  of that slot's options;
- no other entry may use `TOP_LEVEL_BACKBONE`, `BACKBONE_SELECTOR`, or
  `COMPONENT_SELECTOR`; no `PARAMETER_KEY` entry may use
  `"strategy_backbone"`; and every component-bound non-selector entry names
  one existing slot with the exact role and consumer id; and
- the assembly's backbone and component selector surface ids are pairwise
  distinct, every option token is unique within its owning surface, and no
  catalog or assembly surface may be omitted, duplicated, aliased, or widened.

These equalities are verified against the digest-verified assembly before the
catalog can be canonicalized. Catalog data cannot redefine an assembly-owned
selector, option set, role, consumer, interface, pin, or fallback.

### 6.2 Executable Strategy projection

For B-02B v1, `Strategy.parameters` has executable meaning only when it is an
exact built-in dictionary of:

```text
canonical surface_id -> exact scalar SurfaceValue
```

Allowed scalar kinds are exact Boolean, Int64, UInt64, finite Float64 with
negative zero forbidden, canonical text enum, and component-selector token.
Lists, nested dictionaries, null, subclasses, objects, and every other leaf are
rejected at compile time even when A2 correctly accepts them as inert JSON.
This narrowing does not change A2 validation.

An exact dictionary cannot contain duplicate materialized keys. Duplicate raw
JSON member rejection belongs to the B-07S parser boundary. B-02B rejects
duplicate catalog surface ids, duplicate consumer targets, selector
collisions, declared security-fold aliases, and any attempt to map two surfaces
to one semantic target before constructing a lookup map. Ordinary distinct
canonical ids are not aliases merely because one is a textual prefix of the
other.

### 6.3 `ParameterCatalogEntry`

Each exact entry binds:

```text
surface_id
input_source: TOP_LEVEL_BACKBONE | PARAMETER_KEY
consumer_target: ConsumerTarget
value_type: SurfaceValueType
unit_binding: UnitBinding
domain: SurfaceDomain
dependency_surface_ids: canonical set tuple[canonical surface id]
applicability: ApplicabilityRule
requirement: SurfaceRequirement
compatibility_rule_ids: canonical set tuple[canonical rule id]
static_resource_contributions:
  canonical set tuple[StaticResourceContribution]
resource_impact_tags: canonical set tuple[canonical id]
public_outcome_family_tags: canonical set tuple[canonical id]
semantic_owner_binding: SemanticOwnerBinding
lifecycle: CatalogEntryLifecycle
training_lever_binding: TrainingLeverBinding
component_slot_binding: ComponentSelectionBinding
```

`SurfaceDomain` is a closed nominal union of exact Boolean choice, bounded
Int64, bounded UInt64, bounded finite Float64, and finite canonical text-choice
domains. Domains do not coerce, normalize, clamp, round, convert units, call a
predicate, or inspect the environment. Fixture catalogs should prefer finite
discrete domains. Real domains and units remain human-reserved.

`public_outcome_family_tags` are construction-only canonical labels used for
public impact/falsification routing; they contain no metric, threshold, gate,
score, or evidence result and cannot enter those authorities.

`TrainingLeverBinding` contains exactly one closed `SAMPLING`, `CURRICULUM`, or
`AUGMENTATION` kind, one exact executable-semantics ref, and bounded abstract
purpose ids/role-key labels. `ComponentSelectionBinding` names one exact
assembly `slot_id` and required `ComponentRole`. Entry construction enforces
that these bindings agree with the assembly slot, exact role, and consumer id;
only the one selector entry for that slot may have `value_type =
COMPONENT_SELECTOR`. Unauthorized consumer kinds structurally carry
`NOT_APPLICABLE`.

### 6.4 Defaults, applicability, and consumption

Every surface resolves in canonical `surface_id` order to exactly one of:

```text
SELECTED(exact value)
DEFAULTED(exact value)
NOT_APPLICABLE(exact rule ref)
```

`ApplicabilityRule` is the exact closed union `ALWAYS(applicability_ref)` or
`WHEN_SURFACE_IN(applicability_ref, selector_surface_id, nonempty
allowed_values, not_applicable_reason_ref)`. A controlling surface must be an explicit dependency;
the dependency/applicability graph must be acyclic. The compiler evaluates it
in topological order with canonical `surface_id` tie-breaking.
`CompatibilityRule` contains its rule id, ordered surface ids, exact allowed
rows, and semantic-clause ref. Each row has exact domain values or the explicit
`NOT_APPLICABLE` cell. Construction validates row arity, cells, uniqueness,
and refs; the compiler never silently skips a rule or treats a missing
required/default value as not applicable.

There is no optional/unset state. Missing `REQUIRED` rejects. Omitted
`EXPLICIT_DEFAULT` materializes `DEFAULTED`, including origin and exact value,
in the plan and plan hash. Supplying a not-applicable surface rejects as unused
rather than discarding it. A default is literal catalog data, is validated at
catalog construction, and cannot be computed from another value or from the
environment.

Every supplied Strategy parameter must map to exactly one active applicable
entry and exactly one consumer target. Every applicable catalog entry must
resolve or reject. Full resolution precedes compatibility evaluation, so input
insertion order cannot alter semantics. Compatibility uses only a closed exact
table of allowed value tuples over named surfaces; no callable or free-form
predicate is accepted.

### 6.5 Stale and downgrade law

New compilation rejects a catalog, assembly, compiler, dependency,
environment, component, or authoring ref when its exact Challenge, version,
kind, digest, lifecycle, or expected pin does not match. It rejects entries
marked `RETIRED_FOR_NEW_COMPILATION`. It never orders opaque versions, performs
a “latest” lookup, silently upgrades/downgrades, or mutates a historical
object. Exact historical objects remain loadable and verifiable.

---

## 7. Resolved training sampling policy (`R_strategy`)

### 7.1 Exact object

`ResolvedTrainingSamplingPolicy` is exact, frozen, slotted, Challenge-bound,
and contains:

```text
object_kind = "resolved_training_sampling_policy"
schema_version = "1.0"
canonicalization_profile = "carbon_construction_canonical_v1"
challenge_key
training_support_ref: TrainingSupportContractRef
catalog_ref: ParameterCatalogRef
policy_state: BASE_NO_OVERRIDE | RESOLVED_OVERRIDES
bindings: tuple[ResolvedTrainingBinding, ...]
randomness_purposes: tuple[TrainingRandomnessPurpose, ...]
```

`ResolvedTrainingBinding` has a closed kind of `SAMPLING`, `CURRICULUM`, or
`AUGMENTATION`; it binds the resolved surface/value and an exact registered
executable-semantics ref. `TrainingRandomnessPurpose` contains only an abstract
canonical purpose id and registered role-key label. It contains no A4 entropy
domain, entropy context, seed, nonce, RNG state, draw/case identity, ordering,
or realized sample.

The compiler emits `BASE_NO_OVERRIDE` with empty `bindings` and
`randomness_purposes` when no training surface is selected, and
`RESOLVED_OVERRIDES` with nonempty bindings otherwise. The purpose tuple is the
canonical duplicate-free union of the selected bindings' registered purposes.
Absence never means an implicit policy.

### 7.2 Structural prohibitions

The object model has no field capable of carrying target population `P`,
official `SamplingPlan`/proposal `Q`, evidence weighting `w`, EVAL/STRESS role,
official case or protected identity, reference policy/evidence, measurement,
gate, score, qualification, data path/URI, custom/raw dataset, loader, or
participant seed material. Such inputs are rejected before policy creation.

Nominal execution contexts separately select their authorized entropy domain
and derive actual draws through A4. The same policy bytes do not imply shared
entropy authority.

---

## 8. Static resource metadata

### 8.1 Closed metadata

`StaticResourceDimension` binds a canonical dimension id and exact unit ref.
`StaticResourceContribution` is one of:

```text
FIXED(nonnegative UInt64 quantity)
DISCRETE_LOOKUP(tuple[exact SurfaceValue -> nonnegative UInt64 quantity])
```

Contributions attach only to registered entries, backbone options, and
component options. `StaticResourceRequirement` in the plan contains the exact
dimension, unit, checked aggregate quantity, contributing surface/component
ids, and canonical impact tags. Aggregation is checked UInt64 addition in
canonical source order. Overflow, unknown dimension, missing lookup case, or a
dimension/unit conflict rejects compilation.

The exact `CandidateAssemblyContract.resource_dimensions` tuple is the sole
B-02B registry of valid dimensions/units for that assembly. A contribution
cannot create a dimension by mentioning it.

### 8.2 Non-ownership

Resource output contains no ceiling, fit/admit/deny result, forecast
calibration, price, quota, queue, scheduling choice, kill rule, runtime
measurement, success probability, or policy receipt. B-02C may consume the
exact metadata but may not reinterpret a surface, change a resolved value,
replace a pin, clamp a quantity, or mutate plan identity.

---

## 9. Resolved construction plan

`ResolvedConstructionPlan` is exact, frozen, slotted, inert, and contains:

```text
object_kind = "resolved_construction_plan"
schema_version = "1.0"
canonicalization_profile = "carbon_construction_canonical_v1"
challenge_key
strategy_schema_version
strategy_hash: exact shared StrategyHash
authoring_origin_binding: AuthoringOriginBinding
physical_system_ref: PhysicalSystemSpecRef
candidate_output_ref: CandidateOutputContractRef
training_support_ref: TrainingSupportContractRef
candidate_assembly_ref: CandidateAssemblyContractRef
parameter_catalog_ref: ParameterCatalogRef
compiler_identity: CompilerIdentity
backbone_binding: ResolvedBackboneBinding
resolved_surfaces: tuple[ResolvedSurface, ...]
satisfied_compatibility_rule_ids: canonical set tuple[canonical rule id]
resolved_components: tuple[ResolvedComponentBinding, ...]
training_sampling_policy_ref: TrainingSamplingPolicyRef
dependency_pins: canonical set tuple[DependencyPin]
environment_pins: canonical set tuple[EnvironmentPin]
implementation_pins: canonical set tuple[ImplementationPin]
static_resource_requirements: tuple[StaticResourceRequirement, ...]
resource_impact_tags: canonical set tuple[canonical id]
assembly_provenance: ConstructionProvenance
catalog_provenance: ConstructionProvenance
authority_marker = CONSTRUCTION_ONLY_NOT_QUALIFICATION
```

The plan binds all semantic input identities, selected values, explicit
defaults and their origin, not-applicable rules, compatibility result inputs,
exact component roles/options/interfaces/pins, the full `R_strategy` ref,
static resources, the exact authoring-origin binding, and the separate tagged
assembly/catalog construction provenance. It does not retain caller-owned
mutable dictionaries/lists or a participant-controlled reference.

The compiler accepts only a capability-issued exact B-02A
`AuthoringGraphOrigin` or a verified immutable resolver that returns one. It
verifies that the physical-system, candidate-output, and training-support refs
are exact members of the complete loaded graph, recomputes the existing B-02A
`scientific_authoring_graph_fingerprint`, and derives the closed
`AuthoringOriginBinding` from that capability. `FIXTURE_DERIVED` is accepted
only with the fixture authority marker; `DRAFT_OR_UNRESOLVED` rejects. B-02B
never constructs, upgrades, or forges an authoring origin.

The plan contains no practice/official mode, consumer identity, entropy
domain, seed/draw, runtime policy verdict, scientific evidence, gate, score,
qualification, publication, or LIVE field. Canonical bytes produce exactly one
`ResolvedConstructionPlanRef`.

`ConstructionProvenance` is the exact tagged union defined in section 3.3. The
plan retains separate assembly and catalog provenance values; it never
collapses unequal origins into one caller assertion. Registered provenance
still gains no qualification from B-02B.

---

## 10. Compiler boundary and deterministic order

### 10.1 Public operation

The public `compile_strategy(...)` operation receives a hostile Strategy value
and exact trusted `ChallengeKey`, assembly object/ref, catalog object/ref,
B-02A referenced objects or a verified immutable resolver, and exact compiler
identity. It returns exactly one of:

```text
CompileAccepted(
  training_policy,
  training_policy_ref,
  construction_plan,
  construction_plan_ref,
)

CompileRejected(issues: nonempty tuple[CompileIssue, ...])
```

No exception carrying participant data, partial policy, partial plan, mutated
catalog, or fallback value is a supported result.

### 10.2 Shared bounded Strategy identity

`carbon.fees.strategy_identity.identify_strategy` exposes, rather than
reimplements, the deployed A7-owned algorithm. It captures one detached bounded topology-preserving
snapshot, calls A2 `dry_validate` exactly once on that snapshot, rejects
mutation, aliases/cycles after validation, invalid UTF-8, resource overrun, or
identity mismatch, and emits the exact existing `StrategyHash`. The public
limits are representation-safety bounds, not B-02C operational policy.

The public function accepts A7's existing exact `SubmissionResourceLimits` and
returns an owned accepted snapshot plus the exact `StrategyHash`; B-02B compiles
only that snapshot and never trusts a caller-supplied hash. Existing private
A7 function names remain delegating compatibility shims where needed for its
tests and callers. All old A7 hash vectors, root exports, failure mapping, and
public service behavior must remain unchanged.

### 10.3 Compilation order

The compiler performs this exact order:

1. bounded shared Strategy capture, A2 validation, and identity;
2. exact Strategy family id versus supplied `ChallengeKey`;
3. object/ref/digest/Challenge/compiler/lifecycle/pin verification before use;
4. top-level backbone and flat parameter projection;
5. exact type, domain, required/default, and applicability resolution;
6. closed dependency and compatibility evaluation;
7. exact component option, role, interface, state, side-effect, and pin binding;
8. explicit `R_strategy` materialization and reference;
9. checked static-resource aggregation;
10. plan materialization, canonical encoding, digest, and reference.

The compiler performs no import, filesystem, network, clock, environment,
package-registry, runtime-backbone-registry, deserialization, reflection,
callable, evaluator, scorer, gate, or resource-policy operation.

### 10.4 Typed rejection

`CompileIssue` is exact, frozen, slotted, and contains only a closed code, safe
canonical path, and fixed non-echoing message. Paths may include trusted
catalog ids but never an arbitrary hostile unknown key; unknown-key failures
use the safe aggregate path `/parameters`. `CompileRejected` contains a
nonempty deterministic tuple sorted by safe path and code. Errors never use
`repr`, echo a hostile key/value/ref, expose a secret, or contain dynamic
diagnostics.

The exact closed v1 code literals are:

```text
strategy.invalid
strategy.identity_invalid
strategy.challenge_mismatch
strategy.backbone_mismatch
strategy.parameter_shape_invalid
strategy.negative_zero
reference.type_mismatch
reference.kind_mismatch
reference.challenge_mismatch
reference.schema_mismatch
reference.version_mismatch
reference.digest_mismatch
reference.pin_mismatch
reference.retired_for_new_compilation
compiler.identity_mismatch
compiler.version_unsupported
catalog.duplicate_surface
catalog.consumer_collision
catalog.selector_collision
catalog.rule_invalid
catalog.dependency_cycle
parameter.unknown
parameter.unused
parameter.missing_required
parameter.type_mismatch
parameter.bool_int_confusion
parameter.domain_mismatch
parameter.coercion_forbidden
parameter.default_invalid
parameter.not_applicable
parameter.dependency_unsatisfied
parameter.unsupported_combination
component.unknown
component.role_confusion
component.interface_mismatch
component.pin_mismatch
component.fallback_forbidden
component.graph_forbidden
training_support.mismatch
training_policy.binding_invalid
training_policy.forbidden_authority
training_policy.randomness_forbidden
resource.dimension_unknown
resource.unit_conflict
resource.lookup_missing
resource.overflow
resource.policy_forbidden
authority.origin_invalid
capability.forbidden
canonicalization.failed
compile.internal_failure
```

No literal alias or additional public code is permitted in v1. Any
unclassified failure maps to fixed `compile.internal_failure`; it never returns a
partial success.

---

## 11. Security and authority boundary

Strategy and every participant-controlled value are hostile. B-02B rejects
imports, source, scripts, executables, commands, arbitrary graphs, arbitrary
dependencies, packages, paths, URIs, repositories, network endpoints,
callbacks, callables, reflection, serialized blobs, pickle, model artifacts,
checkpoints, custom/raw datasets, loaders, participant seeds/nonces/RNG state,
official case/draw selectors, `P`, `Q`, `w`, EVAL/STRESS controls, references,
measurements, scorers, gates, thresholds, weights, qualification, disclosure,
and unregistered composition.

The compiler emits inert declarative data only and does not execute a
backbone/component or claim sandbox qualification. MQ-015 security review,
MQ-008 backend qualification, real parameters/components under MQ-024, and
measurement admissibility under MQ-005 remain unresolved owner work.

Only closed non-authoritative fixtures may be used in B-02B tests. No fixture
catalog, backbone, component, range, unit, training policy, environment, or
successful test may become a production default or LIVE authority.

---

## 12. Nominal consumer parity

Compilation is consumer-context-neutral. Two fixture-only nominal consumers,
one representing a later practice role and one an official-shaped role,
receive fresh immutable copies of the exact same plan bytes and
`ResolvedConstructionPlanRef`. Their context types and entropy authorities
remain different and outside plan identity. This proves only construction
semantic parity; it does not implement B-07F, official execution, shared
randomness, scientific comparability, or production qualification.

---

## 13. Required implementation and verification

The bounded implementation must include:

- exact models, nominal refs, hostile-input-safe constructors, canonical
  adapters/decoders, digest verification, and mutation isolation;
- the public shared Strategy identity extraction with unchanged A7 golden
  identity and service behavior;
- catalog validation, strict flat projection, full resolution, closed
  compatibility, component binding, explicit `R_strategy`, resources, plan,
  and typed rejection;
- no shipped real/default/production catalog; fixtures live only in tests;
- focused model/ref, canonicalization, compiler, security, resource,
  component, export/dependency, code-authority, installed-wheel, and
  outside-tree tests;
- A2, A7, B-02A, registry, package, and constitutional-invariant regressions;
- exact-head CI, independent Greptile review, repair of every valid finding,
  zero unresolved Greptile threads, and rereview after any material tree
  change.

At minimum tests cover every positive and negative case listed in the B-02B
ticket: exact Strategy-to-plan, determinism across insertion order and fresh
processes, exact default identity, catalog confusion/collision/downgrade,
cross-Challenge/version/digest/pin mismatch, unknown/ignored/non-applicable
parameters, coercion and bool/int/float separation, negative zero and hostile
values, silent clamp/default prohibition, all six component roles and role
confusion, arbitrary-graph and gate-bypass rejection, training-support and
`P`/`Q`/`w`/seed/entropy escape rejection, static-resource aggregation and
policy non-ownership, canonical tamper/trailing/digest checks, mutation and
alias isolation, nominal consumer parity, package direction, installed wheel,
outside-tree imports, and code authority.

---

## 14. Decision crosswalk

The durable decision record is `.agent/DECISIONS.md`:

| Decision | Selected law |
|---|---|
| B-02B-D1 | `carbon.construction` ownership and exact public A7-owned Strategy-identity seam |
| B-02B-D2 | exact nominal refs, full Challenge binding, and acyclic canonical graph |
| B-02B-D3 | flat strict catalog surfaces, explicit defaults/applicability, and exactly-once consumption |
| B-02B-D4 | `R_strategy` isolation and context-owned randomness |
| B-02B-D5 | fixed assembly and closed six-role component compatibility |
| B-02B-D6 | exact policy-free static resource metadata |
| B-02B-D7 | complete plan identity and consumer-context-neutral parity |
| B-02B-D8 | hostile-input, non-echoing, all-or-nothing compiler boundary |

These are agent-authorized bounded engineering decisions under the delegated
decision protocol. Notification does not confer human-owned scientific,
security, resource-policy, qualification, LIVE, or production authority.

---

## 15. Maturity and change rule

Normal merge of the exact independently reviewed contract tree followed by
successful exact-main CI may establish `SPECIFIED = YES` and
`RATIFIED_ENGINEERING_CONTRACT = YES` only for this bounded contract.
Implementation, testing, and Greptile maturity require the separate B-02B
implementation candidate. Implementation merge remains a separate
authorization.

Any semantic change requires a prospective object/compiler/schema version,
updated exact tests, and the owning ticket. Historical identities are never
silently reinterpreted. B-02C and every later ticket remain untouched.
