# Level 4 Phase 0 spike: graph-only construction and B′

**For:** the Test Lead
**From:** the Level 4 engineer, 2026-10-07
**Status:** development spike. CPU only. No pods, no hidden data, no miner
code, no chain, nothing in `CONTRACTS`, no miner-facing change. No cap or
limit is chosen: every value the proposal reserves stays `HUMAN_INPUT`.
**Answers:** `docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md`
§10 Phase 0 and Appendix B.

| File | What it is |
|---|---|
| `allowlist_v0.json` | Allowlist v0, versioned and digest-bound (`level4-allowlist-v0`) |
| `phase0_results.json` | The recorded run: inventories, measurements, serialization probes, equivalence, specimens |
| `scripts/dev/level4_spike/` | Challenge-neutral spike code, plus `adapters/battery.py` |
| `tests/cpu/test_level4_spike.py` | 11 tests (about 30 s on CPU) |

Reproduce (about 4 minutes on CPU):

```bash
python scripts/dev/level4_spike/run.py docs/development/graphite/level4/phase0_results.json --adapter battery
```

The recorded run used WSL Ubuntu x86_64 with the lock-pinned jax/jaxlib
0.10.2, torch 2.13.0+cpu and neuraloperator 2.0.0, on public TRAIN v1. It is
a native diagnostic run. CI runs the tests in the pinned container.

---

## 0. Answer

**Build Level 4 v1 on B′.** Option B as written fails, and option A works but
needs a sandbox that B′ makes unnecessary.

- **Equivalence holds under R1.** Battery's Level 0 MLP and DeepONet, rebuilt
  through B′, train to the same parameter digest and the same predictions as
  the declarative path, bit for bit, at their full step counts. Initialization
  is rebuilt too.
- **Carbon's own `jax.grad` trains the rebuilt graph.** Gradients are never
  miner-supplied.
- **PyTorch shares the path.** Battery's FNO, MLP and DeepONet lower from
  `torch.export` Core ATen into the same format and the same interpreter.
- **Option B fails.** Carbon cannot differentiate imported StableHLO with the
  pinned JAX, and the pinned environment cannot read `jax.export` artifacts at
  all. `torch.export` archives contain a pickle.
- **Three things block "TESTED"**: custom derivative rules (§8, Q1), a GPU R1
  check (Q2), and how PyTorch graphs get initialized (Q3).

---

## 1. Deliverable 1: traces

Every battery graph was traced on the pinned frameworks. Full per-graph
counts are in `phase0_results.json` (`jax.graphs`, `torch.programs`).

**JAX, forward graphs at the TRAIN batch (400 cases):**

| Graph | Primitives (count) |
|---|---|
| MLP, Level 0 (GELU) | `add` 10, `broadcast_in_dim` 4, `dot_general` 4, `integer_pow` 3, `mul` 12, `tanh` 3 |
| DeepONet, Level 0 | `add` 31, `broadcast_in_dim` 13, `concatenate` 2, `dot_general` 14, `integer_pow` 9, `mul` 36, `slice` 5, `tanh` 9, `transpose` 2 |
| MLP + other surface activations with `layer_norm` | adds `reduce_sum`, `div`, `sqrt`, `square`, `gt`, `select_n`, `convert_element_type`, nested `jit`; `logistic` (silu); `exp`, `log1p`, `abs`, `ne`, `neg`, `max` (softplus); **`custom_jvp_call`** (relu, softplus) |
| kNN (TRAIN as named inputs, x64) | `sort` 1, `gather` 2, `dot_general` 1, `sqrt` 1, `reduce_sum` 2, `iota`, `lt`, `select_n`, `jit` 3, plus arithmetic |

**JAX, init and loss graphs:**

| Graph | Primitives |
|---|---|
| Init (every family) | `random_wrap`, `random_split`, `random_unwrap`, `random_bits`, `shift_right_logical`, `or`, `bitcast_convert_type`, `erf_inv`, `slice`, `squeeze`, nested `jit` (call depth 4) |
| Battery Level 1 loss terms (all terms) | `fft` 2, `iota` 10, `reduce_sum` 41, `abs`, `concatenate`, `reshape`, `convert_element_type`, `integer_pow`, arithmetic, nested `jit` |

The union over forward, init and loss graphs is **41 JAX primitives**
(`jax.primitive_union`, with the roles each appears in).

**PyTorch, Core ATen after `run_decompositions()`:**

| Program | Core ATen ops (distinct) | Notes |
|---|---|---|
| MLP (GELU) | `mm` 4, `add` 4, `gelu` 3 (3) | |
| DeepONet | 38 ops (7) | `mm`, `permute`, `slice`, `cat`, `gelu`, 2 `_assert_tensor_metadata` |
| FNO, default (width 256, 3 layers, 16 modes) | 167 ops (27) | `convolution` 13, `_fft_r2c` 3, `_fft_c2r` 3, `bmm` 3 (complex), `view_as_complex` 3, `slice_scatter` 3, `full` 3, `arange`/`lt`/`where` (grid embedding), 34 `_assert_tensor_metadata` |
| FNO, largest (width 512, 6 layers, 61 modes) | 289 ops (27) | Same op set |
| MLP + other activations with `layer_norm` | 29 to 38 ops | adds `mean.dim`, `var.correction`, `sqrt`, `div`, `sub`; `relu`, `tanh`, `sigmoid`; `exp`, `log1p`, `gt`, `where` (softplus) |

The union is **37 Core ATen ops**. No custom op, no RNG and nothing outside
the core set appeared.

---

## 2. Deliverable 2: allowlist v0

`allowlist_v0.json`, version `level4-allowlist-v0`, digest
`sha256:dc88c4b0d8d758eb1ae01d4ec567f81e64d71bc8a653a9eff5281f839ae8c488`.
Any op not listed is refused.

The Carbon graph's vocabulary is JAX's primitive names. Each entry gives:
- a category from proposal §6.1;
- a default of allow, review or refuse;
- the roles it may appear in: forward, init or loss;
- every parameter, with a kind. An unknown kind, a missing or extra
  parameter, or a non-default sharding, precision, accuracy, donation or
  compiler-option value refuses.

| Default | Count | Members |
|---|---|---|
| allow | 71 | Elementwise math, linear algebra, shape, reductions, `fft`, `jit`/`closed_call` (validated recursively). Keyed RNG (`random_wrap`, `random_split`, `random_unwrap`, `random_bits`) and the threefry bit ops are allowed in the **init role only**. `cond` and static `scan` are allowed by category but not yet in the v0 interpreter |
| review | 9 | `custom_jvp_call` (§8, Q1), `gather` and `sort` (kNN; GPU determinism of the gather's scatter-add gradient), `cumsum`, `scatter_add`, `top_k`, `custom_vjp_call`, `stop_gradient`, `remat2` |
| refuse | 21 | `pure_callback`, `io_callback`, `debug_callback`, `debug_print`, `ffi_call`, `custom_call`; `while`; `rng_uniform`, `rng_bit_generator`, `random_seed` (not keyed by Carbon); `infeed`, `outfeed`, `device_put`, `sharding_constraint`, collectives, tokens |

The `aten_core` section classifies 55 Core ATen ops: 44 allow, 2 review
(`view_as_complex` for complex64 weights, and `_assert_tensor_metadata`,
which lowering drops), and 9 refuse (RNG in inference, host
synchronization, data-dependent shapes).

---

## 3. Deliverable 3: measurements for D6

These are measurements only. No cap is chosen (`allowlist.CAPS`, every value
`HUMAN_INPUT`). Batch is TRAIN v1's 400 cases. "Largest" means every
architecture surface at its maximum in battery's registered contract
document (width 512, depth 6, DeepONet depth 6, 64 basis functions, 61 FNO
modes), with rich inputs and full trajectory outputs.

| Graph | Nodes | Call depth | Constant bytes (count) | Document bytes | Largest intermediate | XLA compile | XLA temp | FLOPs |
|---|---|---|---|---|---|---|---|---|
| MLP Level 0, forward | 36 | 1 | 48 (12) | 5,969 | 392 KB | | | |
| MLP largest, forward | 69 | 1 | 96 (24) | 11,215 | 819 KB | 0.04 s | 1.6 MB | 1.16 G |
| MLP largest, Carbon train step | 778 | 4 | | | | 0.25 s | 13.3 MB | 3.51 G |
| DeepONet Level 0, forward | 121 | 1 | 1,104 (38) | 20,608 | 410 KB | | | |
| DeepONet largest, forward | 220 | 1 | 1,252 (74) | 36,115 | 819 KB | 0.07 s | 2.4 MB | 1.80 G |
| DeepONet largest, Carbon train step | 1,243 | 4 | | | | 0.34 s | 20.6 MB | 5.42 G |
| Init, largest DeepONet | 365 | 4 | 236 (59) | 38,337 | 1.0 MB | | | |
| Battery loss terms | 348 | 2 | 284 (71) | 44,065 | 394 KB | | | |
| kNN, forward | 30 | 2 | 40 (6) | 6,066 | 5.1 MB | | | |
| FNO default, forward (from PyTorch) | 253 | 1 | 228 | 45,077 | 99 MB | | | |
| FNO largest, forward (from PyTorch) | 444 | 1 | 420 | 79,162 | 198 MB | 0.15 s | 903 MB | 460 G |

What the measurements show:

- **Legitimate constants are tiny.** No legitimate graph embeds more than
  1.3 KB. DeepONet's two time grids are the largest constants. They are
  published Challenge data and could become named Carbon inputs (§6.2).
- **The constant count must be taken after pruning.** `torch.export` lifts
  the captured neuraloperator module's own weights: 16.8 MB at default size,
  **406.9 MB** at the largest. They feed only the metadata assertions that
  lowering drops. The lowering tool prunes them on the miner's side, and the
  validator counts every byte a document still declares. An unpruned FNO
  would look like a smuggled table.
- **Compile time is not where the risk is today.** Every legitimate graph
  compiles in under 0.4 s on CPU. Compile bombs remain a G5 question for
  crafted graphs, not for these.
- **Size and depth are small.** The largest stored forward graph has 444
  nodes. Carbon's own largest train step has 1,243 primitives. The deepest
  call nesting is 4, from `jax.random`'s nested jits.
- **B′ costs nothing at runtime.** Rebuilt graphs compile to the same FLOPs
  and the same XLA temp bytes as native.
- The largest FNO's 903 MB of XLA temp and 407 MB of parameters set the
  memory scale for Level 4 FNO-like graphs.

---

## 4. Deliverable 4: serialization safety

| Artifact | What happens | Verdict |
|---|---|---|
| `jax.export` (StableHLO) | `Exported.serialize()` needs `flatbuffers`, which is **not in `uv.lock`**: the pinned environment can neither write nor read these artifacts. The text form parses with jaxlib's MLIR C++ parser, a native parser of untrusted input. In the pinned JAX source, a deserialized `Exported` has a VJP only if the blob carries a serialized one (`jax/_src/export/serialization.py`, `_get_vjp`) | **Carbon cannot differentiate an imported StableHLO forward graph.** The gradient would be miner-supplied, which is the fairness problem option B was meant to avoid |
| `jax.export` callbacks | Export refuses `pure_callback` (`NotImplementedError`) | This is the exporter's check on an honest machine, not a property of bytes Carbon receives |
| `torch.export.save` (`.pt2` zip) | `models/model.json` and the configs pass Carbon's `strict_json`. Weights and constants are raw bytes. **`data/sample_inputs/model.pt` holds `data.pkl`, a pickle**, and `torch.export.load` runs `torch.load(weights_only=True)` on it | A restricted unpickler on untrusted bytes. **Never load a `.pt2` on a Carbon host** |
| B′ document | Carbon's own strict JSON, parsed with the existing `strict_json` rules. Constants are base64 with a declared byte count, checked before decoding. Every node's shape and dtype are declared and checked when the graph runs | No third-party deserializer runs on a Carbon host |

---

## 5. Deliverable 5: the B′ probe

### 5.1 Format v0

The format is defined in `scripts/dev/level4_spike/graph.py` (since moved
to `carbon/level4/graph.py`), schema `carbon.development.level4-graph.v0`.

- A document has a role (forward, init or loss), an entry graph, and named
  graphs.
- Each graph has inputs (named, with dtype and shape), constants, nodes and
  outputs.
- Each node is `{"op", "in", "out", "params"}`. Its inputs are value ids
  defined earlier, and its outputs declare dtype and shape.
- A nested call is a parameter `{"graph": "<name>"}`. Call depth is
  measured, and cycles are refused.
- Parameters are the miner's flat, named list (`params/0` …). Carbon feeds
  them from its own initialization.

```json
{"op": "dot_general", "in": [6, 0],
 "out": [{"value": 8, "dtype": "float32", "shape": [400, 64]}],
 "params": {"dimension_numbers": [[[1], [0]], [[], []]], "out_sharding": null,
            "precision": null, "preferred_element_type": "float32"}}
```

### 5.2 Lowering, interpreter and gates

- **From JAX:** `lower_jax.lower` walks the jaxpr and every nested jaxpr.
  Literals become counted constants. Symbolic shapes are refused.
- **From PyTorch:** `lower_torch.lower` emits Carbon ops for each Core ATen
  op the allowlist admits.
  - Torch FFT normalization is mapped explicitly onto XLA's convention.
  - int64 index arithmetic narrows to int32; a constant outside int32 is
    refused.
  - Metadata assertions are dropped.
  - Dead values are pruned.
- **Rebuilt in JAX:** `interpret.rebuild` runs G4 first, then binds each node
  to a primitive Carbon chose, with parameters decoded through the
  allowlist's kinds. It checks every result against its declared shape and
  dtype, and evaluates nested calls inline. Carbon then differentiates the
  rebuilt function with its own `jax.grad`.

### 5.3 Equivalence (R1: bit-identical, CPU)

The classic MLP check runs in three steps:
1. battery's declarative `MLP.fit`;
2. a pinned copy of its written-out Adam loop, run with the native net, which
   must reproduce step 1's digest;
3. the same loop, run with the net and initializer rebuilt through B′.

The general path puts the rebuilt `init` and `apply` inside battery's own
`recipes.MLP._fit_general` and `training.train`, unchanged.

| Recipe | Path | Steps | Declarative = copy | B′ = native | Loss, start → end (B′) |
|---|---|---|---|---|---|
| Scaffold MLP (Level 0) | classic | 2,000 | yes | **yes** (parameters and outputs) | 4.670 → 0.0708 |
| Panel MLP (Level 0) | classic | 6,000 | yes | **yes** | 4.623 → 0.00273 |
| Panel DeepONet (Level 0) | general | 6,000 | (it is the declarative path) | **yes** (parameters and predictions) | 6.834 → 0.0167 |
| Scaffold MLP, tanh | general | 2,000 | | yes | 6.457 → 0.1003 |
| Scaffold MLP, silu | general | 2,000 | | yes | 4.367 → 0.0841 |
| Scaffold MLP, relu | general | 2,000 | | **no** | 5.696 → 0.07168 (native 0.07168) |
| Scaffold MLP, softplus | general | 2,000 | | **no** | 13.56 → 0.1837 (native 0.1837) |

Further results:
- **Batch dimension.** A graph lowered for one case and batched by Carbon's
  `vmap` gave outputs bit-identical to the native batched forward, for both
  MLP and DeepONet.
- **kNN.** The B′ graph matches battery's numpy kNN to 3.6e-15, but not bit
  for bit (numpy against XLA in float64). TRAIN enters as 797 KB of named
  inputs. Embedded instead, it would be a 797 KB constant.
- **PyTorch through B′.** Against torch on TRAIN, every program agrees to
  within 7.2e-6 absolute on outputs of magnitude 1.8 to 8.5. JAX gradients
  over the rebuilt graph match torch autograd to within 1.8e-6 relative. This
  is float32 agreement across frameworks, not R1.
- **Specimens.** 13 programs and 15 tampered documents are each refused at
  their expected gate:
  - callbacks: direct, nested in `jit`, and inside `custom_jvp`;
  - an unbounded `while`;
  - RNG seeded in the graph, and keyed RNG in the forward or loss role;
  - `custom_vjp`, `stop_gradient` and static `scan` (not in v0);
  - duplicate keys, NaN, nesting bombs;
  - unknown or swapped ops, extra or non-default parameters, compiler options
    smuggled into a call;
  - a constant byte-count lie, a declared-shape lie, a call cycle, a key
    dtype outside init, and an allowlist version mismatch.
- **Constants.** A 16 KB table and the same idea split into 512 scalars are
  both counted (16,384 B as 1 constant; 2,048 B as 512 constants). Their cap
  verdict is `blocked_human_input`.

---

## 6. Recommendation: A, B or B′

| | A: Carbon traces miner Python | B: miner submits StableHLO | **B′: miner submits a Carbon graph** |
|---|---|---|---|
| Miner Python on a Carbon host | Yes, in a tracing sandbox | No | **No** |
| Who differentiates | Carbon | **The miner** (serialized VJP), since Carbon cannot differentiate imported StableHLO | **Carbon** (`jax.grad` over the rebuilt graph) |
| Parser on a Carbon host | Carbon's | MLIR bytecode parser, needing a new dependency (`flatbuffers`) | **Carbon's strict JSON** |
| PyTorch | `torch.export` in the sandbox, then a lowering | No verified path | **Same lowering, run by the miner; one validator** |
| Equivalence with Level 0 (R1, CPU) | Same graphs as B′ | Not testable in the pinned environment | **Holds**, except custom derivative rules (Q1) |
| Security-owner acceptance needed (D3) | Tracing sandbox and G5 compile isolation | G5 | **G5 only** |

**Recommendation for D2: B′ for Level 4 v1, in JAX and PyTorch.** Keep A as
a fallback only, for a framework feature B′ cannot carry. Drop B: it cannot
keep autodiff with Carbon.

What B′ still needs from the security owner is narrower than D3:
- XLA compiling a validated, Carbon-built graph (G5);
- Carbon's own JSON parser and interpreter facing hostile documents.

No miner code runs anywhere on Carbon hosts.

---

## 7. What Phase 1 inherits

These parts of the spike are directly reusable:
- the format v0;
- `graph.prune`;
- the parameter-kind codecs;
- the declared-shape check;
- the specimens;
- the equivalence harness, which already is the Phase 1 equivalence test in
  miniature.

The spike code is development tooling under `scripts/dev/`. Phase 1 should
move what it keeps into `carbon/`, with battery as the first adapter.

---

## 8. Open questions

| # | Question | Evidence | Suggested answer |
|---|---|---|---|
| Q1 | **Custom derivative rules.** `custom_jvp_call` carries a Python callable, which a graph cannot hold. B′ keeps the primal and Carbon differentiates it. Battery's relu and softplus then train differently from native (R1 fails at 2,000 steps; final loss agrees to about 1e-5) | §5.3 | Carbon registers a small set of known functions, recognized by a digest of the primal body (relu, softplus/logaddexp, ...), and rebuilds them with its own rule. Refuse any other `custom_jvp_call` in v1. Owner and tech lead decide |
| Q2 | **GPU R1.** All equivalence here is CPU. The per-case `vmap` and the review ops (`gather`, `sort`, `reduce_sum`) need the R1 check on the GPU lane | §5.3 | Run the equivalence harness on the GPU host in Phase 1, before Phase 4 |
| Q3 | **PyTorch initialization.** A `torch.export` program has no init graph, and Carbon must initialize from its own key | §5.2 | The miner declares a shape and a registered initializer per parameter (the menu battery already has), or submits a JAX init graph. Tech lead decides |
| Q4 | **PyTorch training in JAX.** Under B′ a PyTorch-authored model trains in Carbon's JAX loop. It agrees with torch to float32 rounding, never bit for bit | §5.3 | Accept: one trainer, one validator. Consistent with backend parity, if the owner agrees |
| Q5 | **Batch dimension in the interface (§5).** Fixed-batch graphs cannot serve both TRAIN and exam batches | per-case `vmap` is bit-identical on CPU | Interface graphs are per-case; Carbon batches with `vmap`. Confirm on GPU (Q2) |
| Q6 | **Named Challenge inputs.** DeepONet's time grids and kNN's TRAIN are data, not miner constants | §3, §5.3 | Each adapter declares named Carbon inputs (grids, published tables, TRAIN for retrieval families). They never count against the constant cap |
| Q7 | **Review ops.** `gather`, `sort`, `view_as_complex` (complex64), `cumsum` | §2 | Decide per op before v1. `gather` depends on Q2 |
| Q8 | **D6 values.** Constant bytes, node count, call depth, document bytes, largest intermediate | §3 | Owner sets them per Challenge sheet from §3. They are counted after pruning |
| Q9 | **Internal JAX handles.** The interpreter reaches `random_wrap` and `random_unwrap` through `jax._src.random.prng`; no public handle exists in 0.10.2 | `interpret.py` | Accept for v1, with a pin test. Revisit on a JAX upgrade |
| Q10 | **Procedural tables.** A few constants plus `iota` arithmetic can regenerate a table at runtime | specimens | Unblockable by graph checks, as the proposal says. Owned by D4 and Track B |

---

## 9. Non-claims

- This is a spike. It earns IMPLEMENTED and TESTED only for the development
  tooling under `scripts/dev/level4_spike/`. It earns nothing for Level 4,
  for any Challenge, or for miners.
- Nothing here is a security audit. Refusal specimens show attempted
  coverage, never a bound (Admission §3).
- No cap, limit, threshold or budget is chosen. The equivalence results are
  CPU-only.
- Cross-framework agreement numbers are measurements, not tolerances.
