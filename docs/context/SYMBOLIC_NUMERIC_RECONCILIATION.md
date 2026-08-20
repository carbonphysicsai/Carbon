# Symbolic-Numeric Integration Reconciliation

**Status:** active reconciliation on `design/symbolic-numeric-integration`; planning/context only.  
**Base reviewed:** `main` at `c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a` (A3 closed).  
**Design inputs:** `Design_Specs/Physical_System_Representation.md`, `docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md`, `docs/context/SYMBOLIC_NUMERIC_IMPLEMENTATION_MAP.md`.  
**Authority preserved:** domain owners in `Design_Specs/Build_Out.md`; this file does not reopen completed tickets or override semantic owners.

---

## 1. First reconciliation finding — A1, A2, A3 are complete

Repository history and `.agent/WAVE.md` establish:

- **A1:** done;
- **A2:** done;
- **A3:** done;
- **A4:** todo / not started at the reviewed `main`;
- **A5:** todo / not started at the reviewed `main`;
- **A6:** todo / not started at the reviewed `main`.

Therefore the symbolic-numeric integration must **not** be described as work to fold into A1-A3. Those tickets are historical completed boundaries. A4 is the next ordinary Wave-A ticket.

The current next Wave-A sequencing remains governed by `Build_Out.md`; symbolic-numeric work must enter only through a new bounded extension or through later tickets that have not yet been implemented.

---

## 2. A3 already contains a suitable non-invasive binding mechanism

The completed A3 `ChallengeRecord` is strict about top-level fields and exact-version identity, but already contains:

```text
artifacts: Mapping[str, ArtifactBinding]
```

where an `ArtifactBinding` carries a trusted-root-relative path and tagged digest. Artifact identifiers are generic canonical identifiers rather than a fixed closed list.

### Reconciliation consequence

Do **not** add these proposed top-level fields to the A3 record merely for future-proofing:

```text
physical_system_spec_id
physical_system_spec_version
physical_system_spec_hash
```

Doing so would unnecessarily migrate a completed strict schema.

Instead, the preferred P0-compatible design is to reserve a conventional artifact binding such as:

```text
artifacts["physical_system_spec"] = {
  path: <trusted-root-relative path>,
  digest: sha256:<...>
}
```

The bound artifact itself carries its semantic identity/version. The A3 digest binds the exact bytes. A3 remains responsible only for structural identity and bytes, not for interpreting the physical semantics.

This is a **WRAP**, not a REPAIR of A3.

The completed A3 LIVE gate re-hashes every declared artifact. Therefore absence of `physical_system_spec` can remain valid, but once a Challenge declares it, missing, malformed, or digest-mismatched bytes correctly make that exact Challenge ineligible for LIVE. This is fail-closed provenance, not a new scientific gate.

---

## 3. Revised near-term hook names

The original `SN-A1`, `SN-A2`, `SN-A3` labels are retired because they collide semantically with completed Build-Out tickets A1-A3.

### SN-H1 — Challenge physical-system artifact binding

Use the completed A3 generic artifact map to optionally bind one exact `PhysicalSystemSpec` artifact.

**No A3 schema migration. No score change. No ninth qualification slot.**

### SN-H2 — Evidence provenance propagation

Natural owner: **A6 Card store**, which is still `todo` at the reviewed base.

When an official Challenge binds a `physical_system_spec` artifact, internal evidence should preserve the immutable artifact identity/digest needed for future Landscape joins. Miner/public disclosure remains separately allow-listed.

### SN-H3 — Burgers semantic prototype

Authoring-only SciML work. Create a manually inspectable Burgers `PhysicalSystemSpec` using only facts established by current Carbon scientific sources. Where the current sources defer numeric envelope values to later generator/Score-Pack artifacts, use explicit `HUMAN_INPUT` / unresolved fields rather than inventing science.

This prototype must not become a runtime dependency.

---

## 4. Reconciliation against current P0 doctrine

The integration is compatible with current `Build_Out.md` if it obeys these limits:

- completed A1-A3 remain closed;
- A4+ sequencing is not displaced;
- `Scoring.md` remains sole scoring authority;
- Challenge science remains human-qualified;
- no symbolic package is added to validator/miner runtime;
- no new required LIVE qualification slot is introduced;
- missing `PhysicalSystemSpec` remains valid during P0;
- fixture / mock / official isolation is unchanged;
- physical metadata cannot contain official realized draws or seed material.

This matches the existing project doctrine that P0 may receive compatible schema/provenance hooks while post-P0 intelligence machinery remains deferred.

---

## 5. Burgers source reconciliation

`POC_Burgers_FNO.md` currently establishes the following usable semantic facts:

- system: 1D viscous Burgers;
- initial model class: FNO-1d;
- operator map: initial condition → solution at final time;
- procedural train/eval/stress data with role-separated seeds;
- candidate physics checks include finite output, conservation, residual ceiling, and boundary-condition checking if used;
- numeric envelope/schema are delegated to in-repo generator / Score Pack artifacts when implemented.

Therefore the first Burgers `PhysicalSystemSpec` may safely encode the established physical/system facts and the governing relation only where supported by the authoritative scientific source. It must **not** invent viscosity ranges, initial-condition distributions, boundary conditions, conservation-law semantics, or dimensionless-regime thresholds that the current source has not yet ratified.

---

## 6. A4 reconciliation — seeding is a secrecy boundary, not a semantic carrier

A4 is **not complete**. Its ticket is narrowly scoped to seed-domain separation and leakage tests:

```text
mock
official_train
official_eval
official_stress
reference
dossier
```

A4 must guarantee that official seed material and realized draw identifiers do not leak to miner-visible surfaces.

### Symbolic-numeric consequence

`PhysicalSystemSpec` should **not** enter seed derivation. Physical-system identity should not alter the canonical seed-domain contract, role separation, or master-secret derivation unless a future protocol revision explicitly says so.

The useful A4 interaction is negative/invariant-only:

- a `PhysicalSystemSpec` may describe public envelope semantics;
- it must not contain master secrets, official seeds, draw IDs, or reconstruction-sensitive realized exam state;
- leakage tests should eventually treat physical-semantic metadata as another surface that must be safe-by-construction;
- no `PhysicalSystemSpec` field should be used as a covert path around mock/official domain separation.

**Recommendation:** do not add symbolic-numeric implementation scope to A4. Preserve A4 exactly; later A12/integration tests can assert that physical metadata respects A4's leakage invariants.

---

## 7. A5 reconciliation — scoring must remain semantically downstream and independent

A5 is **not complete**. Its ticket implements a deterministic scoring engine and fixture Score Pack. The ticket explicitly requires:

- weights to live in the Score Pack, not the engine;
- hard gates to fail closed;
- forbidden inputs such as prior similarity, `estimate`/`light_*`, fees, and mock-only metrics to be rejected/ignored;
- production thresholds not to be invented;
- `HUMAN_INPUT` gates not to silently pass.

`Scoring.md` is the sole mathematical authority, and current standards require all scientific thresholds to be Score-Pack-bound and dossier-calibrated.

### Symbolic-numeric consequence

A5 should **not** parse or interpret `PhysicalSystemSpec` in order to score a model. The official scoring dependency remains:

```text
qualified generator / reference realization
        ↓
metrics + gate inputs
        ↓
registered Score Pack
        ↓
ScoreEngine
```

A future symbolic authoring tool may help propose candidate residuals, invariants, or regime features, but those become score-bearing only after the existing human-qualified path converts them into explicit metrics/gates in the registered Score Pack.

**Required invariant:**

```text
PhysicalSystemSpec ─X─> ScoreEngine authority
```

There is no direct path from symbolic structure to threshold, gate status, weight, or `S_combined`.

**Recommendation:** do not expand A5's implementation scope. Add only future integration tests proving that extra physical-semantic provenance cannot change a score when metrics and Score Pack are unchanged.

---

## 8. Generator / dossier / envelope reconciliation — this is the true semantic owner path

The generator documents already contain most of the scientific semantics that `PhysicalSystemSpec` is meant to structure.

`Generator_Creation.md` requires, before LIVE, explicit physics family/dimension, operating envelope, exclusions, conserved quantities/failure modes, stress taxonomy, reference rank, and calibrated acceptance evidence. Its standard build loop is:

```text
Envelope
  → generator code
  → reference backend
  → dossier
  → Score Pack bind
  → registry LIVE
```

`Generator_Validation.md` makes the Validation Dossier the public evidence pack for generator credibility, while `Evidence_and_Envelope_Standards.md` defines the envelope as the maximum defendable claim and requires thresholds to be traceable to reference uncertainty and engineering relevance.

### Reconciliation consequence

`PhysicalSystemSpec` should attach **upstream of generator implementation but downstream of human/domain science**:

```text
DOMAIN SCIENCE / PARTNER REQUIREMENTS
            ↓
     PhysicalSystemSpec
            ↓
       Envelope freeze
            ↓
 Generator / reference realization
            ↓
    Validation Dossier
            ↓
       Score Pack bind
            ↓
       Registry LIVE
```

But the existing semantic owners remain authoritative:

- envelope claims → `Evidence_and_Envelope_Standards.md`;
- generator construction → `Generator_Creation.md`;
- validation evidence → `Generator_Validation.md`;
- score math / gates → `Scoring.md`.

`PhysicalSystemSpec` should improve traceability among those objects; it should not become a parallel authority above them.

This also reveals the correct future dossier linkage:

```text
PhysicalSystemSpec relation / assumption
        ↓
reference realization
        ↓
validation evidence
        ↓
qualified metric definition
        ↓
Score Pack threshold / gate
```

That is the strongest scientific integration discovered so far.

---

## 9. A6 reconciliation — internal provenance is the first natural Wave-A propagation point

A6 is still `todo` and depends on A5. Its purpose is to persist the full `InternalResult` while returning only an allow-listed miner-facing `EvaluationCard`.

This is the first ordinary Wave-A ticket where physical-system provenance could naturally propagate without changing scientific behavior.

Recommended A6-compatible design direction:

- if the active Challenge binds `artifacts["physical_system_spec"]`, preserve the artifact digest and semantic identity/version in the full internal evidence object;
- do **not** expose trusted-root paths;
- do **not** add the physical spec to the default miner-facing allow-list merely because it exists;
- disclosure of public high-level physics family/envelope information remains a separate product/protocol choice;
- future Landscape ingestion should join on immutable internal identity, not on miner-facing summaries.

This should be reconciled again when A6's `InternalResult` shape is concretely implemented.

---

## 10. Updated KEEP / WRAP / REPAIR / REPLACE disposition

### KEEP

- A1-A3 completed implementations;
- A4 ticket scope and seed/leakage contract;
- A5 ticket scope and sole Score-Pack scoring path;
- A3 strict exact-version Challenge identity;
- A3 generic content-addressed artifact binding;
- generator/dossier/envelope scientific authority chain;
- current Wave A sequencing;
- all score / seed / disclosure / qualification invariants.

### WRAP

- use A3 `artifacts` to bind optional `physical_system_spec` bytes;
- use `PhysicalSystemSpec` as structured traceability around the existing generator/dossier/envelope path;
- propagate the immutable binding into A6 internal evidence when A6 is implemented.

### REPAIR / EXTEND

- symbolic-numeric planning docs only;
- later dossier traceability to structured relation/assumption identifiers;
- future Challenge-authoring tooling and Landscape physical context after evidence supports it.

### REPLACE

- none.

---

## 11. Immediate next reconciliation steps

1. Inspect current generator/envelope source files for the exact Burgers facts that can safely populate SN-H3.
2. Decide whether `PhysicalSystemSpec` should contain its own `content_hash` field or rely solely on A3's external artifact digest; avoid duplicate hash authority.
3. Reconcile public-vs-private status of the physical spec against current generator transparency rules and future disclosure controls.
4. Define the minimum Burgers prototype schema with explicit unresolved fields.
5. Add a design-only traceability table mapping each proposed `PhysicalSystemSpec` field to its existing semantic owner.
6. Only after those checks decide whether SN-H1 needs any code/test change before A6, or whether the existing A3 artifact map already provides everything required.

---

## 12. Current recommendation

The integration has become narrower and stronger:

> **Do not touch A4 or A5 for symbolic-numeric functionality. A4 protects secrecy; A5 consumes already-qualified metrics and Score Packs. Put physical semantics into the generator/dossier authoring chain, bind the exact artifact using completed A3 provenance, and let A6 preserve that identity internally when it is built.**

This keeps Carbon scientifically representation-aware without compromising the clean Wave-A protocol boundaries.
