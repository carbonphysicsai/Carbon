## TL;DR

**What this is:** The build plan for Carbon’s smallest end-to-end proof — one PDE, one backbone, full **lean** validator loop. It produces the **TrainEvalAPI** handoff that Phase 0 MCP and validators call.

**The loop:** `strategy.json` → schema check → seeded train/eval/stress data → JAX retrain (FNO-1d) → metrics → hard physics gates → 45/30/25 score → **Model Card** (full internal record) on disk.

**Choices:** 1D viscous Burgers; operator map IC → solution at final time; FNO-1d only; no chain, Landscape, specialists, or product battery **in this PoC**.

**Path class:** **Lean eval only.** Product battery is out of scope — see `Specialist_Bank.md`.

**Handoff to full Phase 0:** This PoC is a **dependency** of `Build_Out.md` Phase 0, not a competing SOW. MCP, fees, testnet, and evidence-labeled PriorPacks are **out of this PoC** and **in** later Build Out waves under their ratified contracts. Do not treat “no MCP here” as “MCP is not part of Carbon.”

**Why it matters:** Proves the mechanism (strategy in, not weights; train ≠ eval seeds; gates can zero score; card out) before scaling the agent surface.

**Done when:** Acceptance tests T1–T7 pass (schema reject, seed separation, full loop, gate fail, reproducibility, strategy discrimination, budget cap).

**Build order:** Milestone A data → B train → C protocol spine → D scoring → E harden → then Build_Out MCP/validator wiring. Do not expand PoC scope until green.

**Read next if implementing:** §5 schema, §13 repo layout, §15 tests, §16 milestones; then `Build_Out.md` + `Miner_MCP.md`.

---

**Carbon Subnet**  
**Version:** 1.3 (August 2026)
**Status:** Phase-0 proof-of-concept build specification  
**Related:** `SPEC.md`, `Build_Out.md`, `Miner_MCP.md`, `Data_Management.md`, `Scoring.md`

---

## 1. Purpose

Build the **smallest complete Carbon lean loop**:

```text
strategy.json → schema check → seeded train/eval/stress data
  → JAX retrain (FNO-1d) → metrics → hard physics gates
  → 45/30/25 score → Model Card
```

**Goal:** prove the *mechanism*, not SciML SOTA, not full subnet ops, not commercial productization.

If this PoC passes its acceptance tests, Carbon’s atomic unit is real: miners submit **strategies**, validators **retrain**, eval data is **seed-generated**, gates can **zero** a run, and every run emits a **Model Card**.

Export the official PoC entrypoint as **`TrainEvalAPI`** with an
`OfficialTrainEvalRequest` and an official-data handle. A later practice runner
may reuse internal numerical kernels, but it must use a nominally distinct
request, result, data handle, and service path. A caller-controlled mode string
must never select official versus practice data rights.

---

## 2. Scope Lock

### In scope

| Item | Detail |
|------|--------|
| PDE | 1D viscous Burgers |
| Backbone | FNO-1d only |
| Operator form | IC → solution at final time |
| Strategy JSON | Minimal but real schema |
| Data | Procedural generator; train ≠ eval ≠ stress seeds |
| Train | JAX, budget-capped |
| Gates | Finite, conservation, residual ceiling (+ BC if used) |
| Score | 45% physics / 30% robustness / 25% accuracy (Score Pack fields) |
| Output | Model Card JSON on disk |
| Entry point | CLI `run_once` + TrainEvalAPI surface (no chain required) |

### Out of scope (explicit non-goals for *this PoC*)

- Bittensor neuron / Yuma / emissions (**→ Build_Out C15**)  
- Miner MCP, Wave B research operations, practice tasks, and the official submission/result lifecycle (**→ `Miner_MCP.md`, the Wave B research contract, and Build Out C9**, after TrainEvalAPI)
- Landscape Agent, specialists, immutable coarsened PriorPack *service* (**→ later phases**)
- **Product battery** (PB-INV, deep PB-ROLL, PB-ADV, PB-LAT, PB-ART)  
- Multi-challenge, multi-backbone, multi-physics  
- TPU, multi-GPU, full ONNX commercial pipeline  
- Adaptive stress, D9 routing, multi-fidelity curricula  
- “Best possible Burgers accuracy”  
- Any package path named `hydrogen/` — use **`poc/`** only  

**Note:** Out of PoC ≠ out of Carbon. Full Phase 0 subnet loop is specified in `Build_Out.md`.

---

## 3. Challenge Definition (summary)

1D viscous Burgers; operator IC → u(·,T); FNO-1d; procedural data with role-separated seeds. Full numeric envelope and schema live in-repo under `poc/` and Score Pack YAML when implemented.

---

## 4. Acceptance (T1–T7)

T1 schema reject · T2 seed separation · T3 full loop · T4 gate fail zeros score · T5 reproducibility · T6 strategy discrimination · T7 budget cap.

---

## 5. Handoff checklist (before Build_Out MCP wave)

- [ ] `TrainEvalAPI.run(OfficialTrainEvalRequest, OfficialDataHandle, limits) -> InternalResult` exists
- [ ] The official request and data handle require validator-owned role/seed provenance
- [ ] Reusable internal kernels accept no public authority selector; a later practice wrapper must provide nominally separate request/result/data-handle types
- [ ] Model Card written with pack hash + gate vectors  
- [ ] T1–T7 green  

Then proceed to `Build_Out.md` Waves A–C (MCP, fees, cards, testnet).

---

*POC_Burgers_FNO v1.3 — atomic lean loop, nominal practice separation, and explicit TrainEvalAPI handoff to full Phase 0.*
