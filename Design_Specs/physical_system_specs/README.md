# PhysicalSystemSpec authoring and semantic ownership

**Status:** design-integration guidance; non-runtime and non-scoring.  
**Primary design:** `Design_Specs/Physical_System_Representation.md`.  
**First prototype:** `burgers1d_v0.prototype.yaml`.

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

## Burgers prototype findings

The current P0 implementation supports useful descriptive semantics including a 1D periodic spatial domain, final-time operator target, four-mode Fourier initial-condition family, role-specific viscosity/amplitude ranges, and an IMEX Fourier reference realization. The current executable config and scientific-justification source disagree on the lower stress-viscosity bound (`5e-4` vs `3e-4`); the prototype records this as `SN-BURGERS-001` for scientific-owner resolution.

The repository identifies the system as 1D viscous Burgers but, in the reviewed sources, does not yet provide a separately ratified canonical symbolic equation representation for this new semantic object. The prototype therefore leaves that field `HUMAN_INPUT` rather than importing a textbook equation as protocol truth.
