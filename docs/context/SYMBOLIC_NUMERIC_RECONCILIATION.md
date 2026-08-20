# Symbolic-Numeric Integration Reconciliation

**Status:** active reconciliation on `design/symbolic-numeric-integration`; planning/context only.  
**Base reviewed:** `main` at `c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a` (A3 closed).  
**Design inputs:** `Design_Specs/Physical_System_Representation.md`, `docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md`, `docs/context/SYMBOLIC_NUMERIC_IMPLEMENTATION_MAP.md`.  
**Authority preserved:** domain owners in `Design_Specs/Build_Out.md`; this file does not reopen completed tickets or override semantic owners.

---

## 1. First reconciliation finding — A1, A2, A3 are complete

Repository history establishes:

- **A1:** closed after reviewed registry repair / CI closure;
- **A2:** closed after reviewed strategy-schema merge;
- **A3:** closed after reviewed Challenge-registry merge and closeout.

Therefore the symbolic-numeric integration must **not** be described as work to fold into A1-A3. Those tickets are historical completed boundaries.

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

### Required follow-up review

Before ratification, verify that:

1. `physical_system_spec` is an acceptable canonical artifact identifier under A3 syntax;
2. an extra non-qualification artifact does not alter LIVE eligibility;
3. storing the binding does not cause miner-visible path/digest disclosure outside existing allow-lists;
4. historical records without the artifact remain valid;
5. no symbolic runtime dependency is introduced.

---

## 3. Revised near-term hook names

The original `SN-A1`, `SN-A2`, `SN-A3` labels are too easy to confuse with completed Build-Out tickets A1-A3. Reconciliation should rename them before merge.

Proposed names:

### SN-H1 — Challenge physical-system artifact binding

Use the completed A3 generic artifact map to optionally bind one exact `PhysicalSystemSpec` artifact.

**No A3 schema migration. No score change. No LIVE state change.**

### SN-H2 — Evidence provenance propagation

Natural owner: **A6 Card store**, which is not yet complete at the reviewed base.

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

Therefore the first Burgers `PhysicalSystemSpec` may safely encode the first four scientific facts and the governing relation only where supported by the authoritative generator/scientific source. It must **not** invent viscosity ranges, initial-condition distributions, boundary conditions, conservation-law semantics, or dimensionless-regime thresholds that the current source has not yet ratified.

---

## 6. Reconciliation result so far

### KEEP

- A1-A3 completed implementations;
- A3 strict exact-version Challenge identity;
- A3 generic content-addressed artifact binding;
- current Wave A sequencing;
- all scoring / seed / disclosure / qualification invariants.

### WRAP

- use A3 `artifacts` to bind an optional `physical_system_spec` rather than modifying the A3 top-level schema;
- propagate the binding into A6 internal evidence when A6 is implemented.

### REPAIR / EXTEND

- rename symbolic-numeric near-term hook labels to avoid collision with completed A1-A3;
- revise the implementation map to reflect the actual completed state;
- prototype Burgers semantics with explicit unknown/HUMAN_INPUT fields where science is not yet ratified.

### REPLACE

- none.

---

## 7. Immediate next reconciliation steps

1. Audit A3 serialization/gate tests to confirm a non-qualification `physical_system_spec` artifact is behaviorally inert.
2. Reconcile the proposed `PhysicalSystemSpec` identity rules with A3 tagged SHA-256 artifact semantics; avoid duplicate identity authorities.
3. Read A6 ticket/spec before defining evidence propagation fields.
4. Read generator/envelope/dossier sources before drafting the Burgers prototype.
5. Update `SYMBOLIC_NUMERIC_IMPLEMENTATION_MAP.md` from SN-A1/A2/A3 to SN-H1/H2/H3 and mark A1-A3 complete.
6. Only after those checks decide whether any P0 code change is justified at all.

---

## 8. Current recommendation

The strongest reconciliation path is now narrower than the original draft:

> **Do not reopen A3. Reuse its generic content-addressed artifact binding as the physical-semantic attachment point. Let A6 preserve that identity later. Keep the Burgers semantic object authoring-only until the scientific source fields are qualified.**

This achieves future-proofing with almost no P0 architectural disturbance.
