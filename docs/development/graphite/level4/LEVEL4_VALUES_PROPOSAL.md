# Level 4 values: team proposes, owner approves

**Status.** PROPOSED. Every value here stays `HUMAN_INPUT` in code until the
owner approves it, and approval binds development and testnet only
(OWNER-L4-G5-COMPILE-ISOLATION-01). Mainnet keeps its own review. Drafted by
the Level 4 engineer for the Test Lead to bring to the owner. Nothing here
changes code.

**Evidence.** Each value has one recommendation, the largest measured
legitimate value, and the stated headroom. Sources:
- `phase0_results.json`: every battery family's graphs, with forward, loss
  and init lowered through JAX, and the PyTorch FNO through `torch.export`.
- `values_evidence.json` (`scripts/dev/level4_spike/values_evidence.py`, a
  new run): submission sizes, in-process parse and validate, and Carbon's G5
  lane program run isolated on the staged bytes. It covers battery's Level 0
  and largest recipes and motor's Level 0.
- `phase1_e1_results.json`: E1, battery's Level 0 families trained through
  the gates, bit-identical to declarative training.
- `g3_memory_probe.json` (`scripts/dev/level4_spike/g3_memory_probe.py`):
  the real isolated parse worker on the two largest submissions, at limits
  from 96 to 512 MiB.

**What was measured on.** CPU only: WSL x86_64 with 20 CPUs, JAX 0.10.2. The
real C-03 lane adds container start-up, and GPU numbers come with the A40 R1
leg (plan PR 9). The largest legitimate recipe in every family is the
contract's architecture maxima (`largest_strategies`).

## 1. G0 intake (`carbon/level4/intake.py` `BOUNDS`)

| Bound | Largest measured | Recommended | Headroom | Why |
|---|---|---|---|---|
| `manifest_bytes` | 516 B (FNO) | **16 KiB** | 32× | A manifest is fixed fields plus up to four digests; the size grows with nothing a miner chooses. |
| `document_bytes` | 79,162 B (largest FNO forward) | **1 MiB** | 13× | The largest graph is the FNO at the contract's maxima. This also bounds G3's strict parser. |
| `submission_bytes` | 84,888 B (largest FNO) | **4 MiB** | 49× | Room for forward, loss and init each near the document bound. |

## 2. G3 isolated parse (`intake.BOUNDS`)

| Bound | Largest measured | Recommended | Headroom | Why |
|---|---|---|---|---|
| `parse_seconds` (CPU) | 0.087 s in process; ≤ 0.64 s wall isolated, start-up included | **10 s** | 15× over isolated wall | Parsing is linear in bytes; at 1 MiB per document this stays well under 10 s. |
| `parse_memory_bytes` (`RLIMIT_AS`) | the real worker parses the largest DeepONet and FNO submissions at 96 MiB | **512 MiB** | 5× | The bound covers the interpreter as well as the parse, so it is set by the worker's footprint, not the graph's. |

## 3. G4 caps (`carbon/level4/allowlist.py` `CAPS`)

| Cap | Largest measured | Recommended | Headroom | Why |
|---|---|---|---|---|
| `document_bytes` | 79,162 B | **1 MiB** | 13× | The same as G0, so both gates agree. |
| `nodes_executed` | 444 (largest FNO forward); 365 (largest DeepONet loss) | **4,096** | 9× | Executed nodes count calls expanded; every family is under 500. |
| `call_depth` | 4 (JAX init graphs) | **16** | 4× | Depth comes from JAX's own nesting (`jit`, `custom_jvp`), not model size. |
| `constant_bytes` | 1,252 B (largest DeepONet forward) | **16 KiB** | 13× | Constants are the table-smuggling channel (§8.2). Every legitimate family carries only scalars and small index arrays, so headroom stays small on purpose. Procedural tables remain D4's seam. |
| `largest_intermediate_bytes` | 198,246,400 B (largest FNO forward) | **256 MiB** | 1.35× | Set by memory, not by graph shape (§4): at 198 MB the FNO's compile already uses 84% of the worker's 4 GiB. A larger cap would admit graphs the lane cannot compile. |

## 4. G5 compile (`carbon/level4/compile.py`)

| Value | Largest measured | Recommended | Headroom | Why |
|---|---|---|---|---|
| `DEADLINE_SECONDS` | 6.0 s lane wall (largest FNO), 2.5 s of it compiling | **120 s** | 20× | The C-03 lane admits Carbon's own runs only between 40 and 600 s (`research_carrier`). 120 s leaves room for container start and a slower host. |
| compile memory | 3.35 GiB peak RSS (largest FNO); ≤ 0.47 GiB for every JAX family | **8 GiB for the G5 lane** | 2.4× | **Finding.** The C-03 worker's memory is fixed at 4 GiB with no swap (`worker/model.py`), so the largest legitimate FNO compiles with 16% headroom. The owner can either raise the G5 lane to 8 GiB, which is a lane change not yet built, or keep 4 GiB and the 256 MiB intermediate cap above. Until one is chosen, the 4 GiB lane binds. |

## 5. The Level 4 share of the #727 compute budget

**Recommendation: one budget, no separate Level 4 share.** A Level 4 graph
is trained by Carbon's own loop, at the recipe's own batch, steps and
optimizer. So it is charged exactly as its declarative twin under the same
per-recipe budget (the battery sheet, OWNER-BATTERY-STUDY-SHEET-01), and the
G5 compile counts as setup time inside `rebuild_time_target` (300 s).

**Evidence.**
- **Same work.** E1 trains battery's Level 0 MLP and DeepONet through the
  gates bit-identically to their declarative recipes: same parameters, same
  steps (6,000 and 2,000), same batch (400).
- **Same compute.** G5's measured forward FLOPs (1.16 GFLOP for the largest
  MLP, 1.80 GFLOP for the largest DeepONet, 460 GFLOP for the largest FNO)
  are the same networks.
- **Small compile cost.** G5 adds at most 6 s, which is 2% of the 300 s
  target.

**Precondition (finding M1, #805).** The TRAINING-BUDGET-01 cost calculator
refuses every development recipe, because it compiles with the Level 0
contract. Before any budget check binds Level 4, the calculator must cost a
graph recipe through its declarative twin, or through G5's measured FLOPs.
Until then the budget check stays off, as it is today (#742).

## 6. Not proposed here

- **The inference cost rule** (`grade.INFERENCE_COST_RULE`). It is recorded
  per case and stays `HUMAN_INPUT`; a cost never enters the score without a
  registered scientific contract.
- **The transport bound** of the validator's intake. That is the
  validator's, and is set in VALIDATOR-25.
- **Constant values** (D4) and any GPU number (the A40 R1 leg).

## Approval form

Reply with one of:
- "approve §1–§5 as proposed";
- "approve with changes: <bound = value>";
- "hold <section>".

Approved values go into the code as one change, citing this sheet and the
approval. Each stays development- and testnet-only.
