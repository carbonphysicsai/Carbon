# Evidence Archive, Custody, and Availability Contract

**Version:** 0.1 future implementation contract
**Status:** `SPECIFIED`; no runtime, storage, retention, security, qualification, or deployment is implemented
**Decision:** `OWNER-EVIDENCE-RESEARCH-01`
**Tickets:** `C-EA0` through `C-EA3`, then `E-EA4`, `E-EA5`, and `E-EA7`

This companion owns archive and custody semantics for the canonical
[Evidence Intelligence and Agent Research System](./Evidence_Intelligence_and_Agent_Research.md).
Existing submission, execution, measurement, receipt, and scientific-result owners keep their identities and authority. This document defines how their evidence is retained and made eligible for later uses; it does not create a second result lifecycle.

## 1. Admission and attempt accounting

Durable admission occurs before dispatch and binds an `ArchiveEntry` identity to the source-owned submission, challenge, candidate, execution, and attempt identities. Every admitted attempt is accounted for, including retries, interruptions, cancellations, authorized early stops, scientific failures, and generator, reference, measurement, validator, or infrastructure failures. A retry is a new attempt linked to its predecessor; it never overwrites it.

The archive records five independent axes:

| Axis | Examples | Rule |
|---|---|---|
| execution disposition | not dispatched, running, interrupted, cancelled, early-stopped, completed | operational history, not scientific merit |
| scientific result | pass/fail/contested/indeterminate or source-owned result | only the existing scientific owner may set it |
| evidence completeness | complete, partial with explicit missingness, unavailable | missing required evidence blocks finalization; it is not a physics failure |
| qualification origin | fixture, practice, non-official, official-unqualified, qualified contract/version | preserves the status at creation |
| named-use eligibility | internal audit, Landscape study, release candidate, commercial use | assessed separately for each use and version |

Evidence from real executions is captured before qualification and retains its original non-qualified status. Eligibility for learning, publication, or sale never controls whether an admitted record must be retained. Local unsubmitted miner experiments are outside mandatory collection unless the miner explicitly enters an authorized Carbon research workflow.

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

## 3. Conceptual objects

These are documentation objects, not a ratified runtime wire schema.

| Object | Identity/version | Completeness and lifecycle | Consumers |
|---|---|---|---|
| `ArchiveEntry` | stable entry ID; immutable source/attempt binding; appended state events | admitted before dispatch; terminal only after source result and required archive acknowledgement reconcile | orchestration, audit, recovery |
| `ArtifactManifest` | content-addressed manifest version bound to entry and capture profile | distinguishes expected, written, verified, missing, intentionally absent, withdrawn, and unavailable-key artifacts | archive, restore, use assessment |
| `EvidenceUseAssessment` | entry/snapshot + named use + policy version | records permissions, qualification origin, completeness, dependence and decision; reassessed on correction/withdrawal | Landscape, release, commercial workflows |
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

## 5. Proposed starting persistence design

The proposed first implementation is PostgreSQL for catalogue/state/outbox metadata plus encrypted, versioned object storage for immutable artifacts. Deployment topology, provider, regions, key custody, replication, recovery objectives, and retention durations remain human owner decisions.

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

Conflicting content at an existing immutable identity fails closed. Duplicate identical writes converge. Object availability is rechecked before acknowledgement; downstream projections cannot upgrade the acknowledgement.

## 6. Recovery and fault model

`C-EA0` must declare the faults the selected durability profile covers. At minimum, implementation tests address crashes before/after every stage above, duplicated or reordered events, catalogue/object disagreement, conflicting writes, lost workers, unavailable artifacts, unavailable or rotated keys, vanished validator services, restore from backup, partial-region/service outage, safe orphan reconciliation, queue saturation, and storage backpressure.

No design may claim universal losslessness. Values destroyed before their first acknowledged durable boundary cannot be recovered. The declared fault model must name acknowledgement points, correlated-failure exclusions, restore integrity checks, and the behavior when guarantees cannot be met. Non-essential consumers degrade first. If required evidence cannot be durably acknowledged, official finalization fails closed through the existing lifecycle.

Orphans are quarantined until source identity and authorization reconcile; they are never guessed into an official result. Recovery cannot rerun science merely to repair metadata, and restored records cannot silently acquire a new scientific or qualification status.

## 7. Retention, deletion, and correction

Retention classes distinguish long-lived scientific records, required original artifacts, optional debug material, and rebuildable derivatives. No duration is set here. Storage pressure may reject or backpressure new work according to approved policy but cannot silently delete required evidence.

Approved deletion, legal hold, withdrawal, and permission revocation propagate to catalogues, objects, replicas, derivatives, summaries, embeddings, clusters, exports, and backup-restoration procedures. Where a record must remain for an approved legal/scientific reason, access and use may still be withdrawn. A factual correction appends a new assertion and impact state; it does not rewrite the historical result.

## 8. Acceptance ceiling

Archive acceptance requires attempt reconciliation, manifest verification, restore/fault drills, idempotent effects, availability checks, and proof that required evidence failure blocks finalization without becoming candidate scientific failure. Human owners approve the durability profile, retention/legal/IP policy, security acceptance, production deployment, and any LIVE use.
