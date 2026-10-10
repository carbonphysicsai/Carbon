# Level 4 construction: accept code, run only math

**For:** the Test Lead
**From:** Fitz (owner direction), drafted with Claude, 2026-10-07
**Status:** proposal. Nothing here is accepted, implemented or open to
miners. It asks for the decisions in §11 and proposes the test plan in §10.
**Update 2026-10-07:** the owner approved D1 (OWNER-LEVEL4-GRAPH-ONLY-01,
roadmap rev 2.3). D2–D6 remain open. The Phase 0 report and the Phase 1 plan
are in `docs/development/graphite/level4/`.
**Read with:** `Design_Specs/Challenge_Admission.md` §3 (the ladder and Track
A), `Design_Specs/Challenge_Roadmap.md` (climb procedure, Track A admission),
`docs/development/graphite/ISOLATION_READINESS_L4_L5.md`, and PR #727 (the
compute budget and training budget study).

---

## 0. Summary

**The goal.** Carbon needs Level 4 to reach the innovation level showing up
in current published work. Two recent examples:
- NVIDIA's **CANTO**, a transformer operator that works directly on CAD
  surfaces and uses gradients to improve the design;
- **NOIR**, an operator that unmixes corrupted sensor inputs using an
  independence penalty.

Both need new architectures, and new architectures are Level 4 on our
ladder: "New architectures exporting through a constrained inference
interface".

**The problem.** Today, Level 4 is read as "accept miner executables", and
that path is far away. The isolation assessment (2026-10-04) found:
- no path runs participant code;
- no Level 4 inference interface exists;
- about ten steps stand between today and running hostile code, several of
  them security-owner decisions.

**The proposal.** Redefine how Level 4 is admitted: **miners write code;
Carbon runs only math.**
1. A miner writes a model, and optionally a loss, in JAX, or a model in
   PyTorch.
2. Carbon converts it into a pure computation graph: a JAX `jaxpr` /
   StableHLO, or a PyTorch `torch.export` program.
3. Carbon checks every operation against an allowlist, caps embedded
   constants and counts compute.
4. Carbon trains and grades **only the graph**, in its own training loop,
   from its own seed and data. The miner's Python never runs on a validator
   and never reaches the grader.

**Why it works.** A pure math graph has no files, network, processes, clock,
loaders or callbacks. That removes most of the attack families in Admission
§3 by construction rather than by sandboxing. What remains is score gaming
and encoded prior knowledge, which the exam design and Track B already own.

**What changes:** one roadmap rule (§7), two registry exclusions on a
development-only variant, and battery's empty Level 4 proposal.

**What it needs:**
- a graph validator;
- a Carbon-owned training loop over graphs;
- a small tracing sandbox (option A, §3.2), or none at all (option B);
- an attack suite for graph-specific attacks (§8);
- six decisions (§11).

**Level 5** (custom inference that isn't pure math) stays behind the full
security-owner sequence (§12) and may never be needed.

---

## 1. Why Level 4, and why not just more knobs

Levels 0–3 widen what a miner can *configure*:
- **0:** recipe and registered operations;
- **1:** bounded loss expressions;
- **2:** schedules, optimisers and sampling;
- **3:** training-time numerical routines.

They never let a miner invent a model structure Carbon didn't anticipate.
Published progress is mostly structural: a new layer, a new encoder for a
new input type, a new coupling between physics and learning. For example:

| Idea | Rung it needs | Why |
|---|---|---|
| NOIR's independence penalty | 1 (a loss) | Only useful on top of a new unmixing layer |
| NOIR's unmixing layer | 4 | A new layer inside the operator |
| CANTO's transformer over CAD patches | 4 | A new architecture and a new input encoder |
| CANTO's design improvement by gradients | 4, plus Carbon tooling | Needs a differentiable rebuilt model and a design optimizer (scoped, not built: Admission §6) |

Without Level 4, Carbon can only rank variations of the families it already
ships (k-nearest-neighbour, MLP, DeepONet, FNO for battery).

---

## 2. Where we are today

All references are to `origin/main` at `20fb0ad31`.

| Item | State | Where |
|---|---|---|
| Ladder Levels 0–5 | Defined; a level not listed is NOT_RUN | `carbon/challenge_pipeline/ladder.py`, Admission §3 |
| Battery's current level | 0; Level 1 is Phase 1's first climb | `Design_Specs/Challenge_Roadmap.md` |
| Battery Level 4 proposal | Exists and is **empty** | `carbon/challenge_pipeline/proposals/battery-fastcharge-ageing-development-v1/level-4.json`; OWNER-GRAPHITE-TEST-WAVE-03 |
| Battery Level 4 study map | Places `hybrid` and `prediction` at Level 4 as "new model forms behind the constrained inference interface"; nothing rebuildable | GRAPHITE-ADMISSION-01, GA-D1 |
| Level 4–5 attack seams | `level_4_constrained_inference_export` and `level_5_custom_inference` are declared `NOT_RUN`, needing participant code and the security owner's isolation decision | `carbon/agent_campaign/attack/adapters/battery.py` |
| Roadmap rule | "Below Level 4 a submission is a declarative recipe"; Track A admission refuses "executable content at a level that admits none (submissions are declarative below Level 4…)" | `Design_Specs/Challenge_Roadmap.md` |
| Registry exclusions | `loss_expressions` and `composition_graphs` are excluded under trigger `EXECUTABLE_SUBMISSION` | `carbon/reconstruction/capability_registry.py` |
| Level 3 rule | Declarative menu only; no participant code until the security owner accepts isolation | OWNER-GRAPHITE-TEST-WAVE-03 |
| Development-only variants | Allowed for Graphite's Constructor and Attacker, held outside `CONTRACTS`, pinned by digest; miner surfaces must refuse them | OWNER-GRAPHITE-TEST-WAVE-03 §1 |
| Isolated rebuild worker (C-03) | IMPLEMENTED and TESTED for public development work; **not** SECURITY_QUALIFIED; MQ-015 open; gVisor and microVMs rejected for the C-03 slice | `ISOLATION_READINESS_L4_L5.md` §2; `.agent/DECISIONS.md` |
| Pod security items | #3: participant code could forge pod status and timing. #4: `RUNPOD_API_KEY` readable via `/proc`. Both open, both "blockers before any Level 4–5 pod work" | `.agent/tickets/VALIDATOR-01_challenge_neutral_validator.md` |
| Pinned frameworks | jax/jaxlib 0.10.2, torch 2.13.0, neuraloperator 2.0.0, optax 0.2.8 | `uv.lock` |
| Compute budget per Challenge | Owner direction recorded; ticket TRAINING-BUDGET-01 builds a cost calculator from the compiled graph (F4) | PR #727 |

---

## 3. The proposal: graph-only Level 4

### 3.1 The principle

> **Miners write code. Carbon accepts only the math graph that code
> produces, and only if every operation is on the allowlist and the graph
> fits the budget.**

This keeps the constitution's grader rule intact: "Carbon can widen what
participants are allowed to discover without changing who controls the
grade" (AGENTS.md §7.9).

### 3.2 Two ways to get the graph

Both should be spiked in Phase 0 (§10). They differ in who runs the miner's
Python.

| | **Option A: Carbon traces** | **Option B: miner submits the graph** |
|---|---|---|
| What the miner submits | Python source (a model function, an optional loss function, a declared input/output signature) | Serialized graphs (init, apply, and optionally loss) in StableHLO, produced by Launchpad tooling on the miner's own machine |
| Where miner Python runs | Once, in Carbon's **tracing sandbox**, on shapes only | Never on Carbon hosts |
| Who builds the training step | Carbon: it differentiates the traced graph itself and applies a registered optimizer | Carbon, if the forward graph can be differentiated after import (**to verify**), otherwise the miner submits a train-step graph |
| Security surface | The tracing sandbox (Python runs, but nothing worth stealing is there) and the graph parser | The graph parser only |
| Control and fairness | Strong: Carbon owns autodiff, optimizer menu, loop | Weaker if the miner supplies the train step: Carbon can't easily confirm what the step does, beyond its compute and constants |
| PyTorch | `torch.export` inside the sandbox | Needs a verified path from `torch.export` to a format Carbon can parse safely (**to verify**) |

**Recommendation:** build Level 4 v1 on **option A**. It matches the existing
contract model, where Carbon owns training, and keeps fairness simple. Run
the option B spike in parallel. If it shows Carbon can import and
differentiate StableHLO safely, option B removes the tracing sandbox
entirely and becomes the hardened path.

### 3.3 The rebuild pipeline (option A)

Each gate refuses with a typed reason. A refusal is a construction refusal,
never a physics failure and never `FAILED_INFRA` unless Carbon's own
infrastructure failed (invariant 7).

| Gate | What it does | What it protects | Who owns the values |
|---|---|---|---|
| **G0 Intake** | Size limit on source; declared framework (JAX or PyTorch); declared signature must equal the Challenge's interface (§5) | Parser abuse, malformed submissions | Engineering; size limit is `HUMAN_INPUT` |
| **G1 Static scan** | Reject imports outside an allowlist (no `os`, `subprocess`, `socket`, `ctypes`, `pickle`, `importlib`, file I/O, `eval`/`exec`, `__import__`); reject very large literals | Catches careless attacks only. **Not** the protection | Engineering |
| **G2 Trace** | Run the miner's functions once in the tracing sandbox (§4), with abstract shapes only, to produce the graph. Hard deadline and memory cap | Arbitrary Python runs here; the sandbox has nothing to reach | Security owner accepts the profile |
| **G3 Parse in a separate process** | The trace output is read by a Carbon process outside the sandbox, from a safe format (StableHLO text or bytecode; **never pickle**), with size limits | The trace output is untrusted data | Engineering |
| **G4 Graph validation** | (a) every primitive on the allowlist (§6); (b) total embedded constant bytes ≤ cap; (c) no dynamic-trip-count loops; (d) no RNG primitives except Carbon-keyed ones; (e) graph size and depth ≤ limits; (f) compute and peak memory from the compiled graph ≤ the Challenge's compute budget (TRAINING-BUDGET-01, F4) | Escapes, smuggled weights, unbounded cost | Caps and limits are `HUMAN_INPUT` per Challenge sheet |
| **G5 Compile in isolation** | XLA compiles the validated graph inside the rebuild worker (C-03 lane), under a deadline | Crafted graphs can target compiler bugs or blow up compile time and memory | Engineering; security owner confirms |
| **G6 Carbon trains** | Carbon's own loop: Carbon's seed initializes parameters; Carbon feeds the Challenge's TRAIN set; loss is the miner's loss graph (if Level 1 permits) or the Challenge's; optimizer from the registered menu; steps within budget | Pretrained or hidden weights; training on anything but TRAIN | Contract |
| **G7 Carbon grades** | The trained graph runs through the Challenge's unchanged exam code; outputs checked finite and in range; inference cost recorded | Numerical bombs; slow-inference gaming | Exam rule |

The miner's source is kept for audit, but nothing downstream of G3 reads it.

### 3.4 Training: what the miner controls

**Level 4 v1 proposal:** the miner controls the **architecture** (the
forward graph) and, where the Challenge's Level 1 permits, the **loss
graph**. Carbon controls initialization, the optimizer (from the existing
optax menu), the data feed, the step count within budget, and the loop.

**Deferred:** custom training steps (miner-written update rules) are a
possible later widening, JAX only. They need their own attack panel,
because a train step can encode behaviour that's hard to audit.

**Initialization:** parameters are created by the graph's init function from
**Carbon's key**, with shapes and dtypes declared. Any initializer that
smuggles values hits the constant cap.

### 3.5 PyTorch

- **Model definition only.** `torch.export` produces a program over a fixed
  core operator set (ATen core / Core IR). The allowlist is written over that
  set.
- **Training stays Carbon's.** Exported models train in Carbon's PyTorch
  loop on the validator's pinned image, or convert to JAX/XLA if a reliable
  conversion exists (**to verify in Phase 0**).
- **Serialization needs care.** `torch.export`'s saved format must be checked
  for unsafe deserialization before it is treated as data. If it can't be
  made safe, the export is re-read inside the sandbox and only a vetted
  intermediate form leaves it.

**Rule proposed:** model definition in JAX or PyTorch; custom training steps,
if ever admitted, JAX only.

---

## 4. The tracing sandbox (option A only)

This is much smaller than full Level 4–5 isolation, but it still runs hostile
Python, so **it needs the security owner's acceptance** (Level 3 rule;
`TEST_WAVE_MATRIX.md`: "Participant code runs only under isolation the
security owner has accepted").

| Property | Requirement | Why it's easier than Level 5 |
|---|---|---|
| Inputs | Source, declared signature, abstract shapes. **No data, no references, no seeds, no exam material** | Nothing to exfiltrate |
| Secrets | None in the environment, filesystem or `/proc` (cf. pod item #4) | Nothing to steal |
| Network | None | — |
| GPU | None; tracing needs CPU only | Removes GPU memory isolation (assessment §5 "GPU access: L") |
| Filesystem | Read-only root; one bounded scratch directory; output is one bounded file | — |
| Process | One process tree; whole process group killed at deadline | Assessment step 3 |
| Time and memory | Hard limits | — |
| Output | One file in a safe format, parsed outside (G3) | Output channel is narrow data, not status or timing (cf. pod item #3) |
| Lane | The C-03 Carbon lane's limits, plus a "hostile-code" profile that refuses the unlimited miner lane | Assessment step 4 already proposes this profile |

**What the sandbox does not need:**
- a stronger boundary such as gVisor or microVMs (those stay a Level 5
  question);
- GPU isolation;
- grader separation, because the grader never runs in the sandbox.

**For the security owner to confirm:** whether runc with the default seccomp
profile (C-03 today) is acceptable for this profile, given the sandbox holds
nothing of value. Separately, whether XLA compilation of validated graphs
(G5) needs the same isolation.

---

## 5. The constrained inference interface

The ladder's Level 4 wording requires one. In graph-only Level 4 it is
simply **the graph's signature, fixed per Challenge**:
- named inputs and outputs, with dtype, shape (including the batch
  dimension) and units, taken from the Challenge's existing exam inputs and
  outputs;
- a pure function: inputs → outputs, with no state, no RNG unless Carbon
  supplies the key, and no side effects;
- outputs checked by the exam's existing gates (finite values, physical
  bounds, structure heads such as battery's bounded voltage head where the
  contract requires them);
- inference cost (compute per case, from the compiled graph) recorded, and
  scored or capped as the Challenge's exam rule decides.

**What each Challenge supplies:** its interface signature (names, shapes,
units) through its adapter. This fits the TRAINING-BUDGET-01 adapter
pattern, so the definition stays Challenge-neutral.

**Input formats are a Challenge design question, not a Level 4 one.** For
example, CANTO-style work needs the Challenge to supply geometry as
parametric CAD (NURBS) rather than meshes. Level 4 can only use the inputs
the Challenge provides.

---

## 6. The allowlist

### 6.1 Shape of it

Allowlist by **primitive name in the pinned framework version**. Every entry
is versioned and digest-bound like other contract material. Any primitive
not listed is refused.

| Category | Examples (JAX names; confirm in Phase 0) | Default |
|---|---|---|
| Elementwise arithmetic and math | `add`, `mul`, `div`, `exp`, `log`, `tanh`, `logistic`, `erf`, `sqrt`, `pow`, `max`, `min`, `select_n` | Allow |
| Linear algebra | `dot_general`, `conv_general_dilated`, `transpose` | Allow |
| Shape | `reshape`, `broadcast_in_dim`, `concatenate`, `slice`, `dynamic_slice`, `squeeze`, `pad`, `gather` (bounded) | Allow; review `gather` and `scatter` for determinism |
| Reductions | `reduce_sum`, `reduce_max`, `argmax`, `cumsum` | Allow; check GPU determinism (R1) |
| Spectral | `fft` | Allow (FNO needs it) |
| Control flow | `cond`, `scan` with static length, `fori_loop` lowering to static scan | Allow |
| Unbounded loops | `while` with data-dependent trip count | **Refuse**: compute can't be counted statically |
| Custom differentiation | `custom_jvp_call`, `custom_vjp_call` | Allow only if their inner graphs also pass the allowlist |
| Nested calls | `pjit` / `closed_call` | Allow; validate recursively |
| RNG | `random_bits`, `rng_uniform`, `threefry2x32` | Refuse in inference; in training only from Carbon's key |
| Escapes to Python or native code | `pure_callback`, `io_callback`, `debug_callback`, `ffi_call`, any `custom_call` | **Refuse** |
| Host transfer, sharding, infeed/outfeed | `infeed`, `outfeed`, host callbacks, collectives | **Refuse** |
| Printing and debugging | `debug_print` and similar | Refuse |

For PyTorch, write the equivalent list over the core operator set, with
`aten` ops that call into Python, custom ops and anything outside the core
set refused.

### 6.2 Constants

- **Cap the total bytes of embedded constants**, not each constant
  separately. Otherwise a table can be split into thousands of small
  constants.
- **The cap is `HUMAN_INPUT` per Challenge.** It should allow normal
  hyperparameters, small physical constants and the Challenge's published
  normalization tables, and nothing close to a lookup table of the exam
  population.
- **Published Challenge tables** (for example battery's OCV table) can be
  provided as **named Carbon inputs**, so they don't count against the cap
  and can't be swapped.

### 6.3 Graph limits

- **Caps on op count, nesting depth and unrolled size,** to stop compile-time
  bombs. Values are `HUMAN_INPUT`, measured in Phase 0 from the largest
  legitimate graphs.

---

## 7. Rules and records that would change

| Record | Today | Proposed | Who decides |
|---|---|---|---|
| `Challenge_Roadmap.md`, construction and solver access | "Below Level 4 a submission is a declarative recipe…" | Add: "At Level 4, a submission may include source in a supported framework. Carbon accepts only the graph it produces, refused unless every operation is on the Challenge's allowlist and the graph fits the budget. No miner code runs at training, inference or grading." | Owner and tech lead |
| `Challenge_Roadmap.md`, Track A admission item 1 | Refuses executable content below Level 4 | Keep. At Level 4, refuse any submission whose graph fails G4, and any executable content that survives into the graph (callbacks, `custom_call`) | Owner and tech lead |
| `capability_registry.py` | `loss_expressions`, `composition_graphs` excluded (`EXECUTABLE_SUBMISSION`) | On the **development-only Level 4 variant** only: admissible as allowlisted graphs. The miner-facing contract is unchanged until the owners choose a level | Test Lead (development variant drafted-surface policy); owners for miners |
| Battery `level-4.json` | Empty | Graphite proposes Level 4 capabilities for battery under the climb procedure: what each adds, bounds, research, reconstruction work, attack surface, what's left out | Construction contract owner accepts |
| Attack adapter seams | `level_4_constrained_inference_export` NOT_RUN | Runnable once G0–G7 exist on the development variant | Test Lead |
| Level 3 rule | No participant code until isolation acceptance | Unchanged. Level 4 option A runs participant code only in the tracing sandbox, so that profile needs acceptance first | Security owner |
| Admission §3 declaration | "Declare whether pretrained assets, public solvers and hybrids are permitted" | Must be declared for Level 4 before testing (§11, D4) | Owner |

**No live contract changes in any of this.** A level tested internally is
never opened to miners to gather acceptance data (OWNER-GRAPHITE-TEST-WAVE-03).

---

## 8. Threat model and the Level 4 attack suite

### 8.1 What graph-only admission closes

These Admission §3 attack families are blocked by construction, because a
graph has no channel for them. Each still needs a **known-vulnerable
specimen** proving the gate fires (Admission §3 requires one per family).

| Admission §3 family | Graph-only status | Specimen to prove the gate fires |
|---|---|---|
| Network access, undeclared dependencies | Closed (no I/O primitives) | Model calling `requests`/`socket` at trace time; G1 or G2 refuses, and no I/O primitive reaches the graph |
| Model loaders, hidden assets | Closed except via constants | `jnp.load` of weights at trace time → large constant → G4 refuses |
| Embedded weights / tables | Bounded by constant cap | Table split into many small constants → total-bytes cap refuses |
| Child processes, resource escapes, device/host memory | Closed (no such primitives) | `subprocess` in model code → G1/G2 refuse |
| Caches, checkpoints, cross-attempt residue | Closed (pure function, Carbon-initialized) | Graph reading a "previous run" constant → only visible as a constant, capped |
| Run identification, timing feedback | Closed (no clock, no host transfer) | `io_callback` returning time → G4 refuses |
| Construction-to-evaluator access, answer-key exfiltration, score modification | Closed (grader never runs miner code) | Callback writing to a path → G4 refuses |
| Hidden preprocessing, inference/solver hybrids | Closed unless Carbon offers a solver op (§9) | `pure_callback` wrapping a solver → G4 refuses |
| Malformed outputs, nonfinite values, parser abuse | Partly: outputs checked at G7; parser is a surface | Graph emitting NaN on selected cases → G7 refuses; oversized/deep graph → G3/G4 refuse |

### 8.2 What stays open (owned by the exam, not by Level 4)

| Family | Why it stays open | Owner |
|---|---|---|
| Score gaming: boundary optimism, sacrificing rare cases, exploiting averaging, always-safe predictors | Legitimate math can do these | Exam design, divergence detector (Admission §3.1), Track B |
| Case and seed inference, recognizing known inputs | A model can learn to spot specific inputs if they repeat | Rotating batches, sealed pool, constant cap |
| Encoded prior knowledge | A compact procedure can generate a large table from few constants; code inspection can't prove its absence (Admission §3) | Declared rule on priors and hybrids (D4); a cheap valid method is a discovery |
| Colluding submissions, near duplicates | Same as today | Graph canonicalization and hashing (also used for "never rebuild a duplicate") |

### 8.3 New, graph-specific attacks to add to the suite

| Attack | What it tries | Expected defence |
|---|---|---|
| Callback smuggling | Any of `pure_callback`, `io_callback`, `debug_callback`, `ffi_call`, `custom_call`, including nested inside `custom_vjp` or `pjit` | Recursive G4 validation |
| Constant splitting | Thousands of small constants totalling a table | Total-bytes cap |
| Procedural tables | A small seed and arithmetic that regenerate a large table at runtime | Not blockable; counted as encoded prior knowledge (D4) and measured by Track B |
| Unbounded loop | `while` with a data-dependent trip count to dodge the compute count | G4 refuses dynamic trip counts |
| Compute under-counting | Graph whose real runtime is far above its compiled FLOP estimate (e.g. denormals, pathological gathers) | R6 stress phase and the R7 time safety net (PR #727) |
| Compile bomb | Graph engineered to explode XLA compile time or memory | Graph size limits (G4); compile deadline in isolation (G5) |
| Compiler exploit | Crafted graph targeting an XLA bug | Compile inside the rebuild worker, not the grader host (G5) |
| Trace-time divergence | Code that behaves differently under tracing than when run locally | Irrelevant to the grade: only the traced graph is trained and scored. Recorded so miners aren't misled |
| Nondeterminism | Ops nondeterministic on GPU (`scatter-add`, some reductions) | Determinism check R1; deterministic XLA flags; restrict ops if needed |
| RNG leakage | RNG in inference to fingerprint runs or vary by batch | Refused in inference |
| Interface abuse | Outputs that pass shape checks but encode signals (e.g. extra precision bits) | Exam gates; outputs rounded or validated to the interface's precision if needed |
| Initializer abuse | Init function that ignores Carbon's key and builds fixed weights | Init graph validated like any other: constants capped, key must flow into every parameter (check by data-flow analysis) |

### 8.4 Residual risks to state plainly

- **The tracing sandbox runs hostile Python (option A).** Its safety rests on
  it holding nothing of value and on the container boundary. That is a
  security-owner acceptance, not a test result.
- **The graph parser and XLA compiler are attack surfaces.** They are mature
  but not designed for hostile input.
- **Zero findings means attempted coverage, never a bound** (Admission §3).

---

## 9. Optional middle step: Carbon's solver as a graph operation

Many of the most valuable methods are physics–ML hybrids: run a coarse solve,
then learn a correction. Under graph-only Level 4 they're refused, because a
solver isn't a math primitive. Instead of opening Level 5 for them, Carbon
can expose its **own** reference solver as one registered, allowlisted
operation:
- fixed signature, for example "coarse solve at resolution r";
- metered: its compute cost is a known function of its arguments and counts
  against the budget;
- pinned with the validator image, as the Launchpad solver already is
  (licensing caveats for GPL solvers per the roadmap).

**Decision D5 (§11):** whether this is part of Level 4 or a later level.

---

## 10. Test plan to reach Level 4 testing

Each phase has an exit condition. Phases 0–1 need no security acceptance and
no miner exposure. Everything runs on Carbon's development-only Level 4
variant, under OWNER-GRAPHITE-TEST-WAVE-03:
- the variant is held outside `CONTRACTS`;
- miner surfaces refuse it;
- open findings tag results as conditional rather than stopping exploration.

**Phase 0: Spike (CPU, no pods, no miner code).**
- **Trace legitimate models.** Trace every battery family (MLP, DeepONet,
  k-nearest-neighbour where meaningful) in JAX, and the PyTorch FNO via
  `torch.export`. Record every primitive produced.
- **Probe safe serialization.** Check StableHLO export/import from the
  pinned JAX, and whether `torch.export`'s saved format can be parsed
  without unsafe deserialization.
- **Probe option B.** Can Carbon differentiate an imported StableHLO forward
  graph?
- **Measure** graph sizes, compile times and constant bytes for the largest
  legitimate recipes.
- **Exit:** allowlist v0; measured inputs for the caps and limits; a
  written recommendation on option A vs B; open questions listed.

**Phase 1: Validator and Carbon training loop (CPU, fixtures).**
- **Build** G0, G1, G3, G4 and G6 as Challenge-neutral code, with battery
  as the first adapter.
- **Equivalence test (the key correctness check).** Express battery's
  existing Level 0 recipes as Level 4 graphs. Train them through the graph
  path. Confirm they match the declarative path within the R1 determinism
  rule. This proves the graph path changes nothing about honest recipes.
- **Specimens:** one known-vulnerable specimen per row of §8.1 and §8.3,
  each refused at the expected gate.
- **Exit:** equivalence holds for every battery family; every specimen is
  refused at its gate; no Challenge-specific literal in shared code.

**Phase 2: Tracing sandbox and compile isolation (option A).**
- **Profile.** Build the "hostile-code" profile on the C-03 lane
  (assessment step 4). Kill the whole process group on deadline (step 3).
- **Canaries.** Write Carbon-authored canary programs: secret canaries,
  process escape, scratch exec, network attempts, resource exhaustion
  (step 5).
- **Host-side evidence.** Keep a record outside the container that the
  program can't edit (step 9).
- **Exit:** the security owner accepts this profile for Level 4 tracing,
  and confirms G5 compile isolation. Skipped if option B is chosen and
  needs no sandbox.

**Phase 3: Graphite on the development Level 4 variant (battery first).**
- **Proposal.** Graphite proposes battery's Level 4 capabilities (climb
  procedure); the contract owner accepts or declines.
- **Constructor** explores new architectures within the allowlist.
- **Attacker** runs the full Admission §3 suite plus §8.3, with single- and
  combined-permission attacks.
- **Findings** escalate and are never suppressed (OWNER-CHALLENGE-ADMISSION-01).
- **Exit:** a Level 4 TESTED record (`ladder.py`), or a recorded finding the
  owners must decide on.

**Phase 4: Budget and inference cost.**
- **Compute budget.** Plug the graph-derived compute count (F4) into the
  compute budget (TRAINING-BUDGET-01).
- **Budget study at Level 4.** Run battery's training budget study with
  Level 4 recipes in the panel, so the budget isn't set only on Level 0
  families.
- **Inference cost.** Record inference cost per case.
- **Exit:** the budget study's R5 decides whether battery's Level 4 uses a
  compute budget.

**Phase 5: Owners choose a level.**
- **Choose:** the owners choose the best tested level, then a frozen run
  and a lock.
- **Opening to miners** is a separate, released contract decision.

**Second Challenge.** After battery, repeat Phases 1 and 3 on one other
Challenge with a contract (cold plate or motor). Its adapter supplies the
interface and allowlist adjustments; shared code is unchanged. That is the
proof the design is Challenge-neutral.

---

## 11. Decisions needed

| # | Decision | Who | Blocks |
|---|---|---|---|
| D1 | Adopt "graph-only" as the meaning of Level 4 admission, and the roadmap wording in §7 | Owner, tech lead | Phase 1 onward |
| D2 | Option A (Carbon traces) for v1, with option B spiked in parallel | Test Lead, tech lead | Phase 1 design |
| D3 | Accept the tracing sandbox profile (§4) for hostile Python at trace time; confirm compile isolation (G5); confirm that graph-only Level 4 doesn't require pod items #3/#4 resolved, since no participant code runs in pods | Security owner | Phase 2, and any run of participant code |
| D4 | Declare for Level 4: are pretrained assets, public solvers, analytic priors and hybrids permitted? (Admission §3 requires the declaration before testing) | Owner | Phase 3 |
| D5 | Is Carbon's solver as a graph operation (§9) part of Level 4, or a later rung? | Owner, tech lead | Scope of Phase 3 |
| D6 | Per-Challenge values: constant-bytes cap, graph size/depth limits, source size limit, inference-cost rule. All `HUMAN_INPUT`, informed by Phase 0 measurements | Owner (sheet), tech lead | Phase 1 thresholds |

---

## 12. Level 5, for completeness

**What Level 5 is for.** Custom inference that can't be a pure math graph:
calling an external solver inside inference, custom GPU kernels, adaptive
meshing, libraries outside JAX and PyTorch. It means running miner code at
grading time.

**Proposed order:** graph-only Level 4 → solver-as-operation (§9) → true
Level 5, only where Phase 3 shows a valuable method blocked.

**Requirements, from the isolation assessment §8 and the owner discussion:**

1. **Security-owner decisions.**
   - Where hostile code runs: Carbon hosts or provider pods.
   - The boundary: likely gVisor or microVMs, which reverses the C-03
     rejection for this use.
   - GPU policy: dedicated GPUs or partitions, memory clearing between runs.
2. **Carbon builds the image.** Miners submit source and pinned
   dependencies; Carbon builds from approved base images. Nothing downloads
   at runtime; weights are declared and size-capped.
3. **Narrow channel.** No network or credentials. Fixed-format tensors in
   and out; no logs back to the miner.
4. **Fresh box per batch** or per case, so nothing carries over.
5. **Blind inputs.** No identifiers, shuffled order, decoy and canary cases
   mixed in.
6. **Fixed time per case,** padded, so timing reveals nothing.
7. **Delayed, aggregated feedback,** never per-case scores.
8. **Pod items #3 and #4 resolved** before any pod work.
9. **Testing, in order:** Carbon canaries → Graphite Attacker with
   vulnerable specimens → host-side evidence → independent security review
   and acceptance.
10. **Rollout:** Graphite only → one Challenge with small rewards and a bug
    bounty → wider.

### 12.1 The Level 5 internal lane (future phase, gated on stage C results)

**Status.** This is the owner's approved strategy
(OWNER-LEVEL5-INTERNAL-LANE-01, 2026-10-09). It is a future phase, gated on
Level 4's stage C results, and nothing in it is built, specified or
accepted yet. It does not open the miner-code route above. Any future
miner-code path still needs every requirement in §12.

**What it is.** Level 5 is Carbon's **internal** research lane, and miners
never run code in it:
- Graphite's Constructor explores honest gains there.
- Graphite's Attacker tries to break each one.
- Attack findings never ship.

**How a gain is classified.**

| The gain is | It becomes |
|---|---|
| Plain math | An allowed op, or a library block in the allowlist. |
| A solver need | The solver op (§9). |
| A speed kernel | A Carbon-owned, audited kernel, registered by name. |
| A library | Wrapped, if it is pure. Otherwise it stays internal. |

**How a gain ships.**
1. Carbon implements it.
2. Carbon checks its determinism and its compute counting.
3. Carbon runs the Level 4 attack suite against it.
4. It ships in a **versioned** image and allowlist, tied to a new Challenge
   version.

Nothing changes mid-competition, and old results stay bound to the toolkit
they ran under.

**Four conditions.**
1. **True cost.** Every op is counted at its true cost in the compute
   budget. Solver-calling ops get a hard rule, for example training only and
   never at inference, so that no op defeats the fast-model purpose.
2. **Specs, never code.** Miner proposals arrive as written specs, never
   code. A proposer gets credit and a bounty, with **no exclusive access**.
   The bounty terms are `HUMAN_INPUT`, for the owner to set.
3. **Batched releases.** One toolkit version per competition period.
4. **Parity.** Every new kernel passes the existing backend-parity and GPU
   device-class acceptance.

**Open owner items** (all `HUMAN_INPUT`):
- which findings stay Workbench-internal rather than shipping in the base
  image;
- GPL and licensing, op by op;
- per-run grants for internal Level 5 work;
- the security sign-off for running Attacker code on disposable hosts.

**Starting now: the refused-capability log.**
`docs/development/graphite/level4/REFUSED_CAPABILITY_LOG.md` records every
capability Graphite asks for and Level 4 refuses during stages A to C. It is
the evidence for which Level 5 ops to build first.

---

## 13. Non-claims

- This document is a proposal. It earns no SPECIFIED, IMPLEMENTED, TESTED or
  SECURITY_QUALIFIED state for anything.
- Graph-only admission reduces the attack surface; it does not make
  arbitrary-code execution secure, and no test result here would be a
  security audit (AGENTS.md §13).
- No production value (caps, limits, budgets, margins) is chosen here.
- Nothing opens to miners without a locked, released contract chosen by the
  owners.

---

## Appendix A: references

| Topic | File |
|---|---|
| Ladder and Track A | `Design_Specs/Challenge_Admission.md` §3, §3.1 |
| Climb procedure, Track A admission, construction access | `Design_Specs/Challenge_Roadmap.md` |
| Ladder record | `carbon/challenge_pipeline/ladder.py` |
| Level proposals | `carbon/challenge_pipeline/proposals/battery-fastcharge-ageing-development-v1/` |
| Development variants, conditional findings, assess isolation | `.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md` |
| Isolation readiness | `docs/development/graphite/ISOLATION_READINESS_L4_L5.md` |
| Test-wave gates | `docs/development/graphite/TEST_WAVE_MATRIX.md` |
| Pod security items #3, #4 | `.agent/tickets/VALIDATOR-01_challenge_neutral_validator.md` |
| Registry exclusions | `carbon/reconstruction/capability_registry.py` |
| Attack adapter seams | `carbon/agent_campaign/attack/adapters/battery.py` |
| Compute budget, cost calculator, budget study | PR #727; `.agent/tickets/TRAINING-BUDGET-01_challenge_neutral_study_and_compute_budget.md` |
| Grader separation | `AGENTS.md` §7.9 |

---

## Appendix B: Test Lead assessment (2026-10-07)

**Overall.** I recommend adopting graph-only Level 4. It is protect-first
admission: the freedom widens to new architectures, and the attack surface
shrinks by construction. It matches the owner's direction of maximum
construction freedom with maximum value alignment.

**A refinement to option B, to be tested in the Phase 0 spike.** Call it B′:
Carbon's own graph format plus an allowlist interpreter.
1. **Launchpad tooling, on the miner's machine,** lowers the JAX jaxpr or
   PyTorch `torch.export` program into a **Carbon-defined graph format**. That
   is strict JSON, parsed with the existing `strict_json` rules, with one
   node per allowlisted primitive, explicit shapes and dtypes, and constants
   as counted byte blocks.
2. **The validator parses only that format.** No third-party deserializer
   (StableHLO bytecode, `torch.export` archives, pickle) runs on a Carbon
   host.
3. **Carbon rebuilds the graph** by mapping each allowlisted node to its own
   JAX implementation. That gives one interpreter for G4 validation and G6
   training. Carbon then differentiates the rebuilt function with its own
   autodiff. Gradients are never miner-supplied, so option B's fairness
   concern disappears.

If B′ holds, then:
- no miner Python runs on any Carbon host;
- the tracing sandbox and its security-owner acceptance (D3) are not
  needed for Level 4;
- PyTorch and JAX share one validator path.

The question the spike has to answer is the **equivalence test**: do
battery's Level 0 families rebuilt through B′ match the declarative path
under R1?

**Recommended answers.** These are for the owner and tech lead.

| # | Recommendation |
|---|---|
| D1 | **Adopt** graph-only Level 4, with the §7 wording. |
| D2 | **Phase 0 spikes A, B and B′ side by side.** Build v1 on B′ if it passes the equivalence test, otherwise on A. |
| D3 | **Needed only for option A,** or for G5 compile isolation. Ask the security owner after Phase 0, with the chosen option in hand. |
| D4 | **Pretrained assets:** no in v1 (the constant cap enforces it). **Analytic priors and procedural forms:** yes; they are discoveries, and Track B measures their value. **Public solvers:** only through D5. |
| D5 | **A later rung (call it 4.5),** designed in parallel once Level 4 v1 is TESTED, because physics–ML hybrids are high-value. |
| D6 | **Values come from Phase 0 measurements** of the largest legitimate graphs, then go on each Challenge's sheet (#727 pattern). |

**Where it sits in the test plan.**
- **Phases 0–1:** CPU-only code on the development variant, in parallel with
  battery's operational path. They need no hidden data and no pods.
- **Phase 3:** the kimi-k3 Constructor (grant R4) explores Level 4, and the
  Attacker adds the §8.3 suite.
- **Phase 4:** Level 4 recipes join the #727 budget-study panel.
- **Miners:** nothing reaches the miner path until the owners lock a level.
  That is the rehearsal-first rule.
