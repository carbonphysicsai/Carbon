# Draft physics contracts

PKT-06 / PHYSICS-CONTRACT-PACKETS-01. **DRAFT / HUMAN_INPUT** for Carbon
Validator and science review; RES-06 reconciliation is still required. These
are proposed plain-data documents, not registered validator contracts. Nothing
here adds a gate, score, bank permission, numerical tolerance or runtime ID.

The controlling design principle is **calibrated to the pinned, verified
reference solver**. The operator draft's sections 0–1 were read at SHA256
`3de29124d7b34542b45107bb224322036876d5e0e474c6fac90677c1ed213369`.
Only that format/principle is used; later draft scoring proposals are not adopted.

| Draft | Exact scope | Current useful model outputs | Important missing outputs |
|---|---|---|---|
| [f02.json](f02.json) | Constant-property layered burst-thermal model, menu v2 support | Peak top temperature, extra burst energy | Temperature history/field, full source/boundary energy and stored heat |
| [cooling-cell.json](cooling-cell.json) | Interior cell, **point C draft**: 45 °C, 1400 W, 2.8 L/min footprint flow, 30 kPa allocation | Legacy peak/profile/pressure | Co-located case-plane temperature/flux, independent mass/enthalpy and wall-flux integrals |
| [motor.json](motor.json) | 10p/12s, three-slice 0/2/4° skew | Signed loaded/cogging torque curves and derived summaries | Vector fields, stress contours, energy/coenergy, material applicability |
| [f13.json](f13.json) | Quiescent, rigid, lossless acoustic silencer; 60 mm numerical ports | No registered model kit; draft reference R/T, powers and TL | Adopted complex/power output contract, interior fields, reverse-port witnesses |

The cooling row does **not** replace point B as the central panel, turn optional
point C on, or include a full plate/manifold. The current 8p/24s runtime motor
is not the 10p/12s development kit. A field computed by the reference is not
automatically a model output; a quantity reconstructed analytically from inputs
is not independent evidence that the model conserves it. The contracts make
these distinctions output by output.

## Review and applicability

Each JSON has `laws`, `validity`, `required_outputs`, `tolerances`, `probes`
and `gates`, plus source/scope/calibration records. Mathematics is descriptive
text, never executable expressions. `type` is drawn from the operator draft's
closed vocabulary. `excluded_claims` states tempting but invalid generalisations.
This document schema is **draft v1**, not a validator API or a registry entry.
The symmetry, superposition and limiting-case proposals are mathematical
consequences inferred from the cited equations under the stated assumptions,
not empirical findings on Carbon's reference or automatically sourced adoption.

Input ranges describe existing development support, not earned physical validity.
Use `carbon/challenge_validator/validity.py`: an undeclared material/model law,
unknown input or out-of-range value yields **UNRESOLVED**, not candidate failure.
The cooling PG25 30–99 °C and laminar Re ≤2000 applicability checks are already
declared; f02 and motor material applicability remain undeclared, and f13 has
no registered declaration. A contract cannot remove those holds.

Buyer limits (95 °C f02, 85 °C cooling case plane, motor torque/ripple/cogging,
f13 TL) are not universal physics laws. They remain in their existing buyer
packets. A missing output prevents adoption of its law until a prospective,
reviewed model/reference output contract supplies it. Summary consistency checks
alone do not establish that a model learned the physical equations.

## Image-bound calibration plan (not executed)

1. Record image digest, solver/build, deck/generator digest, observer/material
   digest, units, sign/normal conventions, mesh/time/frequency ladder and scope.
   Confirm code-verification acceptance for **this** equation/element route.
   Elmer heat acceptance does not verify Elmer Helmholtz. Image identity alone
   is not adequacy, store presence, or a calibration result.
2. Register a public development calibration manifest of matched single cases,
   ordered pairs and paths from supported inputs. Include analytic controls,
   interfaces, near-validity edges and symmetry pairs. Never read, republish or
   derive public probes from hidden EVAL/STRESS/quiz/tuning material. These
   proposals authorise no solver run or paid/counted campaign.
3. Measure reference residual distributions and mesh/time/frequency convergence
   on those same observables. Separate solver/observer failure from model error;
   failed references give no candidate failure. Keep signed residuals, absolute
   residuals, units and the number/resolution of cases. Do not use a global MMS
   field error as a transferable °C, N·m or dB tolerance.
4. Science chooses residual quantile, multiplier (at least one), sampling
   uncertainty treatment and absolute floors in observable units. All are
   `null / HUMAN_INPUT` here. Balance denominators must not vanish at zero
   input; use an approved absolute floor and report absolute as well as relative
   residuals. Monotonicity/symmetry tests need matched, resolved pairs, not
   comparisons with changing service conditions. Differences inside reference
   uncertainty remain UNRESOLVED.
5. Proposed law budgets include both numerical uncertainty and any separately
   approved physical simplification discrepancy. The latter cannot be hidden by
   inflating numerical tolerances. An exact manufactured solution is a code check,
   not buyer-tool agreement or agreement with reality. Reference findings trigger
   prospective versioned changes, never silent historical rescoring.
6. Bind the retained calibration to exact identities. Any image rebuild/re-pin,
   deck, material or observer change invalidates its reuse until reviewed and
   recalibrated. Future protected/operator calibration, contract digest adoption,
   probe density and gate/score use need their own explicit authority.

## Non-blocking packet-checker notice

The ordinary CLI now reports a physics-contract advisory:

```text
python -m carbon.challenge_pipeline.onboarding.reconcile --root . --manifest <public-manifest.json> --format markdown
```

Missing file: **physics contract missing**. Present well-formed draft: **physics
contract draft present — HUMAN_INPUT** (metadata inspection only). Unreadable,
malformed, oversized, symlink-escaped or mismatched metadata: **physics contract
unavailable — not evidence of absence**. The JSON notice retains the attempted
public path and, when read, digest. It echoes no document content or exception.
Aliases locate a family draft; they do not prove that draft covers every packet
variant. Unrecognised safe family IDs look only for that family's exact filename.

The CLI emits report v2 with an advisory; `checklist_clear`, buyer-field coverage,
authority and exit codes are unchanged. `reconcile(..., include_physics_contract=True)`
does the same. The default API stays v1 so already-retained example reports are
not rewritten or re-pinned as if they were new evidence. No contract is imported
or interpreted by the scientific validator or any execution path.

## Principal sources

The family documents cite exact repo files for implementation facts and primary
sources for proposed equations; applicability still needs Carbon Validator/science.

- [Elmer Models Manual](https://www.nic.funet.fi/index/elmer/doc/ElmerModelsManual.pdf), heat and Helmholtz models. The retrieved January 2026 manual describes 26.1; the proposed images are separate exact pins, not inferred from the manual.
- [GetDP 3.5.0 manual](https://getdp.info/doc/texinfo/getdp.html), magnetostatic vector potential and the 2D example.
- [MIT Kirtley, Electromagnetic Forces](https://ocw.mit.edu/courses/6-685-electric-machines-fall-2013/06deccf046b565a8295e5ada36b252df_MIT6_685F13_chapter1.pdf), energy/coenergy and Maxwell stress.
- [COMSOL, conservation of energy](https://www.comsol.com/multiphysics/heat-transfer-conservation-of-energy), heat flux and integral energy bookkeeping.
- [COMSOL, maximum principles](https://www.comsol.com/blogs/exploiting-maximum-principles-to-save-time-and-resources/), conditions on convection/diffusion bounds; not blanket applicability to every case.
- [COMSOL, mass/momentum/energy](https://www.comsol.com/multiphysics/fluid-flow-conservation-of-momentum-mass-and-energy), fluid conservation.
- [COMSOL, acoustics](https://www.comsol.com/multiphysics/acoustics), linear pressure acoustics and time-averaged intensity/power.
- [COMSOL, temperature-equation linearity](https://doc.comsol.com/5.5/doc/com.comsol.help.heat/heat_ug_modeling.06.33.html), constant-coefficient linear scope (documentation search evidence; retrieval of the full page was unavailable).
- [Maznev, Every and Wright, reciprocity](https://arxiv.org/abs/1210.6309), symmetric properly normalised transmission for linear conservative, time-reversible systems; not equality of asymmetric-port reflections.

No solver runs, calibration, hidden-case inspection or scientific adoption occurred.
