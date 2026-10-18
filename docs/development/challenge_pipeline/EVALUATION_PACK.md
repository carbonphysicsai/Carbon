# Challenge evaluation data (DEVELOPMENT)

Keep one operator-edited `evaluation-pack.json` under each Challenge's
validator-owned directory, for example
`<private-root>/synthetic-linear-field-2d/evaluation-pack.json`. The trusted
receiver configuration selects this file, Challenge ID and Challenge version.
At admission, `prepare_pack` reads this one editable draft, derives artifact
hashes, and returns fully pinned bytes. The receiver retains those bytes
write-once in its existing private artifact store, records their digest in
the run registration, and calls `load_pack` on the retained snapshot. An
operator edits one manifest and runs the normal validation/admission flow;
they do not copy hashes into a second form.
Miner requests never select a manifest path, digest or artifact root. Do not
put a private manifest, case IDs, reference rows, answers or custody paths in
the repository or a public Challenge kit.

## Onboard a Challenge from its engineering brief

Co-design the Challenge brief and a measurable scoring situation. The brief
defines a useful engineering question; the scoring design exposes which
answers, solver runs and independent checks can actually judge it. Freeze the
resulting Challenge-owned meanings before generating protected evidence. This
is the general onboarding path, not a second scorer or a requirement that a
new Challenge copy Motor, Cold Plate or synthetic fixture values.

| Decision in order | Challenge-owned definition and evidence | Existing pack handoff |
| --- | --- | --- |
| **1. Brief and valid scope** | Name the physical job, assumptions, valid operating envelope, model inputs and outputs with units/shapes, design actions, and important optimization limits with direction and signed margin. Distinguish the target population `P`, draw/proposal `Q`, and evidence weights `w`; identify whole-question masks, independent problem clusters and difficult or OOD strata **inside** the valid envelope. Out-of-envelope stress is a separate diagnostic. | Public `construction_kit`, `interface` and `physics_contract` carry the served construction meaning. Public accuracy, important-limit and design-objective roles can explain it, but their availability alone does not make a scoring rule. |
| **2. Noncompensable gates** | Declare and implement physical/output validity, finite/repeat and required accuracy/coverage gates with source-owned predicates and versions. A gate name alone cannot certify its predicate. An accurate prediction of an infeasible design is not a physics failure. Missing owner-set floors remain `HUMAN_INPUT`; failed or ambiguous reference evidence is unresolved, never a candidate gate failure. | The selected registered Score Pack names applied gates; trusted Challenge measurements supply their verdicts. The receiver and ScoreLab use the same registered predicates and shared scorer. |
| **3. Eligible TOP rule** | After gates, the owner-directed dual-score target allocates **50% to physics quality `A`** (broad accuracy, robustness and predeclared in-envelope OOD performance) and **50% to verified design quality `D`**. `D` measures the solver-verified feasible design outcome against the declared objective and comparator, not proximity to a limit or a model-predicted optimum. Register named component units, directions, transforms, scales, within-leg aggregation, per-leg minima and typed decision-outcome policy only when backed by trusted measurements and evidence. | One selected Score Pack and the shared ScoreEngine own the applied rule; the public allow-listed view explains the applied definitions and shows gate/status, `A`, `D` and TOP without hidden case identities. The current v3 MAE/gate/paired-speedup path does **not** implement the dual `A`/`D` target and keeps its historical meaning. |
| **4. Solver and data plan** | Work backward from those gates and legs to the cases and accepted references needed for complete `P`/`Q` questions, difficult/OOD coverage, signed limit margins, feasible comparator and design verification. Pin solver source/fidelity/applicability and numerical ambiguity; account separately for acquisition, model inference and verification resources. Keep false-feasible, missed-feasible, abstention and typed reference/infra failures visible. | Private `case_bank`, `reference_rows` and `solver_evidence` hold protected source roles; private `score_pack` and optional `source_registration` bind the applied rule and exact registered job. Their file hashes prove identity, not reference adequacy or scientific qualification. |
| **5. Receiver and bank lifecycle** | Admit one exact Challenge/pack/source version, independently reconstruct the submitted model, and evaluate it on the selected protected material. Add, rotate and retire hidden batches on a cost- and exposure-aware schedule separate from KOTH ranking, while retaining draw roles, `P`/`Q`/`w`, masks, reference status, exact run pins and historical interpretations. A new batch is not a fresh-case finalist tournament. | The trusted receiver seals this manifest, checks each used role and run-specific hidden-bank fingerprint/reference digest, then passes authorized measurements to the same ScoreEngine used by ScoreLab. Public results use an allow-list; private paths, answers, draw IDs and full pack digest stay private. |

Construction and public practice continue through the same path for supported
backbones, libraries, strategies and custom graphs even when protected data,
a graded Score Pack or an owner-set gate is still unavailable. Descriptive or
unranked measurement may proceed under its explicit contract; it cannot be
relabeled as a graded
result, qualification, LIVE activation or reward. A new producer formula,
population/mask rule, solver fidelity, gate, score transform or outcome policy
needs a prospective version; old results are never silently rescored.

The present private v3 binder handles registered MAE, gates and paired
speedup. The existing prospective dual reducer can validate declared metric
and gate names, units, transforms, scales, minima and outcome policy, but it
does not attest the trusted producer or reference adequacy. A normal receiver
path that produces authenticated `A` and `D` measurements and binds their
source, common mask and whole-question outcome to one selected dual Score
Pack is still a separate implementation gap for ScoreLab and Platform. Until
that path and each Challenge's measurement and gate contracts exist, the
50/50 target is an onboarding rule design, not an applied grade. Keep missing
scales, floors and evidence roles explicit rather than translating v3 speedup
into design quality.

## Current eight-Challenge data handoff (18 October 2026)

This DEVELOPMENT inventory uses the current briefs in
[`round1/README.md`](round1/README.md). A source, diagnostic registry, or
planned case count is not an accepted protected reference or an admitted Score
Pack. The active Battery v1, older Motor diagnostic, older Cooling synthetic
task, and prospective buyer briefs retain separate identities. The five `f*`
briefs remain draft tasks.

The first useful Design comparison precommits the model pick and a strong cheap
baseline pick, then independently verifies **both whole actions over every
mandatory condition** at the same declared budget. Record each action's
feasibility, buyer objective in native units, signed margins, reference
intervals, failures, and paired achieved value. This needs accepted references
for those picks; it does not need an exhaustive menu. Claim global or
finite-menu regret only with a separate optimum witness or enough accepted
menu references to establish it. `NONE_FEASIBLE` requires complete exclusion
evidence. Keep baseline-relative lift and global-optimum regret distinct.

Physics `A` starts with quantities both the registered model interface and
trusted reference actually expose. Retain ordinary, both-sided critical-limit,
adverse valid-envelope, and held-out **whole-question** cohorts with common
masks and independent-cluster identities. A perturbation component compares
model *and reference* responses. Source failure or numerical ambiguity defers
the question, never fails the candidate. The proposed weakest-component
benefit, Design transform and quantity scales remain experiments until
prospectively registered; the shared reducer does not turn a weighted mean
into a minimum implicitly. A trusted producer must emit any named minimum
benefit and retain its raw components.

For every proposed measurement the packet owner returns **actual source and
version, compatible accepted coverage, smallest missing observer or reference
batch, and unresolved owner decision**. `P`, proposal `Q`, weights `w`, solver
adequacy and scientific floors stay explicit. Diagnostic strata and repeated
operating points do not silently become independent population questions.

| Task / actual producer | Compatible first-pilot data | Missing or conditional evidence |
| --- | --- | --- |
| **Battery.** Active `carbon/battery` plus `carbon/challenge_validator/battery_bank.py`; prospective [`ambient-map v3`](round1/battery-ambient-map-v3.md) via `scripts/dev/evidence_runs/battery_v3.py`, `scripts/dev/battery/feasibility02.py`, `carbon/development_comparison/battery_v3_kit.py`. | Active four-input v1 has public 400 TRAIN / 200 PRACTICE and 121-point V/T, cycle-1 plating, Q1/10/20/30 under **v1 identity**. A prospective six-input v3 Physics pilot can use only five kit summaries: `charging_t_max_c` [°C], `minutes` [min], `plating_min_v` [V], `q30_over_q1` [1], `v_max_v` [V]. Verify pick and baseline across every mandatory band, preserving the guarded minutes clock's initial 120-second rest. | V3 is not the active v1 Challenge or an accepted five-band bank. The source persists phase extrema and plating cycle/phase, **not** raw v3 waveforms or intra-phase timestamp. Waveform/localization scoring requires new observer **and** model-output contracts; v1 traces cannot fill it. The 4.2-V old and guarded 4.19-V protocols cannot share labels. Five-band/full-menu and 4,000-TRAIN plans are conditional, not automatic jobs. |
| **Motor.** Older 8p/24s source `carbon/challenge_validator/motor_source.py`; revised [`precision joint v2`](round1/motor-precision-joint-v2.md) via `scripts/dev/evidence_runs/motor_10p12s.py` and `carbon/development_comparison/motor_10p12s_kit.py`. | Preserve each signed 60-angle torque curve, mean, absolute/defined relative ripple, role margins and method/refinement evidence. Verify pick and baseline across complete selected commands; revised 10p/12s also requires defined skew slices and zero-current cogging. | Old diagnostic curves and synthetic six-command limits do not answer the revised holding/peak job. Revised full-role references, peak/cogging evidence, independent geometries and an admissible comparator must be established. |
| **Cooling cell v3.** [`buyer brief`](round1/cooling-cell-v3.md), `carbon/challenge_pipeline/cooling_readiness.py`; older native outputs in `carbon/challenge_validator/cooling.py`. | Existing source exposes peak/profile temperature and pressure in its own scope. The v3 TIM2 case-plane comparison needs **co-located** heated-face T, interface heat flux q, coordinates/areas and R_TIM2 to compute `max_x(T_plate(x)+R_TIM2(x)q(x))`, plus pressure/flow for each pick/baseline service case. | Buyer post-spreader maps, lid/contact/TIM properties and uncertainty, service panel, hydraulic objective/limit and accepted observer are unresolved. Combining independent extrema or importing the old 100 °C / 0.25 W synthetic task cannot establish the 85 °C case-plane decision. |
| **f02.** [`burst brief`](round1/f02-burst-thermal.md), `scripts/dev/reference_packages/elmer/f02_deck.py`, `f02_menu.py`, `f02_export.py`, `carbon/development_comparison/f02_kit.py`. | Menu-v2 `docs/development/evidence/reference-packages-01/f02-menu-v2/registry.json` specifies 16 actions × 24 contexts. Each pick/baseline needs a 120-second transient, spatial top-die peak/location/time, event-aligned traces, crossing/recovery status and peak refinement near 95 °C. Extra energy is an analytic action integral, not learned Physics credit. | The 384 primary transients and separate 960 off-menu TRAIN rows are **planned**, not accepted solves or pack adoption. The round-one nine-action/216-pair count is historical for menu-v2. Conservation/interface Physics needs field/integral observations beyond a scalar peak. |
| **f06.** [`3D grating brief`](round1/f06-grating-coupler.md), `solver-package-specs/f06-meep.md`, `scripts/dev/code_verification/meep_mode.py` slab control. | Each pick/baseline mask needs all five wavelengths × nine correlated tolerances, coupling/reflection fractions, panel p10, every-cell margins and applicable flux/refinement controls. | Adequate finite-width full-3D truth and an accepted 45-cell panel are not demonstrated by the slab control. Old 2D supermode and metagrating data are different jobs. Establish a bounded 3D resolution/cost witness first; process population and numerical adequacy remain owner-held. |
| **f08.** [`resonance brief`](round1/f08-resonance-structure.md), `scripts/dev/reference_packages/calculix/f08_deck.py`, `carbon/challenge_pipeline/structures_readiness.py`. | Each geometry needs mass, static compliance, modes, complex tip/probe FRFs and adaptive full-band peaks over 80–600 Hz at all three dampings, with mesh/mode/frequency intervals. Keep the actual buyer **tip** peak. | `max(tip,probe)` is a diagnostic, not the buyer tip observer. Accepted complete panels, narrow low-damping peak resolution, independent geometries and comparator receipts remain to be returned. |
| **f13.** [`silencer brief`](round1/f13-compressor-silencer.md), `scripts/dev/reference_packages/elmer/f13_deck.py`, `f13_power_probe.py`, `carbon/challenge_pipeline/silencer_readiness.py`. | Each geometry needs a complete 500–2500 Hz curve, interval-weighted p10 TL, complex R/T, raw powers, notch locations, port-plane definitions and adaptive/refinement evidence. The 5 dB target applies to p10, not every frequency. | Repaired sparse power closure is not full-band/new-design adequacy. Full curves, de-embedding/mode applicability and a strong comparator are still needed; pressure drop is outside the no-flow brief. |
| **f17.** [`mixer brief`](round1/f17-passive-micromixer.md), `carbon/challenge_pipeline/micromixer_readiness.py` flow/scalar observer and cache plan. | Each geometry needs all nine flow × diffusivity conditions, outlet concentration and positive axial-flux weights, unclipped mixing M, pressure [Pa], fluid-volume/flow residence [s], balance and refinement controls. | Draft 5-geometry × 9-condition × 2-rung and separate TRAIN counts are preparation, not accepted coverage or a job grant. Numerical smearing, backflow and flow-cache equivalence need witnesses; no accepted complete design panel is established. |

Use public `interface`, `physics_contract`, accuracy/limit/objective definitions,
TRAIN and intentionally incomplete practice for construction meaning. Private
`case_bank` carries whole questions, panels, `P`/`Q`/`w`, cohorts and exposure;
`reference_rows` carries raw units/coordinates, typed status, intervals and
accepted pick/baseline outcomes; `solver_evidence` pins actual decks, meshes,
observers, controls, attempts and resource use; `score_pack` binds the applied
measurements, transforms, gates, floors, equivalence and outcome policy. None
of those private rows or identities belongs in miner-visible surfaces.
Research owns physical applicability, ScoreLab the score proposal, Packets2
the Battery inventory, the Challenge-pack owner the other seven data maps,
and Product any finite authorized job dispatch.

## Manifest and data roles

The manifest is a small index over existing material, not another bank or
scorer. Its complete shape is:

```json
{
  "schema": "carbon.challenge-evaluation-pack.v1",
  "challenge": {"id": "<registered Challenge ID>", "version": "<version>"},
  "pack_version": "<prospective operator version>",
  "public": {
    "construction_kit": "HUMAN_INPUT",
    "interface": "HUMAN_INPUT",
    "train": "HUMAN_INPUT",
    "physics_contract": "HUMAN_INPUT",
    "accuracy_definition": "HUMAN_INPUT",
    "important_limit_definition": "HUMAN_INPUT",
    "design_objective": "HUMAN_INPUT"
  },
  "private": {
    "case_bank": "HUMAN_INPUT",
    "reference_rows": "HUMAN_INPUT",
    "solver_evidence": "HUMAN_INPUT",
    "score_pack": "HUMAN_INPUT",
    "source_registration": "HUMAN_INPUT"
  }
}
```

`source_registration` is an optional private role in this still-prospective
v1 manifest. The original four-role private manifest remains valid and keeps
its exact byte identity. Omission or `HUMAN_INPUT` means the normal scoring
source is unavailable; it does not prevent pack selection, construction, or
task retention. Unknown roles still fail admission. The role must reference
an owner-private artifact by relative path, never an inline object or a miner
path. `prepare_pack` pins its SHA-256 from the file without asking the operator
to copy a digest into the draft. The pinned artifact has this closed envelope:

```json
{
  "schema": "carbon.challenge-evaluation-source-registration.v1",
  "evaluation_version": "<explicit owner-registered version>",
  "trusted_job": {"<existing trusted job fields>": "<owner-supplied values>"},
  "benchmark_registration": {"<existing benchmark v3 fields>": "<owner-supplied values>"}
}
```

`snapshot.read_source_registration(private_root)` reads the exact pinned
artifact and validates only the envelope. The trusted normal caller must
validate the job against the retained task and selected construction material,
re-register the benchmark document with the existing benchmark validator,
check its computed digest and identity, and derive the one static query from
the verified `case_bank` bytes. A manifest label or fixture registration does
not provide those proofs. No population, case weight, timing profile, job
identity, reference rule, or evaluation version is synthesized. This role is
never included in `public_projection()` or a miner result. A dynamic
`HiddenBatchStore` remains a separate Challenge-specific adapter, not a
fallback to this static query path.

Replace a role with `{"path":"relative/file"}` only when the underlying
existing artifact and its own contract are known. Paths are relative to a
trusted public or private artifact root supplied by the caller.
`prepare_pack` calculates the role's SHA-256 from the actual file and writes
`{"path":"relative/file","sha256":"sha256:..."}` into the returned
**sealed bytes**, leaving the editable draft alone. A stale `sha256` in the
draft is refreshed for a prospective run. `load_pack` accepts only a sealed
manifest with all provided roles pinned. It checks each role on every read;
downstream consumers still use their existing interface, physics, measurement
and ScorePack validators. A digest match does **not** qualify the science.
Small public definitions (`construction_kit`, `interface`, `physics_contract`,
`accuracy_definition`, `important_limit_definition`, `design_objective`) may
instead be edited directly in the one manifest as
`{"inline": {"existing": "contract fields"}}`. `prepare_pack` derives the
inline digest automatically and the sealed snapshot retains immutable encoded
bytes. TRAIN, case banks, reference rows, solver evidence and the exact-byte
Score Pack cannot be embedded this way. The inline object must still satisfy its existing
contract-specific parser when the receiver uses it; this loader never
interprets or invents physical values.
`case_bank` may instead be `{"kind":"hidden_batch_store"}`. The validator
supplies its existing `HiddenBatchStore` and separately records the selected
batch fingerprint and references digest in the run. `resolve_hidden_batch`
requires those exact run pins, `COMPLETE` state, matching Challenge identity,
and the stored document/reference digests. This avoids copying or hashing a
mutable SQLite database as if it were an immutable case snapshot. A sealed
pack may also contain a fixed fingerprint and references digest for a
deliberately static development batch.
`snapshot.run_bindings_required()` names a dynamic `case_bank` until those
run-specific pins have been selected and checked; storage availability alone
does not make the run ready to score.

`prepare_pack(root, relative_path, public_root=..., private_root=...,
challenge_id=..., challenge_version=...)` returns `sealed_bytes` and a parsed
snapshot. The trusted caller retains `sealed_bytes` write-once and records
`snapshot.manifest_digest` automatically. `freeze_pack` is a narrow helper for
an already fully pinned manifest.
`load_pack(root, relative_path, expected_digest=..., challenge_id=...,
challenge_version=...)` returns `EvaluationPackSnapshot`. Use
`snapshot.read_role(root, scope, role, max_bytes=...)` for an artifact, or
`snapshot.resolve_hidden_batch(store)` for the existing hidden batch. Both
refuse a missing or changed reference as `EvaluationPackUnavailable`; that is
not a candidate error or a zero score. `snapshot.public_projection()` exposes
only the public role names, availability and digests. It excludes private
paths, identities, answers and the full manifest digest. The validator retains
`snapshot.manifest_digest` with the exact run registration and result. An edit
requires a new external digest and prospective registration; old results keep
their old pack identity. There is no latest-file fallback.

For JSON roles, `snapshot.read_json_role(root, scope, role,
max_bytes=...)` applies the same verified read and strict decoder, including
typed duplicate-key, nonfinite and malformed-input refusals. The consumer
still applies the role's existing semantic validator. Use `read_role` for an
exact-byte Score Pack so its established loader controls parsing and pinning.

At admission, call `snapshot.verify_available(public_root, private_root,
hidden_store=...)`. It verifies each supplied role and returns the sorted
`HUMAN_INPUT` roles still missing. The caller checks the roles required for its
specific evaluation and applies the existing artifact-specific parsers and
scientific contracts. `verify_available` is a storage/integrity check, not a
claim that the physics, accuracy definition, solver or Score Pack is adequate.

For synthetic linear field 2D v1.3, the existing
`carbon.challenge_kit.synthetic_linear_field_2d` construction material and
`synthetic_linear_field_2d_benchmark_source` provide the current public
interface, fixed TRAIN identity and synthetic physics/reference definitions.
The retained CR06 inference and the separately measured analytic reference
row can be bound as artifacts after their exact bytes are saved. The existing
benchmark Score Pack has a null accuracy ceiling; this remains
`PACK_NOT_READY`, without ranking. For motor, the existing
`carbon.challenge_validator.motor_source` family and `HiddenBatchStore` provide
the private batch/reference path, while its published Challenge contract and
scoring modules remain the owners of physical definitions. A motor manifest
must bind their actual exported artifacts and selected complete batch; this
file does not pick an envelope, limit, score weight or design value. These are
two different Challenge source patterns for the same manifest/loader, not
separate receiver implementations.

The loader is a source-level building block. The normal receiver and ScoreLab
must still be wired to the same trusted snapshot and existing scoring core.
Until that integration and relevant scientific inputs exist, a manifest alone
is not a working evaluation or a LIVE qualification.

For a selected pack and an actual registered private evaluation, the trusted
operator path calls
`carbon.scoring.private_evaluation_source.build_pack_source_receipt` with the
retained `EvaluationPackSnapshot`, saved graph entry, trusted job, registered
cases, actual reference rows and ordered original query bytes. It returns v2
private source-receipt bytes and their SHA-256. The operator stores those bytes
write-once and independently registers their digest; the existing private
evidence binder verifies the exact source and selected pack pin. This helper
refuses missing material used by this v3 source route or a selected TRAIN
digest that differs from the trusted entry. The public
`accuracy_definition`, `important_limit_definition`, and `design_objective`
roles are informational until an actual scoring core consumes them; their
`HUMAN_INPUT` status does not gate v3 source emission or imply an applied
rule. The validated ScorePack and benchmark registration define the applied
v3 rule. The normal caller must also reload and verify the selected
role bytes against the actual construction, case, reference, solver and
ScorePack materials; a matching Challenge ID/version and manifest digest
alone do not prove that relationship. Missing role-specific provenance is
typed source unavailability. The helper does not select a pack, run a solver,
expose private rows publicly, score a candidate or make the source receipt
authoritative by itself. The legacy
no-pack v1 source path keeps its historical meaning.
