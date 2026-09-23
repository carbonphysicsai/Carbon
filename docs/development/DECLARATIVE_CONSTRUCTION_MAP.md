# Declarative construction: capability map and expansion plan

Status: DEVELOPMENT engineering plan, 2026-09-23. It implements the owner
direction recorded as `OWNER-CONSTRUCTION-DECLARATIVE-01` in
`.agent/DECISIONS.md`. It changes no scoring rule, exam, tolerance,
comparison resource or qualification state.

## The rule this plan serves

Miners submit model, training and permitted training-data **policy** choices
from a versioned vocabulary that Carbon owns. Carbon supplies every
implementation, compiles the exact reconstruction plan, trains a fresh model
and runs prediction and evaluation through its registered services.

These stay out of scope:

- source code, executable expressions, and function or import names;
- callbacks and serialized objects;
- participant-defined composition graphs;
- pretrained weights, checkpoints and embeddings;
- fitted parameter arrays;
- uploaded datasets.

New capabilities enter through reviewed Carbon implementations and contract
extensions, never through per-submission exceptions.

The miner's research environment remains unlimited and has every prebuilt tool
available. That governs what a miner may *explore*. This plan governs what they
may *submit*.

A capability counts as submittable only when it has all four of the following:

1. **A public definition.** The miner can discover its allowed values, defaults,
   compatibility rules and limitations.
2. **A registered implementation.** Carbon knows the exact library build and
   code path that implements it.
3. **A complete reconstruction mapping.** The compiler resolves the field into
   the actual builder, training loop and predictor, and ignores or substitutes
   nothing.
4. **Acceptance evidence.** Changing the field changes the intended behavior,
   and invalid combinations fail with a named reason.

## How a submission flows today

1. `dry_validate` (`carbon/schema/strategy.py`) is a structural check only.
2. B-02B `compile_strategy` (`carbon/construction/compiler.py`) runs against
   `research_contracts()` (`carbon/development_session/research_catalog.py`).
3. `compile_recipe` then runs `compile_development_profile`
   (`carbon/reconstruction/profile.py`), which maps each resolved surface's
   `consumer_target` into the vendored lab's model, task and train configs.
4. The validator trains with the vendored `carbon_jax_lab` `Trainer`
   (`carbon/reconstruction/service.py`).

`tests/service/test_cw1_research_controls.py` runs every exposed surface twice,
with two values, in the C03 container. It asserts that parameters, optimizer
state or predictions change, and that its coverage equals the full surface set.

The validator resolves its image from the operator-installed
`validator-worker-image.json` (`carbon/reconstruction/validator_launch.py`),
never from anything the miner used.

## Capability map

Status key:
- **E**: exposed end to end.
- **I**: implemented in the vendored lab but not exposed.
- **U**: declared unavailable.
- **A**: absent.

| Dimension | Capability | Status | Where |
|---|---|---|---|
| Model family | FNO (`fno1d`) | E | lab `models.py`; `profile.py` `_BACKBONES` |
| | DeepONet (`deeponet1d`) | E | same |
| | Physics attention (`physics_attention1d`, Transolver-style) | E (D1) | backbone `transolver` in the research catalog only; the session and GPU catalogs are unchanged |
| | Haar wavelet operator (`haar_operator1d`) | E (D1) | backbone `haar_operator`; levels checked against the 64-point TRAIN grid |
| | Graph operators (`gno1d`, `gino1d`) | E (D1) | backbones `gno` and `gino`; `graph_radius` is exposed as `neighborhood_radius` |
| | Foundax FNO (`foundax_fno1d`) | I | `foundax_adapter.py`; different schedule semantics (see defects) |
| | `uno`, `physicsnemo_fno` | A | accepted by `dry_validate`, then refused at compile |
| Architecture | width, depth, n_modes, branch_points, remat | E | `research_catalog.py` SURFACES |
| | heads, slices, expansion | E (D1) | attention only; width must divide across heads |
| | wavelet_levels, neighborhood_radius, latent_points | E (D1) | GINO modes must fit its latent grid |
| | DeepONet branch and trunk depth | A | hard-coded three-layer MLP |
| Objective | normalised data MSE | E | always on |
| | relative loss, H1 weight, Burgers PDE residual weight | E | lab `training.py` |
| | other registered loss terms (L1, spectral weighting, …) | A | — |
| Optimizer | AdamW: lr, betas, eps, weight decay | E | lab `optim.py` |
| | weight-decay mask policy | I | `optim.py` accepts `decay_mask`; `Trainer` never passes it |
| | other optimizers | U | none in the lab; optax is pinned |
| Schedule | warmup plus cosine with a minimum ratio | E | `optim.py` |
| | other schedule families | A | — |
| Batching and stopping | batch size, microbatches, clip norm, EMA, inference weights, steps | E | lab `training.py` |
| | early stopping, checkpoint selection | U | forbidden, because selecting on labels would be model selection |
| Training stages | physics warmup ramp | E | lab `training.py` |
| | multi-stage schedules | A | resume exists only for infrastructure |
| Training-data policy | uniform case, then uniform time sampling | fixed | hard-coded; no surface |
| | adaptive sampling, curriculum, augmentation | U | vocabulary exists (`TrainingLeverKind`); every research entry is not-applicable |
| Physical structure | hard initial condition, mean enforcement | E | lab `training.py` |
| | other constraints (extrema, energy, symmetry) | A | — |
| Hybrid and templates | component slots | A | schema only; `profile.py` refuses any component |

## Defects under the four-part rule (fix first)

1. **`physics_warmup_steps` has no effect when `pde_weight` is 0.** The ramp
   multiplies only the PDE term. The controls test hides this by forcing
   `pde_weight` to 0.001.
2. **`ema_decay` has no effect on predictions when `inference_weights` is
   `params`.** The controls test checks the EMA state, not the predictor.
3. **FNO `n_modes` is silently clipped** to the grid's rfft length. This is
   harmless at the current 64-point grid, but it would become a substitution on
   a coarser one.
4. **DeepONet rejects an odd `width` because of `heads`,** a field that only
   applies to attention models.
5. **The profile receipt reports `enforce_mean: False` as a fixed value,**
   while the catalog default is `True`, and `True` is what is actually mapped.
6. **"Can I submit this?" cannot be answered.**
   - `dry_validate` accepts unknown backbones and parameters.
   - `parameter.unknown` and `parameter.unused` point only at `/parameters`.
   - `compile_recipe` flattens B-02B issues into a bare `ValueError`.
   - The research service then reports only `INTERNAL_FAILURE`.
   - Backend rules (even width, even `n_modes`) are plain exceptions, not issues.

B-02B compatibility rules are finite tables of allowed rows. They cannot express
conditions over continuous ranges, such as a warmup requiring a positive PDE
weight. Those conditions become named refusals in the recipe compiler, next to
the existing even-`n_modes` rule, and are reported with the same structured
shape as compile issues.

## Expansion plan, in order

**D0: an honest answer to "can I submit this?"** (delivered in part: defects 1 and 2 are refused by name, and compile now reports every issue with its code and field. Still open: `dry_validate` remains a structural check that accepts unknown backbones, and defects 3 to 5 remain)
- Add a structured `SubmissionAssessment`, returned by an export-and-validate
  operation:
  - the canonical design;
  - the resolved defaults;
  - the implementation identities;
  - a status (research-only, validator-rebuildable in DEVELOPMENT, or
    admitted);
  - each blocker, naming its code and exact field.
- Carry B-02B issue codes and paths through to the miner, including the
  offending key for `parameter.unknown`.
- Refuse defects 1 to 4 by name.
- Correct the receipt (defect 5).

No new capability is added in this step.

**D1: expose what already exists (about 3 to 5 days)**, in this order (all four lab families delivered; the weight-decay mask remains):
1. physics attention, with `heads`, `slices` and `expansion`;
2. the Haar wavelet operator, with `wavelet_levels`;
3. graph operators, with `graph_radius` and `latent_points` and a resource
   forecast entry;
4. the weight-decay mask policy.

Each item gets:
- catalog surfaces with backbone applicability;
- a `_BACKBONES` or target mapping;
- compile-time rules;
- a row in the controls test.

**D2: Foundax FNO as its own backbone.** It gets its own surface subset and its
own documented schedule semantics, so a field name never means two different
curves.

**D3: richer training recipes.** Each of these is a Carbon implementation plus a
catalog surface:
- registered loss terms with weights;
- registered schedule families;
- explicit training stages with a step allocation, such as supervised fitting
  then physics fine-tuning;
- training-data policies within the permitted TRAIN support: sample counts,
  resolution, curriculum and emphasis. These use Carbon's own reconstruction
  randomness, never miner data.

**D4: structured templates.**
- Carbon-owned hybrid templates with declared learned slots (for example a
  solver with a learned closure).
- A symbolic model family whose coefficients Carbon fits during reconstruction.

Each step must preserve:
- the independent exam and the current scientific criteria;
- the declared comparison resources;
- the validator's own pinned image.

Widening the catalog adds no scoring rule, no miner-selected tolerance and no
arbitrary resource envelope.

## Beyond the installed lab: the wider inventory (second pass, 2026-09-23)

The map above covers what Carbon can already rebuild. A miner with the full
research environment can discover far more. Under the declarative rule, each
discovery is a gap until Carbon registers it.

### Cost bands

The worker image installs only the `science-jax` group: jax, equinox, optax,
foundax 0.2.0, chex and einops, all pinned by the profile's environment digest.
That fixes three cost bands:

- **In the vendored lab:** mapping only.
- **In foundax or optax:** an adapter, with no new dependency.
- **Only in PyTorch or Julia:** a new registered backend image, with its own
  determinism and security review.

### What foundax 0.2.0 provides

foundax 0.2.0 ships architecture definitions only. It contains no weights and no
loaders.

- **Fit Carbon's direct-prediction interface in 1D:**
  - `deeponet`, with branch, trunk and combination variants;
  - `unet1d`, which must pin a deterministic norm;
  - `mgno1d`;
  - `pointnet`;
  - `gnot`, `cgptno` and `moegptno`;
  - `geofno` and `pcno`.
- **Need a 2D or 3D Challenge:**
  - `fno2d` and `fno3d`;
  - `unet2d` and `unet3d`;
  - `cno2d` and `mgno2d`;
  - `pit`.
- **Named foundation models:** `poseidon`, `dpot`, `mpp`, `morph`, `pdeformer2`,
  `prose`, `bcat` and `walrus`. Without pretrained weights they are only
  architectures, and pretrained state is outside the current contract.

### Engineering-only batch (no owner decision needed)

1. Remaining lab families: the Haar wavelet operator, GNO and GINO.
2. Optimizer families from optax behind a closed choice:
   - Lion, LAMB, Adafactor and RAdam;
   - NAdamW and SGD with momentum;
   - Muon, Prodigy and schedule-free;
   - SAM.
3. Learning-rate schedule families from optax, plus reduce-on-plateau driven by
   TRAIN loss only.
4. The weight-decay mask, lookahead and skip-nonfinite wrappers.
5. foundax DeepONet variants.
6. Weight averaging (SWA or tail averaging).
7. New loss terms: spectral or frequency weighting, time weighting, and Sobolev
   terms beyond H1.
8. Explicit training stages with a per-stage step split and optimizer, for
   example supervised fitting then physics fine-tuning, or an L-BFGS polish.
9. Architecture detail fields (activation, normalization, initialization), and
   DeepONet depth.
10. A rollout or learned time-stepper predictor adapter. It is large, but it
    leaves the exam unchanged.

### Owner decisions required before these can proceed

- **Training-data knobs** (TRAIN case count, grid resolution, number of times):
  these set a data-generation budget and change the declared TRAIN support.
- **Label method:** choosing it touches reference-solver authority.
- **Curriculum and adaptive sampling:** these need the `R_strategy` vocabulary
  ratified (MQ-024). Sampling must stay TRAIN-only.
- **Burgers symmetry augmentations:** deciding which transforms preserve the
  Challenge's invariants is a scientific decision. A Galilean boost, for
  example, changes the mean.
- **Conservation penalties built from exam measurement code:** they must not
  collapse the separation between candidate and measurement.
- **Solver hybrids and closures:** the FV and ETDRK4 solvers are the exam's
  reference and witness methods. A candidate-side solver template may need to
  be registered independently.
- **Ensembles:** these need a resource envelope.
- **Precision beyond float32:** this sets the reproducibility tolerance.
- **2D and 3D families:** these need a new Challenge.
- **PyTorch and Julia reconstruction backends:** these need image and security
  review.
- **Pretrained weights:** these raise provenance and licensing questions and are
  currently forbidden.

### Stays excluded

- arbitrary losses as expressions;
- composition graphs;
- custom datasets;
- miner seeds;
- checkpoint selection on final labels.

### Known gaps

- **`dry_validate` still accepts backbones with no rebuild path** (`uno` and
  `physicsnemo_fno`).
- **The Burgers challenge kit is research-only.** Reconstruction always trains
  on the controller's own TRAIN archive.
- **A family name does not fix its meaning.** Families with the same name in
  JAX, PyTorch and Julia are not equivalent, so Carbon documents its own meaning
  for each family it registers.
