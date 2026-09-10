# Evidence Archive, Custody, and Availability Contract

**Version:** 1.0 evidence-capture contract
**Status:** `SPECIFIED`; C-EA0 contract cases are tested, but no runtime,
storage, retention, security, qualification, acknowledgement, or deployment is
implemented
**Decisions:** `OWNER-EVIDENCE-RESEARCH-01`, `C-EA0-D1`
**Tickets:** `C-EA0` through `C-EA3`, then `E-EA4`, `E-EA5`, and `E-EA7`

This companion owns archive and custody semantics for the canonical
[Evidence Intelligence and Agent Research System](./Evidence_Intelligence_and_Agent_Research.md).
Existing submission, execution, measurement, receipt, and scientific-result owners keep their identities and authority. This document defines how their evidence is retained and made eligible for later uses; it does not create a second result lifecycle.

The normative, machine-checkable contract vocabulary and cases are
[`evidence_capture_contract_v1.json`](./evidence_capture_contract_v1.json).
That file is a design contract and test vector, not a runtime wire schema. C-EA1
must deliberately implement and version its runtime representation rather than
deserializing this document as operational authority.

## 0. C-EA0 decision and authority ceiling

`C-EA0-D1` selects one closed contract with these rules:

1. admission and archive identity precede dispatch;
2. each physical execution attempt has one immutable entry, so retries and
   re-executions link to new entries rather than overwrite history;
3. execution, science, completeness, qualification origin, and named-use
   eligibility remain independent axes;
4. acknowledgement is positive evidence about the exact approved durability
   profile, manifest, catalogue commit, current object availability, and custody
   policy—not a generic stored flag;
5. absent required evidence blocks source-owned finalization without becoming
   candidate physics failure; and
6. every unapproved policy value remains `HUMAN_INPUT` and prevents a real
   `VERIFIED_DURABLE` acknowledgement.

This decision is reversible by replacing the versioned contract prospectively.
Historical entries and acknowledgements retain their original contract and
policy references. It does not select a database, object store, cloud, region,
key manager, retention duration, recovery objective, required scientific
artifact, or legal/IP entitlement.

## 1. Admission and attempt accounting

Durable admission occurs before dispatch and binds an `ArchiveEntry` identity to the source-owned submission, challenge, candidate, execution, and attempt identities. Every admitted attempt is accounted for, including retries, interruptions, cancellations, authorized early stops, scientific failures, and generator, reference, measurement, validator, or infrastructure failures. A retry or independently authorized re-execution is a new attempt linked to its predecessor; it never overwrites it. An exact duplicate admission converges on the existing identity; conflicting content at that identity is rejected.

The archive records five independent axes:

| Axis | Examples | Rule |
|---|---|---|
| execution disposition | `NOT_DISPATCHED`, `RUNNING`, `INTERRUPTED`, `CANCELLED`, `EARLY_STOPPED`, `COMPLETED` | operational history, not scientific merit |
| scientific result | `NOT_AVAILABLE` or an immutable `SOURCE_RESULT_REF` | only the existing scientific owner may create or supersede the referenced value |
| evidence completeness | `UNASSESSED`, `COMPLETE`, `PARTIAL_EXPLICIT_MISSINGNESS`, `UNAVAILABLE` | missing required evidence blocks finalization; it is not a physics failure |
| qualification origin | fixture, practice, non-official, official-unqualified, or an exact qualified-contract reference | preserves source maturity and never upgrades it |
| named-use eligibility | `UNASSESSED`, `ELIGIBLE`, `INELIGIBLE`, `BLOCKED_UNKNOWN` per named use and policy version | capture, use, release, and commercial entitlement are separate decisions |

Evidence from real executions is captured before qualification and retains its original non-qualified status. Eligibility for learning, publication, or sale never controls whether an admitted record must be retained. Local unsubmitted miner experiments are outside mandatory collection unless the miner explicitly enters an authorized Carbon research workflow.

The closed initial named-use vocabulary is `INTERNAL_AUDIT`,
`LANDSCAPE_RESEARCH`, `RELEASE_CANDIDATE`, `EXTERNAL_RELEASE`, and
`COMMERCIAL_USE`. Naming a use does not approve it. Each assessment binds its
rights/use policy version and independently returns eligible, ineligible,
blocked-unknown, or unassessed.

## 2. Capture profile

`EvidenceCaptureProfile` is a versioned, Challenge/execution-class-bound contract. It references rather than replaces source-owned objects and declares required, optional-debug, and rebuildable-derivative fields. At minimum it covers:

- exact submitted strategy bytes or canonical identity and the resolved construction plan;
- versioned Challenge, generator, reference, measurement, Score Pack, execution-environment, compiler, and policy contracts;
- physical context, coordinate/frame meaning, units, resolution, horizon, boundary/initial-condition identity, and resource observations;
- original required measurements, predictions, references, checkpoints, logs or traces required by the governing evidence contract, and artifact availability;
- executed and unexecuted coverage, stopping/censoring reason, retries and reconstruction repeats;
- shared-case, shared-reference, ancestry, checkpoint, and other dependence links;
- known selection reasons/probabilities and whether guidance exposure was observed, absent, or unknown.

Unknown is a first-class value. The archive must not infer an unobserved exposure, execution, independence relationship, or selection probability.

Each artifact rule is conditional on source stage and disposition. A field that
is not required for a declared disposition may be `INTENTIONALLY_ABSENT`; a
required field may not use that value to obtain completeness. `COMPLETE` means
every conditionally required artifact is `VERIFIED`. `WRITTEN` is not verified,
and `EXPECTED`, `MISSING`, `WITHDRAWN`, or `UNAVAILABLE_KEY` on a required
artifact prevents acknowledgement. Optional-debug and rebuildable-derivative
loss remains visible but does not become required evidence by implication.

## 3. Conceptual objects

These are ratified C-EA0 documentation objects, not a runtime wire schema.

| Object | Identity/version | Completeness and lifecycle | Consumers |
|---|---|---|---|
| `EvidenceCaptureProfile` | content identity + schema version + Challenge/execution-class binding | declares conditional required, optional-debug, and rebuildable-derivative artifact rules plus approved policy refs | admission, archive, audit |
| `ArchiveEntry` | stable entry ID; immutable source/execution/attempt binding; `INITIAL`, `RETRY_OF`, or `REEXECUTION_OF`; appended events | admitted before dispatch; reconciles source result and acknowledgement without owning either | orchestration, audit, recovery |
| `ArtifactManifest` | content-addressed manifest version bound to entry and capture profile | distinguishes `EXPECTED`, `WRITTEN`, `VERIFIED`, `MISSING`, `INTENTIONALLY_ABSENT`, `WITHDRAWN`, and `UNAVAILABLE_KEY` | archive, restore, use assessment |
| `ArchiveAcknowledgement` | entry + manifest + capture/durability/custody policy identities | `VERIFIED_DURABLE` only after every positive condition in §5; otherwise not acknowledged, pending, or rejected | source-owned finalization gate |
| `EvidenceUseAssessment` | entry/snapshot + named use + rights/use policy version | records permission, qualification origin, completeness, dependence, selection/exposure knowledge and decision; reassessed on correction/withdrawal | Landscape, release, commercial workflows |
| `ResearchSnapshot` | immutable query/cohort definition + source cutoff + versions | reproducible scientific view with executed/unexecuted masks, missingness, lineage and permissions | Wave E research only |

Example shape only:

```json
{
  "documentation_example": true,
  "archive_entry_id": "synthetic-entry-01",
  "attempt_relation": {"kind": "retry_of", "entry": "synthetic-entry-00"},
  "execution_disposition": "INTERRUPTED",
  "scientific_result_ref": null,
  "evidence_completeness": "PARTIAL_EXPLICIT_MISSINGNESS",
  "qualification_origin": "OFFICIAL_UNQUALIFIED",
  "use_assessments": []
}
```

## 4. Custody zones and entitlement separation

Custody zones are explicit: protected vault; controlled internal scientific views; operational views; tenant-isolated research stores; approved release stores. Movement between zones requires a recorded policy decision and produces a new projection or release artifact. A pointer, hash, signature, catalogue row, or successful upload call is neither proof of durable availability nor proof of scientific truth.

Capture, internal scientific use, external release, and commercial entitlement are four different decisions. Release eligibility does not imply paid entitlement; paid entitlement cannot declassify protected official information.

The closed custody-zone vocabulary is `PROTECTED_VAULT`,
`CONTROLLED_INTERNAL_SCIENTIFIC_VIEW`, `OPERATIONAL_VIEW`,
`TENANT_ISOLATED_RESEARCH_STORE`, and `APPROVED_RELEASE_STORE`. These names
describe authority boundaries, not deployed locations. A move produces a new
projection or release artifact and requires a versioned human-approved policy
decision. Content identity, deduplication, or possession in one zone supplies
no permission to enter another.

## 5. Proposed starting persistence design

The proposed first implementation is PostgreSQL for catalogue/state/outbox metadata plus encrypted, versioned object storage for immutable artifacts. C-EA0 does not approve that proposal for deployment. Deployment topology, provider, regions, key custody, replication, recovery objectives, and retention durations remain human owner decisions.

The protocol does not assume a distributed transaction:

```text
durable admission
-> bounded stage journal
-> immutable object writes
-> verify bytes and manifest
-> catalogue transaction + transactional outbox
-> archive acknowledgement
-> existing orchestration may finalize
-> consumers apply outbox effects idempotently
```

Workers retain a bounded local spool/checkpoint until the selected durable boundary acknowledges it. Protected payloads use the authorized capture channel, never general logs. Admission reserves enough storage for the declared capture profile; under pressure Carbon backpressures or reduces future admission rather than thinning completed evidence.

Conflicting content at an existing immutable identity fails closed. Duplicate identical writes converge. `VERIFIED_DURABLE` requires all of the following at the same versioned boundary:

- approved durability-, capture-, and custody-policy references;
- immutable source/execution/attempt bindings;
- all conditionally required artifacts byte- and identity-verified;
- the exact manifest content identity verified;
- the catalogue transaction committed;
- current object availability verified through the approved custody path.

`NOT_ACKNOWLEDGED`, `PENDING`, and `REJECTED` all block required real
finalization. A downstream projection cannot create or upgrade acknowledgement.
A later loss, withdrawal, key outage, correction, or policy change appends a new
availability/use state and invokes source-owned incident or finalization policy;
it never silently rewrites the historical acknowledgement or scientific result.

## 6. Recovery and fault model

`C-EA0` must declare the faults the selected durability profile covers. At minimum, implementation tests address crashes before/after every stage above, duplicated or reordered events, catalogue/object disagreement, conflicting writes, lost workers, unavailable artifacts, unavailable or rotated keys, vanished validator services, restore from backup, partial-region/service outage, safe orphan reconciliation, queue saturation, and storage backpressure.

No design may claim universal losslessness. Values destroyed before their first acknowledged durable boundary cannot be recovered when no acknowledged copy exists. `VERIFIED_DURABLE` promises only the named approved profile, never universal survival. The declared fault model must name acknowledgement points, correlated-failure exclusions, restore integrity checks, and the behavior when guarantees cannot be met. Non-essential consumers degrade first. If required evidence cannot be durably acknowledged, official finalization fails closed through the existing lifecycle.

Orphans are quarantined until source identity and authorization reconcile; they are never guessed into an official result. Recovery cannot rerun science merely to repair metadata, and restored records cannot silently acquire a new scientific or qualification status.

Backfilled legacy material is an attributable import with original maturity, missingness, permissions, and signature gaps. Migration never fabricates a measurement, signature, source right, or qualification. Tamper-evident history, least-privilege workload identities, scoped keys, controlled human audit, bounded non-secret telemetry, safe serializers, closed fields, validated object paths, and separate fixture/production namespaces are future acceptance requirements.

## 7. Retention, deletion, and correction

Retention classes distinguish long-lived scientific records, required original artifacts, optional debug material, and rebuildable derivatives. No duration is set here. Storage pressure may reject or backpressure new work according to approved policy but cannot silently delete required evidence.

Approved deletion, legal hold, withdrawal, and permission revocation propagate to catalogues, objects, replicas, derivatives, summaries, embeddings, clusters, exports, and backup-restoration procedures. Where a record must remain for an approved legal/scientific reason, access and use may still be withdrawn. A factual correction appends a new assertion and impact state; it does not rewrite the historical result.

Deduplication is allowed only within compatible permission/encryption scopes and cannot expose cross-tenant content existence through hashes, hit/miss behavior, or timing. It reduces bytes, never the number of attempt records.

## 8. Reserved decision register

The contract is implementable because each unsupported value is an explicit
input rather than an implicit default. Until its owner supplies and versions the
value, the affected real path is unavailable.

| Reserved input | Owner route | Current value | Fail-closed effect | First consumer |
|---|---|---|---|---|
| durability fault profile and correlated-failure coverage | Operations + data/security | `HUMAN_INPUT` | no real durability acknowledgement | C-EA1 |
| Challenge/execution-class required-artifact profile | scientific + execution/result owners | `HUMAN_INPUT` | real capture profile cannot be admitted | C-EA1/C-EA2 |
| retention durations, deletion and legal-hold policy | legal/IP + data governance | `HUMAN_INPUT` | no production retention/deletion action | C-EA1 |
| named-use, reuse, release and commercial-rights policy | legal/IP + business + scientific publication | `HUMAN_INPUT` | assessment is `BLOCKED_UNKNOWN` or `INELIGIBLE` | C-EA1/E-EA4+ |
| custody zones, access principals, encryption and key policy | security + data owner | `HUMAN_INPUT` | no protected-zone deployment or acknowledgement | C-EA1 |
| provider, regions, replication and deployment topology | Operations + security | `HUMAN_INPUT` | no production deployment | C-EA1 |
| capacity reservation and backpressure policy | Operations | `HUMAN_INPUT` | no real admission under capacity authority | C-EA1/C-EA2 |
| recovery objectives, exclusions and restore acceptance | Operations/DR + security | `HUMAN_INPUT` | no recovery qualification | C-EA3 |
| security qualification | security owner | `HUMAN_INPUT` | no security/production/LIVE maturity | C-EA3/Wave D |

Fixture-only contract tests may populate visibly synthetic policy references.
They cannot acknowledge real evidence or satisfy any reserved decision.

## 9. Contract-case acceptance

The v1 case matrix covers all six execution dispositions and separately covers:

- retry linkage without overwrite;
- strategy, generator, reference, measurement, validator, infrastructure and
  unknown failure-class accounting without collapsing source ownership;
- missing required, withdrawn, and key-unavailable artifacts;
- unknown selection probability and guidance exposure;
- shared-case and ancestry dependence without an independence inference;
- source result preservation on early stop and completion;
- absence of an approved durability profile; and
- exclusion of local unsubmitted experiments from mandatory capture.

The five axes are deliberately allowed to form combinations that look unusual:
a cancelled or interrupted attempt may have complete evidence and a valid
durability acknowledgement, while a completed scientific result may have
incomplete evidence and be unable to finalize. This is the required separation,
not a contradiction.

## 10. Acceptance ceiling

C-EA0 acceptance ratifies only this exact v1 vocabulary, invariants, reserved-input register, and contract cases. It earns `SPECIFIED` and tested-contract status only. Archive implementation and archive acceptance require C-EA1 through C-EA3 attempt reconciliation, manifest verification, restore/fault drills, idempotent effects, availability checks, and proof that required evidence failure blocks finalization without becoming candidate scientific failure. Human owners still approve the durability profile, required artifacts, retention/legal/IP policy, custody/security acceptance, production deployment, recovery objectives, and any LIVE use.
