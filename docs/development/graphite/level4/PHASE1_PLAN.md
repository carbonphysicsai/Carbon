# Level 4 Phase 1: plan, Q1–Q3 answers

**For:** the Test Lead
**From:** the Level 4 engineer, 2026-10-07
**Authority:**
- OWNER-LEVEL4-GRAPH-ONLY-01 (D1, approved 2026-10-07): graph-only Level 4,
  roadmap rev 2.3. Phase 1 is go.
- D2–D6 stay the Test Lead's recommendations until the owner rules. Every cap
  stays `HUMAN_INPUT`.
- Development only: nothing miner-facing, nothing in `CONTRACTS`.

**Builds on:** `PHASE0_SPIKE_REPORT.md` (PR #746).

| File | What it is |
|---|---|
| `carbon/level4/allowlist_v1.json` | Allowlist v1: v0 plus named functions. `custom_jvp_call` is refused unless it is a registered kernel |
| `phase1_design_results.json` | The record for Q1 and Q3, and the Phase 0 equivalence re-run under v1 |
| `carbon/level4/named.py`, `carbon/level4/initializers.py`, `scripts/dev/level4_spike/run_design.py` | Q1, Q3 and the record's runner |
| `tests/cpu/test_level4_named_init.py` | Q1 and Q3 tests |

**Progress.**

| Plan PR | State |
|---|---|
| 1 | Merged (#748) |
| 2 | `carbon/level4` core: format, allowlist v1, G4 `validate.py`, named functions, interpreter, initializers, specimens; `tooling/` (miner-side lowering); battery adapter `carbon/battery/level4.py`; `submission.py`, the manifest and canonical-bytes rule the Launchpad slot (LAUNCHPAD-LEVELS-01) and the validator share |
| 3 | G6 `train.py` (Carbon-built init, padded inference, Carbon's key schedule; the Challenge's own loop through its adapter); G4 init data flow (`check_init`) and `validate_submission`; battery `lower_recipe`, `train_graph`; E1 through G3, G4 and G6 (`phase1_e1_results.json`) |
| 6 | `specimens.attack_suite`: one specimen per row of §8.1 and §8.3 under non-production fixture caps; rows no graph gate can test are recorded with their owner |
| 4 | G0 `intake.py` (bounds `HUMAN_INPUT`; an unset bound blocks) with G3's isolated parse (`_parse_worker`: CPU, memory and file limits; a crash or overrun is the submission's refusal, a worker that cannot start is `FAILED_INFRA`); the miner-side CLI `python -m carbon.level4.tooling lower` for the Launchpad |
| 5 | G7 `grade.py`: padded inference, non-finite cases named (the exam's gates type them), inference cost measured from the compiled graph (rule `HUMAN_INPUT`); battery `grade_graph` on public PRACTICE with battery's exam code unchanged. A trained Level 0 graph gets exactly the declarative path's exam verdict |
| 7 | G5 `compile.py`: Carbon's own lane program compiles the rebuilt forward graph, a gradient step and the init graph in the C-03 Carbon lane from staged bytes only; a deadline or in-lane failure is the submission's refusal, any other lane failure `FAILED_INFRA`; the deadline is `HUMAN_INPUT`; the profile is recorded as awaiting the security owner (D3) |
| 10 | E6, motor (`carbon/motor/level4.py`, adapter only; shared code unchanged). Motor has no gradient-trained family. Its Level 0 kernel ridge prediction is lowered to a graph whose parameters Carbon's own closed-form fit supplies at G6, and G7 grades it through motor's unchanged practice exam. Predictions agree with native to float64 rounding (max 1.1e-11 N·m), every case's gate decision is identical, and the score differs by about 1e-13. It is not bit-identical (numpy against XLA). **Open:** gradient training through G6 for a second Challenge needs a trainable family there |
| 8 (part 1) | The development-only Level 4 variant `battery-l4-graph-v1` (LEVEL4-DEV-VARIANT-01). It is graph-only: `hybrid.composition_graphs` widened under allowlist v1, routed through the shared dispatch (BATTERY-DEV-DISPATCH-01), and every rebuild fails closed until D3. Also: the capability draft (`LEVEL4_CAPABILITY_DRAFT.md`, for the owner) and the lesson on lowering at the recipe batch. Part 2 is the `battery_level4` attack adapter |
| 8 (part 2) | The `battery_level4` attack adapter, registered at (battery, 4) against `battery-l4-graph-v1`. It runs seven §8 families at Carbon's real gates (G3 parse, G4 validate, rebuild) and declares six seams NOT_RUN with owners. Every attack is HELD, every specimen FIRES, every control PASSES. Its finding: a document whose declared shapes lie now gets `declared_aval_mismatch` at G4 (abstract evaluation), where before it surfaced only during execution. Dispositions are the Test Lead's |

**Q5 answered (plan PR 3).** Per-case graphs batched by Carbon's `vmap` run
forward bit-identically, but they do **not** train bit-identically for every
family. The classic MLP matches; DeepONet does not, because its gradient
accumulation order changes under `vmap`. So a forward graph is lowered at
the recipe's training batch (`validate(..., batch=)`). Carbon trains at that
batch and pads inference into blocks of it (`Prepared.predict`), which keeps
every case's result the declared graph's.

**Carbon's key schedule.** An init graph returns parameters only, never a
key. Carbon derives the training key itself (`train.keys`), so a submission
cannot steer data order. Full-batch recipes, which include battery's Level 0
recipes, match the declarative path bit for bit (E1). A minibatch recipe
trains deterministically under Carbon's key, which by design is not the
declarative path's.

Reproduce (CPU, development only):

```bash
python scripts/dev/level4_spike/run_design.py docs/development/graphite/level4/phase1_design_results.json --adapter battery
```

---

## 1. Q1: custom derivative rules as named functions (built and shown)

**The problem (Phase 0).** A `custom_jvp_call` carries its derivative rule as
a Python callable. B′ v0 kept the primal body and let Carbon differentiate
that instead. Battery's relu and softplus then trained to different
parameters than native: R1 failed at 2,000 steps.

**The fix.** Registered kernels become first-class graph nodes.
- A registered kernel lowers to a single node, `{"op": "named_function",
  "params": {"name": "relu"}}`.
- The interpreter rebuilds that node with Carbon's own implementation of the
  name. That implementation carries Carbon's own JVP rule, and its transpose
  gives the VJP.
- **Recognition is structural.** Lowering (on the miner's side) accepts a
  `custom_jvp_call` as `relu` only if its primal body equals, node for node,
  the body of Carbon's `jax.nn.relu` traced at the same input types.
- **A miner's rule never reaches Carbon.**
  - An unregistered rule is refused (`custom_jvp_call` is `refuse` in v1).
  - A forged rule on a registered body is replaced by Carbon's rule. A test
    lowers a `custom_jvp` with relu's body and a gradient rule that lies, and
    checks that Carbon trains it with relu's true gradient.
- **On Carbon's side**, a `named_function` node passes only if:
  - its name is in the allowlist and in Carbon's kernel table;
  - its arity matches;
  - its results match the declared shapes.

  Otherwise it is refused, with one of `named_function_not_allowlisted`,
  `named_function_refused`, `named_function_arity` or
  `declared_aval_mismatch`.

**The registry, per the pinned JAX 0.10.2.** Every public function in
`jax.nn`, `jax.numpy` and `jax.scipy.special` was traced.
- 32 contain a custom rule. A *kernel* is a function whose trace is exactly
  one `custom_jvp_call` with no constants; there are 19 distinct kernels.
  `jax.nn.softplus` is `logaddexp(x, 0)`, so softplus, mish and log_sigmoid
  lower to `logaddexp`.
- **allow (9):** `relu`, `relu6`, `log1mexp`, `logaddexp`, `logaddexp2`,
  `logit`, `log_ndtr`, `xlogy`, `xlog1py`.
- **review (5):** `i0`, `exp1`, `sici`, `poch`, `zeta`.
- **refuse (5):** `dawsn`, `erfcx`, `fresnel`, `owens_t` (their rules close
  over constants) and `frexp`.
- Functions that only call a kernel (hard_sigmoid, hard_silu, hard_swish,
  mish, log_sigmoid) lower through it. The rest hold several kernels or an
  internal one (sinc, entr, expi, expn, kl_div, rel_entr, wofz) and are
  refused unless their kernels are added.
- PyTorch's `aten.relu` lowers to the named relu: Carbon's rule, which gives
  zero gradient at zero, as torch does.

**Equivalence for every battery family (CPU, R1: bit-identical).**
`phase1_design_results.json` covers the JAX families, MLP and DeepONet, at
every activation on battery's contract surface and every normalization:
5 × 2 × 2 = 20 cases, plus float64 for each family, so 22 in all.

| Check | Result |
|---|---|
| Gradient of battery's training loss, native and B′ | identical in all 22 cases |
| Gradient through every Level 1 loss term, native and B′ | identical in all 22 cases |
| Init rebuilt through B′ | identical in all 22 cases |
| Training through battery's own path (classic for the Level 0 MLP, `training.train` otherwise), parameter digest and predictions | identical in all 22 cases, including relu and softplus, which failed in Phase 0 |
| Phase 0 equivalence re-run under v1 (Level 0 MLPs and DeepONet, every activation, per-case `vmap`) | all identical |

The full record above trains each recipe for its own step count (MLP 2,000,
DeepONet 6,000).

The other battery families:
- **kNN** has no gradient: it is not trained.
- **FNO** is PyTorch-only. Its B′ gradients match torch autograd within
  float32 rounding, as do every PyTorch MLP and DeepONet activation; the
  numbers are in `torch_v1`. That is cross-framework agreement, not R1.

---

## 2. Q3: initialization for PyTorch-lowered graphs (proposed and prototyped)

**Proposal.** A PyTorch graph is initialized by Carbon:
- shapes and dtypes come from the forward graph's declared `params/*` inputs;
- values come from Carbon's key and Carbon's initializer menu;
- the module's own initialization is never used.

The miner declares only, per parameter, a menu name and which axes count as
fan-in and fan-out. The declaration is a small strict-JSON document bound to
the forward graph's digest:

```json
{"schema": "carbon.development.level4-init-spec.v0",
 "graph": "sha256:<forward document>",
 "parameters": [{"input": "params/0", "initializer": "he_normal",
                 "fan_in_axes": [0], "fan_out_axes": [1]}, ...]}
```

- **The menu (`initializers.MENU`):** `he_normal`, `glorot_normal`,
  `lecun_normal`, `zeros`. These are the standard named rules. A Challenge's
  adapter may narrow the menu. Whether to widen it, for example to uniform
  rules or orthogonal init, is a D4/D6 question.
- **Carbon builds the init function in JAX.** It splits its key once per
  parameter, in parameter order.
- **Refusals:**
  - a different graph digest;
  - a missing or extra parameter;
  - a name outside the menu;
  - an axis out of range;
  - a non-float parameter.

**What the prototype shows** (default FNO, PyTorch MLP and DeepONet):
- **The module's initialization cannot reach the graph.** The same recipe
  built under two different torch seeds lowers to byte-identical documents.
  The captured module's weights are pruned (Phase 0 §3).
- **Determinism.** The same key gives the same parameters.
- **Carbon trains it.** Carbon's own `jax.grad` and optimizer bring each
  family's loss down from Carbon's init. The record uses optax Adam,
  learning rate 1e-3, 50 steps. These are a demonstration setting, not a
  chosen value.

**Recommendation for the tech lead.**
- PyTorch graphs carry an init spec.
- JAX graphs may carry either an init graph or an init spec.
- Phase 1 adds the data-flow check that an init graph's key reaches every
  parameter (§8.3 "initializer abuse").

---

## 3. Q2: the GPU R1 leg in the A40 acceptance harness (#739)

Add it once Phase 1 has a graph rebuild in `carbon/` (PR 3 below). This is
what the leg needs:

1. **Code on the pod.** The rebuild must ship in `carbon/` through the pod
   phase's code manifest (`PHASE_MODULE`). Nothing under `scripts/dev/` goes
   to a pod.
2. **Documents prepared before spend.** The operator side lowers each pick to
   its B′ documents on CPU (forward, and init or init spec), and records
   their digests in the run record before any pod starts. Pods receive
   documents as data. Nothing is exported or lowered on a pod, and torch
   never runs there for this leg.
3. **Two comparisons per pick.**
   - Same host: the native rebuild digest equals the B′ rebuild digest, under
     the same pinned GPU environment (`pinned_environment`, the same XLA
     determinism flags).
   - Across hosts: B′ equals B′, gated by the barrier rule, so driver builds
     match.
4. **PyTorch-authored picks.** The default FNO, lowered, trains in Carbon's
   JAX loop. It has no native JAX comparator, so it is compared across hosts
   only.
5. **Review ops on GPU.** The leg should include at least one graph with
   `gather` and one with a named function. A mismatch there is a finding for
   Q7 (Phase 0), not a harness failure.
6. **Budget.** One extra rebuild per pick per host. The smoke must measure
   the leg's own deadline, and the cap arithmetic stays the grant's. No spend
   figure goes in the repository.
7. **Failure typing.** A failed probe or pod is `FAILED_INFRA`. A digest
   mismatch is a recorded R1 finding.

---

## 4. Phase 1 plan

### 4.1 Gates under B′, as Challenge-neutral modules

New package: `carbon/level4/`. Battery's adapter lives in
`carbon/battery/level4.py`. Spike modules are KEEP-then-WRAP: they move into
the package with their tests, and the spike copies are removed in the same
PR.

| Gate | Under B′ | Module | Values |
|---|---|---|---|
| G0 Intake | Document set (forward, optional loss, init graph or init spec), framework label, declared interface equal to the Challenge's (adapter: names, dtypes, per-case shapes, units), size bound | `intake.py` | Size bound `HUMAN_INPUT` |
| G1 Static scan | Not on a Carbon host: there is no source to scan. Optional source is kept for audit and never executed | (none) | |
| G2 Trace | Miner side: Launchpad tooling (`tooling/lower_jax.py`, `tooling/lower_torch.py`, `named.py` recognition, `prune`) | `tooling/` | |
| G3 Parse | Carbon's strict JSON plus structure, in a separate process with resource limits | `parse.py` | Limits `HUMAN_INPUT` |
| G4 Validate | Allowlist v1: ops, roles, parameter kinds, named functions. RNG in init only; init key data-flow; declared outputs equal the interface. Caps on constant bytes (after pruning), nodes, call depth, document bytes, largest intermediate | `allowlist.py` (data `allowlist_v1.json`), `validate.py` | Caps `HUMAN_INPUT` per Challenge sheet (D6) |
| G5 Compile | XLA compiles Carbon's training step and inference graph in the C-03 lane, under a deadline | `compile.py` | Deadline `HUMAN_INPUT`; security owner (D3) |
| G6 Train | Carbon's loop: Carbon's key initializes (graph or spec); TRAIN only; the loss is the Challenge's or an admitted loss graph; registered optimizer menu; steps within budget (TRAINING-BUDGET-01 F4) | `interpret.py`, `initializers.py`, `train.py` | Budget from the sheet |
| G7 Grade | The Challenge's exam code, unchanged, on the trained graph; outputs finite and in range; inference cost recorded | `grade.py` (adapter hook) | Inference-cost rule `HUMAN_INPUT` |

Each refusal is a typed construction refusal: never a physics failure, and
never `FAILED_INFRA` unless Carbon's own infrastructure failed.

### 4.2 The equivalence suite (the key correctness check)

| Leg | What | Rule |
|---|---|---|
| E1 | Battery's Level 0 recipes (scaffold MLP, panel MLP, panel DeepONet) through G0–G6 against the declarative path | Parameter and prediction digests identical (R1) |
| E2 | Every activation × normalization × precision on battery's surface (the 22 cases of §1) | Gradients and training identical |
| E3 | Inference padded into blocks of the declared batch, against the declared graph on each block (replaces per-case `vmap`, which does not train bit-identically for DeepONet) | Identical |
| E4 | PyTorch families lowered to B′ against torch | Float32 agreement, recorded, never R1 |
| E5 | GPU leg (§3) | Identical on one host and across hosts |
| E6 | A second Challenge (cold plate or motor) through the same shared code | E1–E3 hold with only an adapter |

### 4.3 Known-bad specimens, one per row

The proposal's §8.1 rows:

| Row | Specimen | Gate | Spike status |
|---|---|---|---|
| Network access, undeclared dependencies | A document holding `io_callback` (the miner's network call can only surface as one) | G4 `op_refused` | have |
| Model loaders, hidden assets | Weights loaded at trace time, then a large constant | G4 constant cap (fixture cap, labelled non-production) | measured only; needs a cap fixture |
| Embedded weights or tables | A table split into many scalars | G4 total-bytes cap | measured; needs a cap fixture |
| Child processes, resource escapes | `ffi_call` / `custom_call` node | G4 `op_refused` | have (`custom_call` listed) |
| Caches, checkpoints, residue | An init graph that ignores the key | G4 key data-flow | **new** |
| Run identification, timing | `io_callback` returning time; RNG in the forward graph | G4 | have |
| Construction-to-evaluator access | A callback that writes to a path | G4 | have |
| Hidden preprocessing, hybrids | `pure_callback` wrapping a solver | G4 | have |
| Malformed outputs, nonfinite values, parser abuse | A graph emitting NaN on selected cases; oversized or deep documents | G7; G3/G4 | parser side have; **G7 new** |

The proposal's §8.3 rows:

| Row | Specimen | Gate | Spike status |
|---|---|---|---|
| Callback smuggling | Inside `jit`, inside `custom_jvp`, inside `custom_vjp` | G4 recursive | have |
| Constant splitting | 512 scalars | G4 total bytes | measured; needs a cap fixture |
| Procedural tables | `iota` arithmetic regenerating a table | Recorded, not blockable (D4, Track B) | **new** (recorded only) |
| Unbounded loop | Data-dependent `while` | G4 | have |
| Compute under-counting | Denormal-heavy or gather-heavy graph | R6/R7 (Phase 4) | **new**, Phase 4 |
| Compile bomb | Deep call nesting; huge static unroll | G4 caps; G5 deadline | **new** (caps fixture) |
| Compiler exploit | Not constructible safely | G5 isolation; security owner | recorded only |
| Trace-time divergence | Not applicable on Carbon hosts under B′ | (none) | recorded |
| Nondeterminism | `scatter_add`/`gather` gradient on GPU | E5 | **new** with E5 |
| RNG leakage | RNG in forward or loss | G4 roles | have |
| Interface abuse | Outputs that pass shape checks but carry extra precision | G7 interface rounding | **new** |
| Initializer abuse | An init graph that builds fixed weights | G4 key data-flow / init spec | **new** |

Phase 0 and this PR added three more: a forged custom rule (now Carbon's
rule), a declared-shape lie, and named-function tampering. All three are
covered.

### 4.4 Estimated PRs

| # | PR | Contents | Needs |
|---|---|---|---|
| 1 | **This PR** | D1 record, roadmap rev 2.3, Q1 named functions, Q3 init spec, this plan | D1 (done) |
| 2 | `carbon/level4` core | Format, G3 parser (in process), allowlist v1 data, G4 validator, named functions, interpreter; spike tests ported | |
| 3 | Init and G6 | Init graphs with the key data-flow check, init specs; the Challenge-neutral training loop over graphs; battery adapter; E1–E3 | |
| 4 | G0 and the out-of-process G3 | Interface from adapters; document-set intake; parse in a separate process with limits (`HUMAN_INPUT`) | |
| 5 | G7 | Grading hook (exam code unchanged), output checks, inference-cost record | Inference-cost rule (D6) |
| 6 | Specimen suite | Every row of §4.3, with cap fixtures clearly non-production | |
| 7 | G5 | Compile in the C-03 lane under deadline | D3 (security owner) to accept |
| 8 | Development-only Level 4 variant | Battery's development Level 4 variant (held outside `CONTRACTS`); attack seam `level_4_constrained_inference_export` runnable | OWNER-GRAPHITE-TEST-WAVE-03 rules |
| 9 | A40 GPU leg (E5) | §3, on #739's harness | PR 3; an A40 grant run |
| 10 | Second Challenge (E6) | Cold plate or motor adapter only | PRs 2–3 |

PRs 2–6 need no security acceptance and no pods. PR 7 can land with its
profile marked pending acceptance. Phase 3 (Graphite on the development
variant) starts after PR 8.

### 4.5 G6 loss slot v1 (working contract)

**Authority.** The Test Lead's ruling of 2026-10-08 (L4 G6 loss slot v1).
It is a working contract: it may change prospectively. The code is
`carbon/level4/loss.py`, with the gate in G0 (`intake.intake`) and G4
(`validate.validate_submission`). The fixtures are in
`tests/cpu/test_level4_loss_slot.py`.

| Item | Contract |
|---|---|
| **Level 1 gate** | Each Challenge declares `loss_override: none \| terms \| graph`. A loss document under `none` or `terms` (Level 1's loss terms) is refused at G0 (`loss_not_permitted`), never silently ignored. An unknown or unset declaration permits nothing. |
| **Inputs** | By name, in this order: `loss/pred/<k>` (the Challenge's declared outputs), `loss/target/<k>` (TRAIN targets, same layout), `loss/x/<name>` (the TRAIN inputs), optional `loss/aux/<k>`. Nothing else: no parameter input (regularisation is the optimizer menu's), no key (no RNG; the allowlist admits RNG only in init). |
| **`aux`** | Up to N auxiliary outputs the forward graph declares after the interface's outputs, for latent penalties. N is `HUMAN_INPUT` (`loss.AUX_LIMIT`); unset, no auxiliary output is admitted (`loss_aux_not_admitted`). |
| **Output** | The case's loss: one float, shape `[1]`. Carbon maps the graph over the batch, which gives the per-case loss vector `[B]`. |
| **Reduction** | Carbon's: the mean over the batch. No cross-case or batch-composition term. |
| **Exam** | When the loss graph fully replaces the Challenge's loss, G7's exam is unchanged. |
| **Budget** | The loss graph's FLOPs count toward F4 (TRAINING-BUDGET-01). |
| **Failure** | A non-finite loss is the candidate's own training failure, never `FAILED_INFRA`. |
| **Rest** | Allowlist v1 and Carbon's autodiff, as now. |

**Per case, mapped by Carbon (contract).** The Level 4 engineer proposed it
and the Test Lead accepted it, 2026-10-08, as structurally stronger than a
`[B]`-vector rule. The ruling's "per-case loss vector, Carbon's mean, no
cross-case tricks" is enforced by structure:
- The loss graph is **declared per case**: every input has leading dimension
  1, and its one output has shape `[1]`.
- Carbon maps the graph over the batch with `jax.vmap`, which gives the
  per-case vector `[B]`, then takes the mean (`loss.per_case_mean`).
- So the graph never sees a second case. Declaring it at batch B instead
  would need an independence proof that shapes alone cannot give.

**Not yet built.** The ruling's content is complete, but these pieces wait:
- **Battery's `loss_override`.** It is a Challenge declaration, so it waits
  for the Test Lead, and changing it changes the registered variant document,
  which means a new version.
- **G6 training on a submitted loss.** The battery adapter's
  `train_graph` with `per_case_mean`, and the F4 count, are the next slice.
- **Admitting `aux` outputs.** That needs N set, and the forward interface
  check then widened to admit them.

---

## 5. Open items carried forward

| # | Item | Owner |
|---|---|---|
| D2 | v1 on B′ (recommended) | Owner / tech lead |
| D3 | G5 compile isolation and Carbon's parser under B′ | Security owner |
| D4 | Pretrained assets, priors and hybrids; whether the init menu widens | Owner |
| D5 | Solver as an operation | Owner / tech lead |
| D6 | Per-Challenge caps (constant bytes, nodes, depth, document bytes, largest intermediate, parser and compile limits, inference cost) | Owner (sheet) |
| Q7 | Review ops (`gather`, `sort`, `cumsum`, `view_as_complex`) and review named functions | Tech lead, after E5 |
| Q9 | Internal JAX handles (`random_wrap`/`unwrap`, threefry impl); pin test on upgrade | Engineering |

## 6. Non-claims

- Development tooling only. Nothing here earns SPECIFIED, IMPLEMENTED or
  TESTED for Level 4 on any Challenge, or anything for miners.
- Every equivalence result is CPU-only until E5 runs.
- No cap, limit, threshold, menu or budget is chosen. The demonstration's
  optimizer settings are not values.
- Not a security audit.
