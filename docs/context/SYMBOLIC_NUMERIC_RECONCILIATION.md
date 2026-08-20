# Symbolic-Numeric Integration Reconciliation

**Status:** active reconciliation on `design/symbolic-numeric-integration`; planning/context only.  
**Base reviewed:** `main` at `c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a` (A3 closed).  
**Design inputs:** `Design_Specs/Physical_System_Representation.md`, `docs/context/SYMBOLIC_NUMERIC_INTEGRATION_DECISIONS.md`, `docs/context/SYMBOLIC_NUMERIC_IMPLEMENTATION_MAP.md`.  
**Authority preserved:** domain owners in `Design_Specs/Build_Out.md`; this file does not reopen completed tickets or override semantic owners.

---

## 1. Current build-state reconciliation

Repository history and `.agent/WAVE.md` establish:

- **A1:** done;
- **A2:** done;
- **A3:** done;
- **A4:** todo / next ordinary Wave-A ticket at reviewed base;
- **A5:** todo;
- **A6:** todo.

Symbolic-numeric integration does not reopen A1-A3 and does not displace A4+ sequencing.

---

## 2. A3 attachment mechanism — resolved

Completed A3 already supplies:

```text
ChallengeRecord.artifacts: Mapping[str, ArtifactBinding]
```

Use the optional conventional binding:

```text
artifacts["physical_system_spec"] = {
  path: <trusted-root-relative path>,
  digest: sha256:<...>
}
```

### SN-H1 disposition

**Resolved: no A3 schema/code migration is needed.**

- `physical_system_spec` is a valid canonical artifact id;
- absence remains valid;
- if declared, ordinary A3 byte-integrity checks apply;
- no ninth qualification slot is created;
- no score/disclosure authority follows from the binding;
- later A12/integration tests should prove the negative invariants rather than reopening A3.

Identity rule:

```text
semantic identity = physical_system_spec_id + version
byte identity     = A3 ArtifactBinding.digest
```

No second canonical internal content hash.

---

## 3. Wave-A boundary reconciliation

### A4 — keep pure secrecy/seed-domain work

`PhysicalSystemSpec` does not participate in official seed derivation, role-domain separation, master-secret handling, or realized draw identity. It may describe public Challenge semantics only.

### A5 — keep pure scoring work

`ScoreEngine` must not parse `PhysicalSystemSpec` to invent gates, thresholds, weights, or `S_combined` behavior.

```text
PhysicalSystemSpec ─X─> ScoreEngine authority
```

Official path remains:

```text
qualified generator/reference
        ↓
metrics + gate inputs
        ↓
registered Score Pack
        ↓
A5 ScoreEngine
```

### A6 — first natural evidence-provenance propagation point

When A6 is implemented, preserve physical-system semantic id/version + bound artifact digest in full internal evidence when present. Do not expose trusted-root paths or automatically add this information to the miner-facing allow-list.

---

## 4. Generator / dossier / envelope semantic owner path

The physical semantic representation sits inside the existing authority chain:

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

Canonical owners remain:

- envelope / claim boundary → `Evidence_and_Envelope_Standards.md`;
- generator construction → `Generator_Creation.md`;
- generator evidence / dossier → `Generator_Validation.md`;
- scoring → `Scoring.md`.

`PhysicalSystemSpec` links those meanings; it does not supersede them.

---

## 5. Burgers semantic prototype — current decisions

Prototype:

```text
Design_Specs/physical_system_specs/burgers1d_v0.prototype.yaml
```

Current implemented/configured facts include:

- 1D viscous Burgers;
- final-time operator map;
- periodic `x∈[0,1)`;
- `nx=128`, `T=1.0` normal mode;
- four-mode Fourier IC family;
- train/eval `nu=[1e-3,1e-2]`;
- stress `nu=[5e-4,5e-3]` in executable config;
- IC coefficient bounds `0.5/0.5/0.8`;
- IMEX Fourier reference realization with 2/3 dealiasing.

### SN-BURGERS-001 — stress lower bound

**Provisional decision: `5e-4`.**

The explanatory justification source says `3e-4`, but the executable config consumed by the generator says `5e-4`. The semantic layer follows current executable behavior pending review. If `3e-4` is scientifically preferred, version/change the executable Challenge and re-qualify rather than editing metadata alone.

### R2 — governing relation

Provisional relation matched to current reference implementation:

```text
d_t(u) + u*d_x(u) = nu*d_xx(u)
```

The relation is descriptive. The Carbon relation IR carries machine semantics; human display text is review/presentation only and does not define identity or symbolic equivalence.

---

## 6. SN-1 — Burgers end-to-end traceability test

Detailed analysis:

```text
Design_Specs/physical_system_specs/BURGERS_TRACEABILITY.md
```

### Test chain

```text
physical relation / assumption
        ↓
generator + numerical realization
        ↓
Validation Dossier evidence
        ↓
qualified metric definition
        ↓
Score Pack
        ↓
A5 ScoreEngine
```

### Verdict

**SN-1 PASS.**

The representation has already exposed two real integrity problems that were easier to miss when scientific meaning was distributed across code/config/prose.

#### Finding 1 — source-envelope drift

`5e-4` executable stress lower bound vs `3e-4` explanatory metadata.

#### Finding 2 — SN-BURGERS-004 residual-proxy mismatch

Current `poc/train/losses.py::residual_diagnostic()` computes:

```text
mean |u*u_x - nu*u_xx|
```

on a final-time predicted field. It omits `d_t(u)` and the implementation itself says it is not a full spacetime residual.

Therefore it must not be semantically promoted to the full residual of:

```text
d_t(u) + u*d_x(u) - nu*d_xx(u) = 0.
```

Recommended classification:

```text
final_state_spatial_balance_proxy
```

or retain the legacy name only with explicit `proxy` status and the omitted-time-derivative limitation.

**A5 implication:** do not widen A5, but do not let the fixture Score Pack accidentally harden a PoC proxy into a falsely named authoritative PDE residual. Any future full residual requires a new mathematical definition, implementation, dossier evidence, calibration, and registered Score-Pack use.

### Conservation chain

The current discrete mean conservation metric is physically motivated by the accepted Burgers relation + periodic domain, but remains a proxy requiring numerical/reference floor characterization and threshold calibration before production authority.

### Boundary chain

Periodic semantic structure does not automatically imply a boundary gate. The current endpoint-excluded Fourier representation makes a naive endpoint equality test inappropriate; any future diagnostic must be explicitly defined and qualified.

---

## 7. Public/private disposition

A registered `PhysicalSystemSpec` may be classified `public_challenge_semantics` when every field is already authorized public science. This aligns with existing generator doctrine that publishes generator code/ranges, Score Packs, and Validation Dossiers while protecting realized exam material.

Never include:

- master secrets;
- official seeds/draw IDs;
- materialized eval/stress tensors;
- reconstruction-sensitive protected state;
- unauthorized partner-private semantics.

Publication classification is instance-level, not a universal property of the type. Miner-facing disclosure remains separately allow-listed.

---

## 8. KEEP / WRAP / REPAIR / REPLACE

### KEEP

- A1-A3 completed implementations;
- A4 secrecy scope;
- A5 metrics + Score-Pack-only scoring boundary;
- A3 generic artifact provenance;
- generator/dossier/envelope authority chain;
- current build sequencing.

### WRAP

- optional `physical_system_spec` via A3 artifacts;
- semantic traceability around generator/reference/dossier/scoring;
- later A6 internal provenance.

### REPAIR / EXTEND

- reconcile `5e-4` vs `3e-4` source drift after lead review;
- classify current Burgers residual diagnostic honestly as a proxy;
- later stable relation/assumption/metric provenance IDs;
- later schema/validator/adapters/primitives only after generality tests.

### REPLACE

- none.

---

## 9. Next symbolic-numeric steps

1. **Tech/science review:** `docs/context/REVIEW_THESE_PRELIMINARY_DECISIONS.md` now contains R1-R7.
2. **SN-2 schema minimization:** derive the smallest `PhysicalSystemSpec v0.1` candidate justified by Burgers; keep optional/extension fields out of core where possible.
3. **SN-3 second-system test:** test the candidate on a structurally different physics family, preferably Poisson if Carbon's source semantics are sufficiently specified.
4. Only after two-system survival, build a Carbon-native structural validator.
5. Only after a stable target contract, build a ModelingToolkit authoring adapter.
6. Later build candidate evaluation primitives and dossier linkage; never auto-authorize gates.
7. At A6 preserve physical provenance internally; at A12 prove score/secrecy/disclosure non-interference.

---

## 10. Current recommendation

> **Continue. The Burgers traceability test demonstrates that structured physical semantics can catch real scientific/provenance drift without touching runtime authority. Move next to schema minimization and a second-physics generality test, while ordinary Wave-A work proceeds independently.**
