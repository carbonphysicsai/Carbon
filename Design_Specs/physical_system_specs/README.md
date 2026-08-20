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
6. **When implementation and explanatory metadata disagree, preserve current runtime behavior unless an explicit scientific change is approved.** A representation artifact must not silently expand or narrow a live/implemented envelope.

## Burgers prototype findings

The current P0 implementation supports useful descriptive semantics including a 1D periodic spatial domain, final-time operator target, four-mode Fourier initial-condition family, role-specific viscosity/amplitude ranges, and an IMEX Fourier reference realization.

### SN-BURGERS-001 — provisional decision

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

This is intentionally marked **provisional pending tech-lead review**. If the intended science is actually `3e-4`, the correct repair is to version/change the executable Challenge semantics and then update the representation, not to let the representation lead runtime behavior.

The repository identifies the system as 1D viscous Burgers but, in the reviewed sources, does not yet provide a separately ratified canonical symbolic equation representation for this new semantic object. The prototype therefore leaves that field `HUMAN_INPUT` rather than importing a textbook equation as protocol truth.

## First dossier-traceability test

The representation earns its complexity only if it makes an existing scientific chain easier to inspect. For Burgers, use the following initial traceability targets:

| Physical semantic fact | Current source | Reference/numerical realization | Dossier evidence needed before authoritative use | Score relationship |
|---|---|---|---|---|
| periodic spatial domain `x∈[0,1)` | `challenge_burgers1d.yaml` | Fourier reference solver in `burgers1d.py` | demonstrate reference implementation respects the registered boundary semantics and numerical error is acceptable | may support a future qualified boundary-condition metric; no gate implied by the spec |
| viscosity role domains; stress lower bound provisionally `5e-4` | executable YAML config | generator samples `nu` from role range | convergence/reference evidence across the registered viscosity envelope, including the lower stress boundary | contributes to stress-case definition; thresholds remain Score-Pack-owned |
| four-mode Fourier IC family with role-specific amplitude bounds | YAML + `_sample_ics()` | procedural IC sampler | evidence that generated distributions match the declared family and that reference solutions remain credible across amplitude bounds | defines data/stress semantics, not score directly |
| IMEX Fourier reference realization with 2/3 dealiasing | `burgers1d.py` | `burgers_reference_solve()` | convergence / cross-reference evidence sufficient for the dossier's reference rank | reference source for downstream metric calculation; not itself a score definition |
| candidate conservation / residual checks | PoC design + future qualified definitions | future metric implementations | explicit scientific definition, numerical method, calibration, and applicability evidence | only after registration in Score Pack may a metric/gate affect `S_combined` |

This table is deliberately incomplete. Missing dossier evidence should remain missing rather than being inferred from the existence of a symbolic/structured model.
