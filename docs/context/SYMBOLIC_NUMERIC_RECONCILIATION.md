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

Do **not** add proposed top-level physical-system fields to A3 merely for future-proofing. The preferred P0-compatible design is:

```text
artifacts["physical_system_spec"] = {
  path: <trusted-root-relative path>,
  digest: sha256:<...>
}
```

The bound artifact carries semantic identity/version. A3 binds exact bytes. A3 remains responsible only for structural identity and bytes, not interpretation of physical semantics.

This is a **WRAP**, not a REPAIR of A3.

The completed A3 LIVE gate re-hashes every declared artifact. Absence of `physical_system_spec` remains valid, but once a Challenge declares it, missing or digest-mismatched bytes make that exact Challenge ineligible for LIVE. This is fail-closed provenance, not a new scientific gate.

### SN-H1 disposition

Reconciliation now concludes that **SN-H1 requires no A3 schema/code change**. `physical_system_spec` is a valid canonical artifact identifier under the existing model, and the generic artifact mechanism already provides the required content binding. Any additive proof should be an invariant/integration test later (preferably A12), not a reopening of A3.

---

## 3. Near-term hooks

### SN-H1 — Challenge physical-system artifact binding

Use the completed A3 generic artifact map to optionally bind one exact `PhysicalSystemSpec` artifact.

**No A3 schema migration. No score change. No ninth qualification slot.**

### SN-H2 — Evidence provenance propagation

Natural owner: **A6 Card store**, which is still `todo` at the reviewed base.

When an official Challenge binds a `physical_system_spec` artifact, internal evidence should preserve immutable artifact identity/digest needed for future Landscape joins. Miner/public disclosure remains separately allow-listed.

### SN-H3 — Burgers semantic prototype

Authoring-only SciML work. `Design_Specs/physical_system_specs/burgers1d_v0.prototype.yaml` now captures current implemented/configured Burgers semantics without becoming a runtime dependency.

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

---

## 5. Burgers source reconciliation

The implemented/configured P0 sources support a richer prototype than the older PoC summary alone implied. Current supported facts include:

- system label: 1D viscous Burgers;
- initial model class: FNO-1d;
- operator map: initial condition → solution at final time;
- periodic spatial domain on `[0,1)`;
- `nx=128`, `T=1.0` for normal mode;
- four-mode Fourier initial-condition family;
- train/eval viscosity `[1e-3,1e-2]`;
- stress viscosity configured as `[5e-4,5e-3]`;
- role-specific IC coefficient bounds `0.5/0.5/0.8`;
- procedural role-separated train/eval/stress data;
- IMEX Fourier reference realization with explicit advection, implicit viscosity, and 2/3 dealiasing.

The current Carbon sources still do not provide a separately ratified canonical symbolic equation string/AST for `PhysicalSystemSpec`; that field remains `HUMAN_INPUT` pending scientific-owner review.

### SN-BURGERS-001 — selected provisional value

The executable challenge config and `poc/generators/justification.py` disagree on the lower stress-viscosity bound:

```text
executable config:  5e-4
justification text: 3e-4
```

**Provisional design decision: use `5e-4`.**

Rationale:

1. `generate_batch()` reads the executable YAML and therefore samples from `5e-4` today.
2. A `PhysicalSystemSpec` should describe current realized Challenge behavior, not silently expand it.
3. Choosing `3e-4` only in semantic metadata would create a false claim about what the generator actually covers.
4. Changing runtime to `3e-4` would be a scientific/protocol change that should be explicit and versioned.

If the tech/science lead accepts this decision, the intended repair is to change the stale explanatory justification range to `5e-4`. If the lead instead decides `3e-4` is the scientifically intended boundary, the generator/config must be deliberately revised/versioned and the semantic representation should follow that change.

This is a design-branch decision pending technical review, not a silent mutation of `main`.

---

## 6. A4 reconciliation — seeding is a secrecy boundary, not a semantic carrier

A4 is not complete. `PhysicalSystemSpec` should not enter seed derivation. It may describe public envelope semantics but must not contain master secrets, official seeds, draw IDs, or reconstruction-sensitive realized exam state.

**Recommendation:** do not add symbolic-numeric implementation scope to A4. Preserve A4 exactly; later A12/integration tests can assert that physical metadata respects A4 leakage invariants.

---

## 7. A5 reconciliation — scoring remains downstream and independent

A5 is not complete. `PhysicalSystemSpec` must not be parsed by `ScoreEngine` to invent or alter a score. The scoring dependency remains:

```text
qualified generator / reference realization
        ↓
metrics + gate inputs
        ↓
registered Score Pack
        ↓
ScoreEngine
```

A future symbolic authoring tool may propose candidate residuals, invariants, or regime features, but they become score-bearing only after the existing human-qualified path converts them into explicit registered metrics/gates.

Required invariant:

```text
PhysicalSystemSpec ─X─> ScoreEngine authority
```

---

## 8. Generator / dossier / envelope reconciliation — true semantic owner path

`PhysicalSystemSpec` attaches upstream of generator implementation but downstream of human/domain science:

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

Existing semantic owners remain authoritative:

- envelope claims → `Evidence_and_Envelope_Standards.md`;
- generator construction → `Generator_Creation.md`;
- validation evidence → `Generator_Validation.md`;
- score math / gates → `Scoring.md`.

### First concrete dossier-traceability targets

The Burgers prototype now uses five test chains to determine whether structured semantics improve auditability:

1. **Periodic domain** → YAML config → Fourier reference realization → boundary/numerical evidence → possible future qualified BC metric.
2. **Viscosity role domains** → YAML config → role sampler → convergence/reference evidence across the envelope → stress-case semantics; Score Pack still owns any threshold.
3. **Fourier IC family** → YAML + `_sample_ics()` → procedural draws → distribution/reference credibility evidence → data/stress semantics.
4. **IMEX Fourier reference method** → `burgers_reference_solve()` → convergence/cross-reference evidence → dossier reference rank → downstream metric reference source.
5. **Conservation/residual candidates** → PoC scientific intent → future explicit metric implementation → applicability/calibration evidence → only then a registered Score-Pack gate/component.

The traceability table is maintained in `Design_Specs/physical_system_specs/README.md`. Missing dossier evidence remains explicitly missing; symbolic structure cannot fill it by implication.

---

## 9. A6 reconciliation — internal provenance is the first natural Wave-A propagation point

A6 remains `todo`. When it is implemented:

- if the active Challenge binds `artifacts["physical_system_spec"]`, preserve artifact digest plus semantic identity/version in the full internal evidence object;
- do not expose trusted-root paths;
- do not add the physical spec to the miner-facing allow-list by default;
- future Landscape joins use immutable internal identity rather than miner-facing summaries.

Reconcile again when the concrete `InternalResult` shape exists.

---

## 10. Identity authority decision

The design now locks:

```text
semantic identity = physical_system_spec_id + version
byte identity     = A3 ArtifactBinding.digest
```

Do **not** add a second canonical `content_hash` inside the spec. A3 already owns exact registered bytes; duplicate hash authority would create avoidable disagreement modes.

---

## 11. KEEP / WRAP / REPAIR / REPLACE

### KEEP

- A1-A3 completed implementations;
- A4 seed/leakage scope;
- A5 sole Score-Pack scoring path;
- A3 exact-version Challenge identity and generic artifact binding;
- generator/dossier/envelope scientific authority chain;
- current Wave-A sequencing and trust boundaries.

### WRAP

- bind optional `physical_system_spec` through A3 artifacts;
- use `PhysicalSystemSpec` for structured traceability around the generator/dossier/envelope path;
- later propagate immutable identity into A6 internal evidence.

### REPAIR / EXTEND

- repair `poc/generators/justification.py` stress bound to `5e-4` if the provisional decision is accepted;
- later dossier relation/assumption identifiers;
- future Challenge-authoring primitives and Landscape physical context after evidence supports them.

### REPLACE

- none.

---

## 12. Next reconciliation steps

1. Tech/science lead review of SN-BURGERS-001 (`5e-4` provisional decision).
2. Decide and ratify a canonical symbolic representation for the Burgers governing relation; do not import one silently.
3. Determine whether the current generator/reference evidence is sufficient to populate any dossier-traceability links now, or only define the required future evidence objects.
4. Reconcile public-vs-private status of the physical spec against generator transparency and A6/A9/A10 disclosure controls.
5. When A6 is designed, add the minimal internal provenance fields there rather than inventing an out-of-band evidence store.
6. At A12, add invariants proving physical metadata cannot change score or leak protected exam state.

---

## 13. Current recommendation

> **Preserve A4 and A5 as clean protocol boundaries. Use `5e-4` as the provisional Burgers stress lower bound because it matches current executable behavior. Treat the physical semantic layer as traceability around the generator/dossier chain, not as a new source of scientific or scoring authority.**

The integration is now concrete enough for tech-lead review without expanding P0 runtime scope.
