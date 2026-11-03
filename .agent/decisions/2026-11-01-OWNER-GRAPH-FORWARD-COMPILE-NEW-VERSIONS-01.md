# OWNER-GRAPH-FORWARD-COMPILE-NEW-VERSIONS-01: graph models compile once; ships before the 4 new versions open

Date: 2026-11-01 (CST), ~21:00
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words, in order: "Great! Let's get this fix in"; "Just need it before these challenges go in"; and, on the Lead's plan for the widened miner finding, "Great. Lock it in and audit any other graph building issues that are limiting our miners".

## Context (miner reports, verified in code on main)
- `carbon/level4/interpret.py` builds new Python lambdas for `_while`, `_scan` and `_cond` on every forward call, so JAX re-traces and recompiles every loop body for every case. Miner repro: 0.34 s per call falls to 0.006 s when the body is built once, with bit-identical outputs.
- Rebuilt graphs run eagerly, op by op, in practice, in the trainer's train predictions and in judge inference. Miner figures: about 7 s per case on a 3090 with loops, and about 2 s on GPU or 27 s on 2 CPU cores even without loops. A practice makes about 420 single-row calls, so a physics-in-graph recipe cannot finish the 600 s practice or be frozen.

## Decided
1. **Loop-body cache fix:** build the loop-body callables once in `rebuild()` and reuse them. No op, number or ordering changes, and outputs must be bit-identical. It applies to every version.
2. **Compiled forward, versioned:** the rebuilt forward is compiled once per parameter state with jax.jit and used identically in practice, the trainer's predictions and judge inference. It applies only to versions that opt in, which the Lead recommends as the 4 new versions. Live versions keep eager execution.
3. **No rescore:** nothing already graded is rescored or reinterpreted.
4. **Timing:** both ship in the worker image the 4 new versions (Ribbed Bracket 2.0, Burst Thermal 3.0, Motor 1.7, Cooling 1.8) open on. They are a ship condition for each, and are NOT part of the current image move (8c6faad8).
5. **Validator:** rules the exact design and the opt-in list, and receipts the head. Tests cover run-to-run bit equality under jit, a reported jit-vs-eager difference, and the practice wall time on a scan graph.
6. **Audit:** the Lead audits other graph-building limits on miners, and each fix gets its own record or receipt.
