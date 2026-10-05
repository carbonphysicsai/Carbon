# Battery Level 1, loss expressions: drafted-surface review packet

**Status: DRAFT FOR THE TEST LEAD'S REVIEW.** Nothing here is registered,
wired or opened. `development_variant_policies/registry.json` is unchanged,
`training.py` and the pod phase read no expression, and battery's
miner-facing contract keeps `objective.loss_expressions` excluded. The build
PR follows the review.

**Authority.**
- OWNER-GRAPHITE-TEST-WAVE-03 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`)
  §1: development-only variants for Graphite; "construction-side freedom is
  made as wide as can be tested".
- OWNER-GRAPHITE-DEV-LEVELS-01 F1 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-DEV-LEVELS-01.md`,
  carbonphysicsai/Carbon#589): "Drafted surfaces OK". A development-only
  variant may widen to a surface Carbon drafts, reviewed by the Test Lead and
  recorded as a registered, versioned policy with its bounds.
- The Test Lead's direction: draft each level as wide as Carbon can rebuild
  and test, and for Level 1 consider widening the GA-D6 bounds (depth, node
  count, operations) to whatever the trainer can rebuild deterministically.
- The mechanism: GRAPHITE-DEV-VARIANTS-01 and
  `carbon/reconstruction/development_variants.py` (W1, #589).

**What this packet contains.** The Test Lead's five items, in order:
1. the capabilities and bounds as a draft registered, versioned policy, with
   the measurements behind each bound;
2. the attack surface the level opens, by Track A family;
3. how Carbon rebuilds it, with evidence, and the wiring the build PR needs;
4. matched valid and attack panels;
5. the ablation and combined-permission plan.

Then the build steps and the open questions.

**Files on this branch.**
- This packet.
- The draft variant document:
  `carbon/reconstruction/development_variant_policies/drafts/battery-l1-loss-expressions-v1.draft.json`.
- The measurement script: `scripts/dev/l1_loss_expression_measure.py`, and its
  raw output, `docs/development/graphite/L1_LOSS_EXPRESSIONS_MEASUREMENTS.json`.

**Where the files classify.** `scripts/dev/classify_changes.py` puts the
draft document and the script under the runtime prefix and classifies
`docs/development/graphite/` as an unknown path, which fails closed. Either
way the branch takes full runtime acceptance. No runtime behaviour changes.

---

## Summary

| | GA-D6 draft (`carbon/battery/level1_draft.py`) | Proposed `battery-l1-loss-expressions-v1` |
|---|---|---|
| Terms | 7 per-case terms | the 7, plus 8 per-component terms (squared error and target energy for voltage, temperature, plating margin and capacity), plus 3 per-time terms |
| Operations | add, mul, div, scale, pow, log1p, sqrt | the 7, plus max, min, cap, excess, expm1 (capped argument), and the time reductions mean_t and max_t |
| Depth / nodes / add arity | 4 / 16 / 8 | 24 / 256 / 16 |
| scale | [0, 10] | [0, 100] |
| pow exponent | [0.5, 2] | [0.25, 4] |
| New constants | none | cap `at` and excess `over` in [0, 1e4]; expm1 `cap` in [0, 16] |
| epsilon | 1e-6 | 1e-6 (unchanged; it is `training.case_loss`'s) |
| Left out | exp, min, max, conditionals | raw sub, neg, abs and exp; reductions across cases; constant leaves; conditionals |

The headline evidence, measured on CPU with the pinned stack (jax 0.10.2,
numpy 2.4.6):
- **Rebuild is bit-identical.** Across two clean processes, JAX float32 loss
  values and gradients for 120 random expressions at the proposed limits, on
  two data regimes, hash identically. Short jitted fits of 9 expressions up to
  152 nodes give identical parameters in both processes. Carbon's L-BFGS
  polish over kinked expressions is identical too.
- **numpy is not JAX.** numpy and JAX agree only to a tolerance on the
  transcendental operations, so the rebuild must be JAX against JAX, never a
  numpy recomputation (§1.4, table E).
- **The non-negativity invariant is the line that matters.**
  - With raw sub and neg, 85 of 200 random expressions give a negative
    per-case loss, and 22 make `hard_example_weight`'s weights non-finite.
  - A loss unbounded below goes non-finite in 11 gradient steps.
  - With raw sub, neg and exp added, about 30 % of random expressions are
    non-finite even at a perfect fit, in float64 as in float32.
  - Every proposed operation keeps a non-negative argument non-negative.
- **Overflow by composition cannot be removed by per-operation bounds.**
  - The GA-D6 draft already has it, as gradient blowups.
  - With the proposed set it is rare: in float32, 1 to 2 of 200 expressions
    at the limits have a non-finite loss and 1 to 5 a non-finite gradient,
    depending on the regime. In float64 there are none.
  - It is the construction's own failure: non-finite predictions fail the
    frozen rule's `schema_finite` gate. The build PR must prove it is never
    typed `FAILED_INFRA`.
- **Cost is small.** At 256 nodes, a value-and-gradient step of a width-256
  MLP over battery-shaped data costs about 1.35x the Level-0 menu's, and it
  compiles in under a second, on CPU.
- **Two defects in the shipped module** (both fixable, both for the build PR):
  an oversized integer constant raises an untyped `OverflowError`, and a
  deeply nested document raises an untyped `RecursionError` in `from_bytes`.
  Either could be typed as infrastructure failure, which is a refund path.

---

## 1. The capabilities and bounds, as a registered, versioned policy

### 1.1 The draft document

`carbon/reconstruction/development_variant_policies/drafts/battery-l1-loss-expressions-v1.draft.json`
is written in W1's schema (`carbon.construction-development-variant.v1`):
- version `battery-l1-loss-expressions-v1`, battery, level 1;
- base contract `sha256:eb0241b5…238e` at expansion record 1 (the live
  battery contract, checked fresh on 2026-10-05);
- one widened capability, `objective.loss_expressions` (field
  `loss_expressions`), with `surface: null`, because an expression is not a
  catalog field, and the bounds object below;
- `applies_to: ["deeponet", "mlp"]`, the families whose JAX trainer
  (`training.train`) would read it;
- `participant_code: false`.

**It is deliberately unloadable.** Its `review` is
`{"reviewer": "HUMAN_INPUT", "record": "HUMAN_INPUT"}`, and
`DevContractVariant.from_document` refuses it
(`development_variant_malformed: review names its reviewer and record`).
With the review filled in a scratch copy, the document passes
`from_document`, so its shape is valid. It is not in `registry.json`:
`load()` returns no version and `variant(battery, 1)` raises
`development_variant_unregistered`.

**Why the shipped directory, in `drafts/`.** Nothing in the shipped
directory refuses a subfolder:
- `load()` reads only `registry.json` and the versions it pins;
- the package data glob (`development_variant_policies/*.json`) does not
  recurse, so the draft does not ship in a wheel;
- no test lists the directory.

The draft sits beside the registry it would join, and it cannot be loaded
by accident. If the Test Lead prefers, it moves under `docs/` unchanged.

### 1.2 The expression language (v2 of `carbon.loss-expression`)

A loss expression is data, never code: a tree over a closed operation set,
validated, canonicalized, pinned by digest and evaluated by Carbon's code.
The v1 module's rules are kept: exact node fields, registered terms only,
finite constants in range, commutative arguments sorted, depth and node
counts bounded, `from_bytes` refusing another operation set.

**Two sorts.** Every node is either:
- **case-sorted**: one value per TRAIN case. This is the v1 language;
- **time-sorted**: one value per case and time. It is evaluated once per
  trajectory (normalized voltage, normalized temperature), because the two
  trajectories need not have the same length (`Layout.nv` is `g` or `g - 1`,
  `Layout.nt` is `g - 1`).

Elementwise operations take arguments of one sort. A reduction turns a
time-sorted argument into a case-sorted value. The whole expression is
case-sorted, so the trainer still averages one loss per case under its case
weights.

**Terms.** Each is non-negative, computed from TRAIN outputs, TRAIN targets and
the output weights only, as `training.case_loss` computes its menu terms:

| Sort | Term | What it is |
|---|---|---|
| case | `sq_error`, `target_energy`, `traj_ramp_early`, `traj_ramp_late`, `traj_d1`, `traj_d2`, `traj_spectral` | the 7 GA-D6 terms, unchanged |
| case | `sq_error_{voltage,temperature,plating,capacity}` | each output group's share of `sq_error` (the groups of `MLP._group_weights`) |
| case | `target_energy_{voltage,temperature,plating,capacity}` | each output group's share of `target_energy` |
| time | `err_sq_t` | the squared normalized trajectory error at each time |
| time | `time_t`, `time_rev_t` | the time coordinate, 0 to 1 and 1 to 0 |

The component terms sum to `sq_error` to 4e-16 relative. The time terms
restate the menu's ramps: `mean_t(over both, scale(2, mul(time_t, err_sq_t)))`
equals `traj_ramp_late` exactly in the measurement.

**Operations.** Every one keeps non-negative arguments non-negative:

| Operation | Computes | Constant and range |
|---|---|---|
| `add` | a + b + … | 2 to 16 arguments |
| `max`, `min` | elementwise maximum or minimum | 2 to 16 arguments |
| `mul` | a · b | |
| `div` | a / (b + ε) | |
| `scale` | by · a | `by` in [0, 100] |
| `pow` | (a + ε) ^ p | `exponent` in [0.25, 4] |
| `log1p` | log(1 + a) | |
| `sqrt` | √(a + ε) | |
| `cap` | min(a, at) | `at` in [0, 1e4] |
| `excess` | max(a − over, 0) | `over` in [0, 1e4] |
| `expm1` | e^min(a, cap) − 1 | `cap` in [0, 16] |
| `mean_t`, `max_t` | the mean or maximum over time, summed over the trajectories named by `over` | `over` in {both, voltage, temperature} |

ε is 1e-6, `training.case_loss`'s relative-loss epsilon. Limits: depth 24,
256 nodes, variadic arity 16.

**Replaces the menu.** An expression replaces `relative_loss`,
`time_weighting`, `h1_weight`, `h2_weight` and `spectral_weight`. A
strategy supplying any of them beside an expression is refused, by the
contract's own rule that a supplied field must change what Carbon rebuilds
(`compile.rebuild_issues`).

### 1.3 How each bound was chosen

The rule applied: a bound is as wide as Carbon can rebuild deterministically
and evaluate without a numerical hazard **that a single operation causes on
ordinary TRAIN-scale inputs**. Hazards that only arise by composing
operations (overflow of a long product chain) cannot be removed by
per-operation bounds once `mul` and `pow` nest. The packet does not narrow
the surface for them; they are typed as the construction's own failure
(section 2, R1).

| Bound | Proposed | Why this value | Evidence |
|---|---|---|---|
| depth / nodes | 24 / 256 | No determinism limit was found: values, gradients and fits rebuild bit for bit at these limits. The limit is cost: at 256 nodes a step costs ~1.35x the menu's and compiles in under a second; at 512 the step is ~1.8x. Depth 24 is far inside Python's recursion limit for Carbon's evaluator and canonicalizer | §1.4 tables C, D |
| variadic arity | 16 | Arity is bounded by the node count anyway; 16 lets a sum or maximum cover every registered case term | |
| non-negativity | every operation | Keeps `hard_example_weight`'s `(loss / mean) ** w` defined, keeps `sqrt`, `log1p` and `pow` in their domains, and keeps the loss bounded below | table B: 0 non-finite weights with the proposed set, 22 of 200 with raw sub/neg; divergence in 11 steps for `neg(sq_error)` |
| `scale` | [0, 100] | Linear; a hundredfold weight on a TRAIN-scale term stays far inside float32. Wider than the menu's 0–10 so a recipe can weight a small component term against `sq_error` | table A |
| `pow` exponent | [0.25, 4] | At exponent p and the smallest argument ε, the derivative is p·ε^(p−1): about 8e3 at 0.25 and finite in float32. Exponent 4 on the largest measured term (about 1.8e4, in the divergence regime) is about 1e17, far from float32's 3.4e38 | table A |
| `cap` / `excess` threshold | [0, 1e4] | The measured span of the terms (`term_ranges` in the raw output): the error terms stay below 2 in the typical regime and below 40 at initialization, and reach about 1.2e4 for `sq_error` (1.8e4 for `err_sq_t`) only when diverging. The target energies stay below 13. Beyond the span the operation is the identity or a constant | raw output |
| `expm1` cap | [0, 16] | e^16 ≈ 8.9e6 bounds the value and its derivative; raw `exp` is non-finite on ordinary terms | table A, raw row |
| ε | 1e-6 | Unchanged from `training.case_loss` | |

### 1.4 The measurements

Method, in `scripts/dev/l1_loss_expression_measure.py`, raw output in
`docs/development/graphite/L1_LOSS_EXPRESSIONS_MEASUREMENTS.json`:
- **Prototype.** The script holds a prototype of the proposed language
  (canonicalizer and evaluator, mirroring `loss_expressions.py`). It changes
  nothing in the repository.
- **Data.** Battery-shaped arrays: 400 TRAIN cases, 246 outputs (121
  voltage, 120 temperature, 1 plating, 4 capacity), the trainer's group
  weights. There are five regimes for the prediction error: perfect (0), near
  (0.01), typical (0.3), init (an independent draw) and large (30, a diverging
  network).
- **Expressions.** Random well-sorted expressions at the limits, with
  constants drawn with 30 % at the range endpoints, and every fifth one a
  maximal-depth chain of unary operations.
- **Evaluation.** Each is evaluated in numpy float32 and float64, and in
  JAX float32 and float64 under `jit`, eager, and `value_and_grad` of the
  case-mean loss, as the trainer would trace it.
- **Determinism.** Checked in two clean processes (`env -i`, CPU only).

**Table A: non-finite loss / gradient, and the largest finite float32
gradient, per regime.**
- Counts are expressions whose case-mean loss (L) or gradient with respect to
  the predictions (G) is non-finite.
- The draft sample is 120 expressions at its limits (depth 4, median 5
  nodes). The proposed sample is 200 at depth 24 / 256 nodes (median 50
  nodes, largest 181). The "+ raw" sample is 120 with raw sub, neg and exp
  added.

| Regime | GA-D6 f32 L/G | GA-D6 f64 L/G | GA-D6 max \|G\| | proposed f32 L/G | proposed f64 L/G | proposed max \|G\| | + raw f32 L/G | + raw f64 L/G |
|---|---|---|---|---|---|---|---|---|
| perfect | 0/0 | 0/0 | 0 | 1/1 | 0/0 | 0 | 35/40 | 36/40 |
| near | 0/0 | 0/0 | 2.0e10 | 1/4 | 0/0 | 5.6e23 | 38/45 | 40/44 |
| typical | 0/0 | 0/0 | 6.9 | 1/4 | 0/0 | 2.5e28 | 39/45 | 41/44 |
| init | 0/0 | 0/0 | 7.8e2 | 1/4 | 0/0 | 1.3e30 | 40/47 | 42/47 |
| large | 0/0 | 0/0 | 3.2e17 | 2/5 | 0/0 | 3.1e38 | 44/54 | 46/54 |

Reading it:
- **The proposed set.** It is finite in float64 on every sample. In float32
  a few long compositions overflow; `culprits` names four distinct
  expressions.
  - One is a 24-deep unary chain: `expm1` applied to `expm1`, then `pow`
    3.3, which overflows even at a perfect fit.
  - The others are 147 to 177-node trees that combine `pow`, `div`,
    `mul` and `expm1`, often on time-only, parameter-free branches, ending in
    `0 · inf`.
  - Each operation is bounded; the composition is not.
- **The raw operations.** Their failures appear in float64 as often as in
  float32. They are not precision artefacts; they are what the operations
  do on TRAIN-scale inputs.
- **The GA-D6 draft.** It already has gradient blowups of 1e10 to 1e17
  (`div` by an error term that approaches 0). Gradient size is not a line the
  draft held either.

**Table B: the non-negativity line.**

| Check | Proposed set | With raw sub and neg |
|---|---|---|
| random expressions with some negative per-case loss (of 200) | 0 | 85 |
| `hard_example_weight` weights `(loss/mean(loss))**0.5` non-finite (of 200) | 0 | 22 |
| 300 gradient steps of `neg(sq_error)`, MLP 4 → 64 → 64 → 246 | not expressible | loss non-finite at step 11 |
| 300 steps of `mean_t(both, time_t)` (a constant) | parameters unchanged, loss 1.0 | |

**Table C: cost** of one jitted value-and-gradient step of an MLP (4 → 256 ×
3 → 246, GELU) on 400 cases, CPU. Each row is the slowest compile and the
median step of up to three random expressions at the limits.

| Limits | Actual depth / nodes | Compile (s) | Step (ms) | Step vs menu |
|---|---|---|---|---|
| Level-0 menu (11 nodes) | 3 / 11 | 0.34 | 4.64 | 1.00 |
| 4 / 16 (GA-D6) | up to 4 / 11 | 0.27 | 4.16 | 0.90 |
| 8 / 32 | up to 8 / 25 | 0.33 | 4.56 | 0.98 |
| 16 / 64 | up to 14 / 41 | 0.50 | 5.26 | 1.13 |
| 16 / 128 | up to 16 / 97 | 0.64 | 5.63 | 1.21 |
| **24 / 256 (proposed)** | up to 21 / 169 | 0.85 | 6.25 | 1.35 |
| 32 / 512 | up to 32 / 264 | 1.58 | 8.32 | 1.79 |

**Table D: rebuild determinism across two clean processes** (JAX float32,
CPU):

| Check | 16 / 128 | 24 / 256 |
|---|---|---|
| sha256 over values, losses and gradients of 120 expressions × 2 regimes | identical | identical |
| parameter digests after 100-step jitted fits, 8 random expressions + the menu restated | 9/9 identical | 9/9 identical |
| of those 8, parameters left exactly at the initialization (a dead loss) | 4 | 5 |
| `training.polish` (L-BFGS, 25 steps) over `max`, `max_t`, `excess`, a saturated `cap` and a smooth control | 5/5 identical, all finite | |

**Table E: numpy against JAX, same expression and data** (400 samples: 200
proposed expressions × typical and init regimes):

| Comparison | Bit-identical | Median relative difference | Largest relative difference |
|---|---|---|---|
| numpy f32 vs JAX f32 (jit) | 208 / 400 | 0 | 2.3e-4 |
| numpy f64 vs JAX f64 (jit) | 225 / 400 | 0 | 1.9e-14 |
| JAX jit vs JAX jit, same process | 400 / 400 | 0 | 0 |
| JAX eager vs JAX jit | 250 / 400 | | |
| GA-D6 draft: numpy f32 vs JAX f32 | 16 / 240 | 2.7e-7 | 2.2e-6 |

The non-finite pattern always agreed between numpy and JAX for the proposed
set, and the canonical form was stable:
- shuffling every commutative argument list gave the same canonical form,
  200 / 200;
- the canonical-bytes round trip gave the same form, 200 / 200.

**Table F: probes of the shipped module** (`loss_expressions.py`, GA-D6
operation set):

| Input | Result today | Should be |
|---|---|---|
| `scale` by `True` | `by_outside_bounds` | as is |
| `scale` by a NaN token through `from_bytes` | `by_outside_bounds` | as is |
| an object nested 5 000 deep through `compile_expression` | `too_deep` | as is |
| `scale` by the integer 10**400 | **untyped `OverflowError`** | `by_outside_bounds` |
| a document nested 200 000 deep through `from_bytes` | **untyped `RecursionError`** | a typed refusal before parsing |
| `scale` by −0.0 | accepted, with a digest different from +0.0 | normalized to +0.0 |
| non-canonical (indented) bytes through `from_bytes` | accepted; same digest | refused unless canonical (the rebuild reads canonical bytes only) |
| a duplicate key (`{"term": "traj_d1", "term": "sq_error"}`) | accepted, the last key wins | refused |
| `scale` by 5e-324 (subnormal) | accepted | as is (finite, in range) |
| `scale(1, sq_error)` beside `sq_error` | two digests | as is; see U3 |

---

## 2. The attack surface, by Track A family

The surface widens what a construction may ask Carbon's trainer to minimize
on TRAIN. It reads nothing new: every term is a function of TRAIN outputs,
TRAIN targets and the output weights. It does not touch the exam, the score,
the disclosure rule or the evaluator. So the risks are on Carbon's side of
the build (typing, cost, identity) and in how well the frozen rule's score
tracks value when training can aim at it more precisely.

| Track A family | What the surface opens | Expected verdict | Fixable? |
|---|---|---|---|
| `baseline_and_permission_ablation` | an expression at Level 0, at a miner door, or with the variant digest named at the intake | REFUSED: `parameter.not_rebuildable` at Level 0; `development_variant_not_served` at every miner door (W1) | already held |
| | an expression beside a menu field, on `knn` or `fno`, or with `backend: pytorch` | REFUSED: `parameter.dependency_unsatisfied` / `development.not_applicable` | build PR (B4, B5) |
| `artifact_and_dependency_attacks` | unregistered term or operation (`label`, `reference_voltage`, `exp`, `sub`, `where`), extra node fields, a constant out of range or non-finite, a `bool` constant | REFUSED by code (`term_not_registered`, `operation_not_in_the_set`, `node_fields`, `<field>_outside_bounds`) | already held |
| | an integer constant 10**400 | **untyped `OverflowError`** today | yes: refuse it as `<field>_outside_bounds` (B1) |
| | a document nested 200 000 deep through `from_bytes` | **untyped `RecursionError`** today | yes: bound the byte size and the nesting before parsing (B1) |
| | non-canonical bytes, a duplicate JSON key, −0.0 | accepted today; the identity is the recompiled digest; −0.0 gets its own digest | yes: require the canonical bytes exactly and normalize −0.0 (B1) |
| | many digests for one loss (`scale(1, E)`, `cap(E, 1e4)` above every value, reordered non-commutative forms) | distinct digests for the same loss | **no, not at the surface** (U3) |
| `score_exploitation_and_tail_failures` | a loss aimed at the frozen rule's components (for example the four component terms, each weighted) | a valid construction, scored by the frozen rule | **no; it is the surface's purpose** (U1) |
| | tail sacrifice: `cap`, `min`, `sqrt`, `log1p`, `pow` with exponent below 1 all down-weight large errors | trains; the frozen rule's gates and tail metrics decide | **no, not at the surface** (U2) |
| | degenerate losses: constant (`mean_t(time_t)`), saturated (`cap` at 0, `expm1` cap 0), adversarial denominators (`div(sq_error, traj_d1)` rewards rough trajectories) | trains to the initialization or to a poor model, deterministically; scored, gate-failed or poor | partly (U4) |
| | a loss unbounded below or non-finite on ordinary inputs | not expressible: raw sub/neg/exp are left out | held by the set |
| `adaptive_feedback_and_state_attacks` | a far larger space of distinct constructions for repeated practice queries | no new disclosure: practice feedback, the TRAIN-loss history and the hidden pool are unchanged | rate limits and attack budgets, as now (U5) |
| `resource_and_failure_accounting` | expensive expressions | bounded by 256 nodes: ~1.35x step, < 1 s compile on CPU; past the deadline it is `CANDIDATE_RESOURCE_EXCEEDED` | held by the bound |
| | overflow by composition | non-finite parameters, non-finite predictions, `schema_finite` FAIL, so `GATE_FAILED`; never `FAILED_INFRA` | must be proven in the build PR (R1, B7) |
| | crash-to-refund: an expression that makes Carbon's compile raise an untyped error | today two inputs do (above); the host compiles before launch, so the pod never runs | yes (B1) |
| | interactions: `hard_example_weight`, the plateau curve, the L-BFGS polish, float64, microbatches | finite and deterministic with a non-negative loss (table B, the polish check) | held by non-negativity |
| `construction_evaluation_isolation` | none new: the expression is interpreted by Carbon's code over a closed set; `participant_code` is false | no participant code runs | held |
| `reconstruction_and_recipient_rebuild` | the rebuild must reproduce the trained parameters | bit-identical JAX against JAX across processes (table D); the expression's digest is bound in `development.widened_digest` | held, if the rebuild never substitutes numpy (R2) |
| `fresh_attack_confirmation` | any score-exploitation result above | confirmed on fresh cases before it is believed, as now | unchanged |

**Required behaviours the build PR must prove** (each a test):
- **R1.** A non-finite TRAIN loss or non-finite parameters is the candidate's
  failure:
  - the predictions are non-finite and the frozen rule types them
    `GATE_FAILED`;
  - a pod run that ends this way is typed by `pod_outcome` as a candidate
    outcome, which it may be, since Level 1 is a trusted-writer level in the
    v1 attribution policy;
  - it is never `FAILED_INFRA` and never refunded.
- **R2.** The reconstruction rebuilds with the same JAX trainer path. numpy is
  used only for tolerance checks, never as the rebuild.
- **R3.** Every compile-time refusal is an `ExpressionRefused` with a code,
  raised on Carbon's host before a pod is launched.

**What cannot be fixed if the surface is widened.** None of these lets a
construction read hidden material or change the grade. They are the
surface's cost, recorded so the owners can weigh it against the freedom:
- **U1. Metric-aimed training.** An expression can aim training at the frozen
  rule's components far more precisely than the menu can. Where the score
  and value disagree, Level 1 finds the disagreement faster. This is a
  score-to-value alignment question (τ/ρ, regret, false-feasible rate), which
  the wave measures side by side with the freedom. No bound on the surface
  removes it without removing the surface.
- **U2. Tail sacrifice.** Any sub-linear transform of the error (`sqrt`,
  `log1p`, `pow` below 1, all already in the GA-D6 draft, and `cap` and `min`
  here) lets training give up on hard cases. Only the frozen rule's gates and
  tail metrics, on hidden and fresh cases, can catch a score that improves
  that way.
- **U3. Identity aliasing.** Two expressions with different digests can be
  the same loss, and deciding equivalence in general is not practical.
  Anything that counts novelty by expression digest can be farmed. The
  mitigation is to count by the rebuilt artifact (the trained parameters'
  digest), not by the expression.
- **U4. Dead and degenerate losses.** A loss can be constant, saturated, or
  can reward error through a denominator.
  - Static checks can catch some cases: an expression with no error-bearing
    term, a `cap` at 0. Run-time saturation cannot be caught statically.
  - In the deterministic-fit sample, 4 of 8 random expressions at 128 nodes
    and 5 of 8 at 256 nodes left the parameters exactly at their
    initialization.
  - These are harmless if typed and scored as the candidate's own result.
    The packet does not refuse them (open question Q3).
- **U5. Search amplification.** A space this large gives an adaptive
  participant many distinct constructions per unit of practice. The free
  loop's intentional incompleteness and the rate limits carry this, as at
  Level 0.

---

## 3. How Carbon rebuilds it

### 3.1 The reconstruction rule

The reconstruction rule (OWNER-GRAPHITE-02, W1's `RECONSTRUCTIONS`):
1. **Compile from bytes.** Carbon recompiles the expression from its
   canonical bytes, against the operation set whose digest the variant's
   bounds pin (`loss_expressions.from_bytes`).
2. **Require canonical bytes.** The bytes must equal the canonical bytes
   exactly (B1). A different operation set is refused
   (`operation_set_mismatch`).
3. **Evaluate with Carbon's code.** Carbon's evaluator runs inside Carbon's
   JAX trainer. Nothing the strategy supplies is executed.
4. **Bind the digest.** The built record carries the expression's digest
   through `CompiledDevelopment.development.widened_digest`, so the bundle's
   clean rebuild compares it.

### 3.2 Evidence

- **Cross-process, values and gradients.** 120 expressions at depth 24 / 256
  nodes, two regimes, JAX float32: one sha256 over every value and gradient,
  identical in two clean processes. The same holds at 16 / 128.
- **Cross-process, training.** Jitted `lax.scan` fits (100 steps, MLP 4 → 128
  → 128 → 246) for 8 random expressions up to 152 nodes, plus the
  menu-restating expression: identical parameter digests in two clean
  processes, at both limit settings.
- **L-BFGS polish.** Carbon's `training.polish` (25 steps) over `max` of
  component terms, `max_t`, `excess` and a saturated `cap`, and a smooth
  control: finite, identical in two processes. The saturated cap leaves its
  loss unchanged.
- **Within a process.** `jit` against `jit`: bit-identical for every sample.
  `jit` against eager is not always bit-identical (XLA fuses differently), so
  the rebuild must use the trainer's own jitted path.
- **numpy against JAX.** See tables A and E. Agreement is within a tolerance,
  not bit for bit, because `log1p`, `expm1`, `pow` and the reductions are
  implemented differently.
- **GPU.** Not measured; this work was CPU only. The expression adds
  elementwise operations and mean and maximum reductions over time. The menu
  already uses the elementwise operations and the mean, the maximum is
  order-independent, and the pod pins `--xla_gpu_deterministic_ops=true`
  (`carbon/reproducibility/development.py`). GPU bit identity is open
  question Q6.

### 3.3 Where it plugs in

- **`RECONSTRUCTIONS[(battery, "objective.loss_expressions")]`** is a function
  `(value, admitted) -> record`. It:
  - recompiles the canonical bytes against battery's v2 operation set, after
    checking that the set's digest equals the one in the variant's bounds;
  - refuses a backend other than JAX and a family outside `applies_to`;
  - refuses any menu field the strategy also supplied;
  - returns `{"expression_digest", "operation_set", "canonical"}`.
- **`compile_development`** already:
  - splits `loss_expressions` from the base parameters;
  - compiles the rest through `compile_submission`;
  - calls the reconstruction;
  - binds `development.widened_digest`.

  `Widened.within` returns True for a surface of `null`, so the bounds check
  is the reconstruction's own, as GRAPHITE-DEV-VARIANTS-01 intends.

### 3.4 Trainer wiring needed

No path reads an expression today. The build PR needs:
1. **The recipe carries it.** `BatteryRecipe` (or the built record's
   `development` section) carries the compiled expression's canonical
   document, so the program's staged files include it and the pinned
   `expected` digests cover it.
2. **The general loop is taken.** `MLP._classic` returns False whenever an
   expression is present. Otherwise a default-valued recipe silently trains
   with the written-out loop and ignores the expression.
3. **The trainer reads it.** `training.train` and `train.case_loss`: when an
   expression is present, `case_loss` returns
   `evaluate(compiled, terms(...), jnp)`:
   - `terms` computes the 15 case terms and the per-trajectory time terms
     from `zhat`, `zt`, `gw`, the trajectory map and the layout's group
     boundaries;
   - in PCA mode the boundaries are those of the coefficients;
   - when no expression is present, the menu code is untouched, so every
     Level-0 recipe traces exactly as before.
4. **The torch backend.** `torch_training` has its own `case_loss`; v1 does
   not wire it, and the reconstruction refuses `backend: pytorch`.
5. **The pod phase.** `pod_phase.run` already chooses
   `development_built_record` when the job names a variant. The program it
   runs must stage the expression with the recipe (point 1).
6. **The time terms** are added to `level1_draft.terms` (or its successor)
   and the operation set's documented schema moves to
   `carbon.loss-expression-operation-set.v2`, beside the v1 set, which stays
   as it is for its existing tests.

---

## 4. Matched panels

Every panel item runs under the previous profile (Level 0) and the expanded
profile (the variant), as `climb.py` requires, with the same attack budget
under each. The previous-profile runs of items that use the expression must
come back REFUSED.

### 4.1 Valid constructions

They start from EV4's trained panel member (`mlp`, the adapter's
`TRAINED_PANEL`). Each is expected to help on some axis; that is a
hypothesis the climb tests, not a claim.

| Id | Expression | Why it might help |
|---|---|---|
| `valid_menu_restated` | `menu_expression(the recipe's own menu settings)` | Control: the Level-0 objective restated. It should rebuild and score as the menu recipe does, to tolerance. It tests the wiring, not a benefit |
| `valid_component_relative` | `add(div(sq_error_c, target_energy_c))` over the four components | Balances each output group by its own scale (a weighted relative loss) |
| `valid_plating_emphasis` | `add(sq_error, scale(4, sq_error_plating))` | Physics-term emphasis on the plating margin, the safety-relevant output |
| `valid_late_voltage` | `add(sq_error, mean_t(voltage, mul(pow(time_t, 2), err_sq_t)))` | Emphasizes late-window voltage, where the cutoff knee sits |
| `valid_worst_time` | `add(sq_error, scale(0.1, max_t(both, err_sq_t)))` | Penalizes the worst time point, not only the mean |
| `valid_robust_l2` | `sqrt(sq_error)` | Root error per case: less weight on outlier cases |

### 4.2 Attack constructions

Each declares its violation before it runs.

| Id | Expression or input | Declared violation | Expected verdict |
|---|---|---|---|
| `attack_metric_aimed` | the four component terms weighted to mirror the frozen rule's component weights | scores better than the Level-0 control while value does not improve | runs and is scored; a reproduced violation is a frozen-rule (U1) finding, not a surface defect |
| `attack_tail_sacrifice` | `cap(sq_error, small)` | score improves while important-region or tail cases fail | runs; the frozen rule's gates and tail metrics decide (U2) |
| `attack_constant_loss` | `mean_t(both, time_t)` | a no-op loss is typed `FAILED_INFRA` or refunded | parameters equal the initialization; scored as the candidate's result |
| `attack_overflow` | `pow(pow(pow(scale(100, sq_error), 4), 4), 4)` | non-finite training typed `FAILED_INFRA`, refunded, or crashes Carbon | non-finite predictions, `schema_finite` FAIL, `GATE_FAILED` (R1) |
| `attack_adversarial_denominator` | `div(sq_error, traj_d1)` | beats the Level-0 control | trains toward rough trajectories; scores worse (U4) |
| `attack_compile_bomb` | 256 nodes at depth 24, dense with time reductions | exceeds the deadline or is typed `FAILED_INFRA` | compiles in about a second; inside the deadline |
| `attack_parse_bombs` | the integer 10**400, nesting 200 000 deep, NaN and Infinity tokens, −0.0, a duplicate key, non-canonical bytes | accepted, or an untyped exception | each refused with a code on Carbon's host before launch (R3, B1) |
| `attack_unregistered` | terms `label`, `reference_voltage`, `hidden_case`; operations `exp`, `sub`, `where`, `python` | admitted | `term_not_registered` / `operation_not_in_the_set` |
| `attack_identity_alias` | `scale(1, E)` beside `E`; `cap(E, 1e4)` beside `E` | two digests counted as two novel constructions | reproduced: a known, unfixable-at-the-surface result (U3); the count must use the rebuilt artifact |
| `attack_menu_and_expression` | an expression plus `relative_loss: true` | the menu field is silently ignored | `parameter.dependency_unsatisfied` |
| `attack_wrong_backend` | an expression with `backend: pytorch`, or on `fno` or `knn` | the expression is silently ignored | `development.not_applicable` |
| `attack_miner_door` | the expression at Level 0 through the miner path; the variant digest at the intake | admitted to a miner | REFUSED (`parameter.not_rebuildable`; `development_variant_not_served`) |

Today's adapter (`attack/adapters/battery.py`) has the seam
`level_1_loss_expressions`, which waits for an expansion record. Its
`_climb_items` holds one Level-1 attack, `attack_loss_expressions_draft`,
which checks only that Level 0 refuses the field. The build PR replaces that
with the panels above, run against the variant.

---

## 5. The ablation and combined-permission plan

The plan follows `climb.py`, with `development_variant` set to the
registered variant's digest, so the climb continues past a finding and tags
what follows it (`COMPLETED_CONDITIONAL`).

**Step 1, valid.** The panel in 4.1 under Level 0 and the variant.
`valid_menu_restated` must agree with its Level-0 twin to tolerance.

**Step 2, matched attacks.** The panel in 4.2 in full under both profiles
(`attack_budget` = 12, the attack set's size).

**Step 3, single-permission ablation.**
- **The permission.** The variant adds one permission,
  `objective.loss_expressions`. Its ablated profile is exactly Level 0.
- **What must happen.** Every valid item and attack that uses the expression
  must come back REFUSED. One that runs is a `permission_not_enforced`
  finding.
- **Operation-family arms.** One capability hides several widenings, so the
  panel also carries matched arms. They are not climb permissions. Each valid
  item that uses a v1 feature gets a twin restricted to the GA-D6 set, the
  nearest expressible form. The arms are:
  - time reductions;
  - `max`, `min`, `cap` and `excess`;
  - `expm1`;
  - component terms;
  - the wider constants.

  The difference measures what each widening adds over the conservative
  draft. If the Test Lead wants these as true ablations, each becomes its own
  capability id in a later variant version (open question Q2).

**Step 4, combined-permission attacks.** Each pairs the expression with a
Level-0 permission that changes how the loss is consumed:

| Id | Pairs with | What it checks |
|---|---|---|
| `combined_hard_example_weight` | `training_data.hard_example_weight` | `(loss/mean)**w` stays finite with a saturating expression |
| `combined_polish` | `stages.polish_steps` | the L-BFGS line search on kinked losses stays finite and deterministic |
| `combined_plateau` | `schedule.learning_rate_curve = train_loss_plateau` | a flat (capped) loss only halves the rate; nothing non-finite |
| `combined_float64` | `inference.precision = float64` | the float64 path rebuilds bit for bit |
| `combined_microbatches` | `batching.microbatches` | accumulation over chunks equals the per-case definition; deterministic |
| `combined_trajectory_components` | `architecture.trajectory_components` | the time terms are computed through the PCA trajectory map |
| `combined_bounded_voltage` | `physical_structure.bounded_voltage_head` | the terms in logit space; finite at the bounds |
| `combined_width` | `architecture.width` | the existing interaction item, kept |
| `combined_ensemble` | `inference.ensemble_members` | every member trains with the same expression; the rebuild matches |
| `combined_curriculum_weights` | `training_data.curriculum`, `training_data.important_region_weight` | case weights times the expression; the weights mean what they meant |

`interaction_coverage` must list each of them. Any new permission left
without a combined attack is `NOT_RUN`, never passed.

**Step 5, reconstruction.** Every valid item that the plan marks promising
gets a clean rebuild, which must match.

**Reporting.** The report records the freedom granted, the score-to-value
alignment (τ/ρ, regret, false-feasible rate) and the findings split into
fixable and not fixable, as WAVE-03 asks. It claims no level TESTED and opens
nothing.

---

## 6. Build steps for the follow-up PR

1. **B1, harden the shipped module** (`carbon/reconstruction/loss_expressions.py`):
   - refuse an integer constant that does not convert to a finite float
     (`<field>_outside_bounds`);
   - normalize −0.0 to 0.0;
   - in `from_bytes`, bound the byte length and the nesting before
     `json.loads`, refuse duplicate keys (`object_pairs_hook`), and require
     the input to equal the canonical bytes;
   - every refusal is an `ExpressionRefused` with a code.
2. **B2, the v2 language.** Sorts, the new terms and operations, `over` on
   reductions, as a v2 operation-set schema beside v1. The proposed
   operations' semantics are exactly the prototype in the measurement
   script.
3. **B3, battery's v2 operation set and terms** in `carbon/battery/level1_draft.py`
   (or a successor module), with the component groups taken from the
   recipe's layout.
4. **B4, the reconstruction** registered in `RECONSTRUCTIONS`, as in 3.3.
5. **B5, the compile rules.** Refuse menu fields beside an expression; refuse
   a non-JAX backend and the `fno` and `knn` families.
6. **B6, the trainer wiring** in 3.4, with a test that every Level-0 recipe
   traces and trains bit-identically before and after.
7. **B7, the typing tests R1–R3**, including a pod-phase test that a
   non-finite fit is a candidate outcome and never `FAILED_INFRA`.
8. **B8, register the variant.**
   - Fill the review with the Test Lead's review record and move the
     document to `development_variant_policies/battery-l1-loss-expressions-v1.json`.
   - Pin its digest in `registry.json` and make it `current` for
     (battery, 1).
   - Write the development expansion record
     (`python -m carbon.reconstruction.development_variants record`).
9. **B9, the attack adapter.** Register the adapter at (battery, 1), its
   contract digest being the variant's. Replace `_climb_items`' Level-1 items
   with the panels in section 4. Set `development_variant` on the climb plan.
10. **B10, the measurement script** becomes a CPU test of the rebuild
    properties (cross-process identity of values, gradients and fits) on a
    small sample, so a later jax or numpy pin change is caught.

---

## 7. Open questions

For the Test Lead:
- **Q1. The limits.** Depth 24 / 256 nodes is a cost bound, not a
  determinism bound: none was found. Raise it, or keep it?
- **Q2. Operation-family ablation.** Matched arms inside one capability, as
  proposed, or one capability id per operation family, each truly ablatable
  in the climb? The second needs a field per family or a variant version per
  family.
- **Q3. Degenerate losses.** Refuse statically detectable no-op expressions
  (no error-bearing term; a `cap` or `expm1` cap of 0), or let them run as the
  candidate's own result? The packet leaves them in, for discovery.
- **Q4. Adversarial denominators.** Keep `div` general, or restrict its
  denominator to target-only terms (`target_energy*`)? General `div` lets a
  loss reward error. That harms only the construction, but it widens the
  degenerate class.
- **Q5. The torch backend.** Is v1 JAX-only acceptable, or should the build
  PR also wire `torch_training.case_loss`, with its own rebuild evidence?
- **Q6. GPU bit identity.** Only CPU was measured. Should the build PR's
  climb include a GPU rebuild under a grant, before the variant's results are
  cited?

For an owner, through the Test Lead:
- **Q7. Novelty counting (U3).** Anything that rewards or counts distinct
  constructions must count by the rebuilt artifact, not by the expression
  digest. Is any current or planned count keyed on recipe or expression
  identity?
- **Q8. Alignment versus freedom (U1, U2).** Metric-aimed training and tail
  sacrifice are expected to be reachable at Level 1. The surface cannot
  close them; only the frozen rule can. Whether the frozen rule's tail
  coverage is adequate is a science owner's question. The climb's alignment
  metrics inform it; they do not answer it.

---

## Appendix: reproducing the measurements

From a worktree with the pinned science stack, on CPU only:

```
export JAX_PLATFORMS=cpu PYTHONPATH=$PWD
python scripts/dev/l1_loss_expression_measure.py main OUT.json   # tables A, B, C, E and the probes
python scripts/dev/l1_loss_expression_measure.py fingerprint     # run twice in clean processes; compare
python scripts/dev/l1_loss_expression_measure.py fit             # run twice in clean processes; compare
python scripts/dev/l1_loss_expression_measure.py polish          # run twice in clean processes; compare
python scripts/dev/l1_loss_expression_measure.py culprits        # the non-finite float32 samples
```

`L1_MAX_DEPTH` and `L1_MAX_NODES` override the limits (the 16 / 128 runs).
The `main` run took about seven minutes on a 20-thread CPU. The runs
recorded here used the `claude/dev-contract-variants` base (60889f40f).
