# PhysicalSystemSpec authoring and semantic ownership

**Status:** design-integration guidance; non-runtime and non-scoring.  
**Primary design:** `Design_Specs/Physical_System_Representation.md`.  
**First prototype:** `burgers1d_v0.prototype.yaml`.  
**SN-1 traceability test:** `BURGERS_TRACEABILITY.md`.

The purpose of this directory is to test structured physical semantics without creating a new scientific authority. A field may appear in a `PhysicalSystemSpec` only when its source/owner is explicit. Source disagreements remain visible until resolved by the appropriate scientific owner.

## Identity

For a spec bound to a registered Challenge:

```text
semantic identity = physical_system_spec_id + version
byte identity     = ChallengeRecord.artifacts["physical_system_spec"].digest
```

Do not add a second canonical `content_hash` inside the spec. A3 owns exact registered bytes.

## Field-to-owner map

| PhysicalSystemSpec information | Source / semantic owner | Rule |
|---|---|---|
| `physical_system_spec_id`, semantic `version` | Physical-system authoring contract | Human/machine semantic identity only; A3 digest owns bytes. |
| Challenge / generator binding | Challenge Registry + generator artifacts | Must reference exact existing identities; do not invent future versions. |
| Physics family / dimension | Domain science / Challenge author | Descriptive; does not prove validity. |
| Independent/state variables | Domain science + implemented generator/model interface | Preserve implemented meanings and units when known. |
| Governing relations | Domain science / qualified scientific source | Never infer a canonical symbolic form merely from a Challenge name. |
| Initial/boundary conditions | Generator config + domain science | Public descriptive semantics; realized draws remain protected. |
| Parameter domains | Executable generator config; claim boundary remains Evidence & Envelope Standards | Source conflicts must be recorded. |
| Excluded regimes / maximum claim | `Evidence_and_Envelope_Standards.md` + registered envelope | PhysicalSystemSpec may mirror; it does not widen the envelope. |
| Reference realization | `Generator_Creation.md` / generator implementation | Numerical method is evidence provenance, not physical truth. |
| Dossier evidence / reference rank | `Generator_Validation.md` + `Evidence_and_Envelope_Standards.md` | Spec may link only. |
| Candidate conserved quantities / invariants | Domain science | Candidate until dossier/Challenge qualification. |
| Candidate evaluation primitives | Future Physics Evaluation Primitive Library | Non-score-bearing until explicitly qualified and registered. |
| Gate IDs / thresholds / weights / `S_combined` | **`Scoring.md` + registered Score Pack only** | Never authored by PhysicalSystemSpec. |
| Seed domains / official seed derivation | A4 / Data Management | Never stored or altered by PhysicalSystemSpec. |
| Miner-visible disclosure | A6/A9/A10 allow-lists | Public-safe semantics do not imply automatic MCP/card/leaderboard disclosure. |
| Landscape physical features | Future Landscape evidence contract | Must earn prospective value; similarity is not causal evidence. |
| Product context of use | Specialist/product qualification path | Physical identity may be referenced; it never expands qualification automatically. |

## Authoring rules

1. **Prefer executable/configured facts over prose descriptions of implementation**, while preserving any conflict rather than erasing it.
2. **Do not silently convert general scientific knowledge into Carbon protocol semantics.** If Carbon has not ratified a canonical equation/constraint/feature, mark it unresolved.
3. **Never embed protected exam realizations.** Public ranges, equations, assumptions, and topology are different from official seeds/draws/tensors.
4. **Do not duplicate authority.** The representation links existing owners; it does not replace them.
5. **Unknown is valid.** Use `HUMAN_INPUT`, `UNRESOLVED`, or a typed missing state rather than fabricating precision.
6. **When implementation and explanatory metadata disagree, preserve current runtime behavior unless an explicit scientific change is approved.** A representation artifact must not silently expand or narrow a live/implemented envelope.
7. **A metric name must not overstate its mathematical meaning.** A proxy linked to a governing relation remains a proxy unless the implemented quantity actually matches a qualified mathematical definition.

## Burgers prototype findings

The current P0 implementation supports useful descriptive semantics including a 1D periodic spatial domain, final-time operator target, four-mode Fourier initial-condition family, role-specific viscosity/amplitude ranges, and an IMEX Fourier reference realization.

### SN-BURGERS-001 — provisional stress-bound decision

The current executable config and scientific-justification source disagree on the lower stress-viscosity bound:

```text
poc/configs/challenge_burgers1d.yaml  -> 5e-4
poc/generators/justification.py       -> 3e-4
```

**Provisional integration value: `5e-4`.**

Rationale:

- `generate_batch()` consumes the YAML config, so `5e-4` describes current realized P0 generator behavior;
- selecting `3e-4` only in `PhysicalSystemSpec` would falsely describe a stress envelope the current generator does not sample;
- silently changing the generator to `3e-4` would be a scientific/protocol behavior change and should require deliberate review/versioning;
- therefore the least-assumptive reconciliation is to preserve current executable behavior and repair the explanatory metadata if the tech/science lead accepts the decision.

### SN-BURGERS-004 — residual-proxy semantic finding

The SN-1 traceability test found that `poc/train/losses.py::residual_diagnostic()` computes

```text
mean |u*u_x - nu*u_xx|
```

on the predicted final field. It does **not** include `d_t(u)` and the implementation itself documents that it is not a full spacetime residual.

Therefore the current PoC quantity must not be promoted by `PhysicalSystemSpec`, dossier language, or a future production Score Pack as the full residual of

```text
d_t(u) + u*d_x(u) - nu*d_xx(u) = 0.
```

Treat it as a final-state spatial-balance proxy (or retain the old name only with an explicit proxy limitation) until a mathematically complete residual is implemented and qualified.

This finding is important evidence that the semantic layer is useful: it caught an existing terminology-to-mathematics mismatch before that language could harden into protocol authority.

## First dossier-traceability test

The complete analysis is in `BURGERS_TRACEABILITY.md`. The main chains are:

| Physical semantic fact | Current source | Reference/numerical realization | Dossier evidence needed before authoritative use | Score relationship |
|---|---|---|---|---|
| Burgers governing relation | relation IR + reference implementation | explicit advection + implicit viscosity in Fourier solver | convergence/reference evidence establishing numerical credibility over envelope | relation itself never scores |
| periodic domain / integral conservation implication | Challenge config + governing relation | Fourier periodic realization; discrete mean proxy | conservation floor, grid/precision sensitivity, envelope behavior, calibrated threshold | only an explicit Score-Pack metric may score |
| viscosity role domains; stress lower bound provisionally `5e-4` | executable YAML config | generator samples `nu` from role range | convergence/reference evidence across registered viscosity envelope | stress semantics only; weights/thresholds Score-Pack-owned |
| four-mode Fourier IC family | YAML + sampler | procedural IC sampler | distribution/coverage and reference credibility evidence | data/stress semantics, not score directly |
| IMEX Fourier reference realization with 2/3 dealiasing | `burgers1d.py` | `burgers_reference_solve()` | convergence / cross-reference evidence sufficient for stated reference rank | reference provenance only |
| current final-state spatial-balance proxy | `losses.py` | spectral derivatives of final prediction | definition/applicability/calibration evidence; do not call full PDE residual | only explicit registered Score-Pack use may score |

Missing dossier evidence remains missing. Symbolic structure cannot manufacture it.

## SN-1 disposition

**PASS.** The Burgers traceability exercise has already exposed two real integrity issues: the stress-range source conflict and the residual-proxy naming mismatch. Proceed toward a minimal `PhysicalSystemSpec v0.1` candidate after review, while keeping runtime/scoring unchanged and testing the schema against a structurally different second physics family before calling it general.
