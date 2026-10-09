# Value + cost analysis for all 8 Challenges (Test Lead, 2026-10-08)

**Owner direction:** "give me a rigorous value + cost analysis to run on these. Give codex the freedom to fix the customer question to something we can execute AS LONG AS its value is real and clear. run it on all of them."

**Purpose.** One scorecard per Challenge that decides **keep**, **reframe** or **replace** on evidence. It covers all 8: battery (v3), motor, cooling cell, f02, f06, f08, f13 and f17.

The [cheap buyer-method baseline specs](BASELINE_SPECS.md) define the matched
comparison Data Collection must measure for V4. They set no acceptance value.

---

## Part V: is the value real and clear? (packets Codex; evidence cited)

| # | Criterion | Pass condition | Evidence required |
|---|---|---|---|
| V1 | **Real decision** | A named buyer role makes exactly this decision today, using simulation | ≥ 2 independent public sources: an industry workflow, tool documentation or published design studies. No invented buyers. |
| V2 | **Value at stake** | The value of a better decision, in buyer units (USD, minutes, kWh, yield %), with an explicit assumption chain | Every number either sourced or labelled ASSUMPTION, with a low/base/high range |
| V3 | **Volume** | How often the decision is made (designs per year, market proxy) | Sourced, or a labelled ASSUMPTION range |
| V4 | **Surrogate leverage** | Measured reference cost per evaluation × the evaluations a buyer runs per decision, i.e. what a fast model saves | Reference cost from Part C; workflow evaluation count sourced |
| V5 | **Credibility tier** | The tier (#767) we can honestly claim for the reframed question (Tier 2 = agrees with the buyer's industry simulator workflow) | The reference route and what it cannot claim |

**Reframing freedom, with the guardrails the owner set.** Codex may change the buyer question (decision variables, objective, limits, strata, model fidelity such as 2D, axisymmetric, periodic-cell, or a different but adjacent component) **only if** every one of these holds:
1. V1–V3 are evidenced for the **new** question.
2. The value is not inflated: report V2 for the original and the reframed question side by side, and **state what the buyer gives up**.
3. The fidelity reduction matches **how industry actually does this design step** (cited), and the credibility claim drops to match (V5).
4. Hard safety and feasibility limits are never relaxed to manufacture feasibility. Requirement values may move only to real buyer-realistic values, with a source.
5. It's prospective: historical evidence is unchanged, and the result is a new packet version.

## Part T: is it a valid, game-proof test? (Data Collection measures; the Test Lead judges)

| # | Criterion | Pass condition (working values; final thresholds are the owner's) |
|---|---|---|
| T1 | **Feasibility** | At least one design is feasible across every stratum (or per band for indexed decisions), on refined truth |
| T2 | **Value check** | Every stratum: (a) **contested decisions**, meaning at least 5 feasible **and** at least 5 infeasible designs among the buyer-plausible action set, with infeasible designs **near** the feasible frontier (within one refinement band of a limit). The overall pass fraction is reported but isn't a gate: a wide action set legitimately has a low pass fraction, and narrowing the set just to raise it would be gaming the check. (b) A margin spread of at least a meaningful buyer unit. (c) Holds with T1. (d) The best answer changes across strata or draws. |
| T3 | **Power** | Behaviour-defined controls (edge-optimist, over-cautious, sign-error, lattice-aware) detected with probability ≥ 0.8 at α = 0.05, at a registered moderate severity, **within E exposures of cross-batch accumulation**, at a k per batch the cost allows |
| T4 | **Close calls** | The residual UNRESOLVED rate after refinement is ≤ 25% of questions (battery v8 was 87.5%; that is the problem to fix) |
| T5 | **Reference adequacy** | Refinement convergence within the packet tolerances; conservation checks (energy, mass, power) within tolerance; no reference finding left open on the scored region |

## Part C: is it affordable? (Data Collection measures)

| # | Measure | Pass condition (working values) |
|---|---|---|
| C1 | Per-case reference cost, p50/p95 CPU-h, and peak memory | Measured on the pinned package. No hypothesis values |
| C2 | **Bank startup cost:** B × C1 plus refinement, in € on a CCX63 (€1.37/h) | **≤ €100 per startup** |
| C3 | **Ongoing cost:** (draws per week ÷ E) × C1 | ≤ 15% of one AX42-equivalent per Challenge |
| C4 | Validator cost per submission: rebuild and inference, CPU or GPU-minutes | Fits the #727 budget-study envelope |

## The decision rule

- **KEEP:** V1–V5, T1–T5 and C2–C3 all pass.
- **REFRAME:** any fail, so Codex proposes one reframed question under the guardrails, and Data Collection re-measures. **One reframe cycle per Challenge.**
- **REPLACE:** still failing after the reframe, so the owner chooses a replacement from candidates passing at least V1–V3 and an estimated C2 ≤ €100.
- **Ranking:** value-to-cost index = V2 (base) × V3 (base) ÷ (C2 + 52 × C3 weekly €), reported with its low/high range. This is an ordering aid; it never overrides a failed gate.

## Who runs what, per Challenge, in parallel

| Step | Owner | Output |
|---|---|---|
| 1. Value dossier (V1–V5), plus a reframe proposal wherever T or C is known to fail (f06, f13, f17, cooling, motor) | packets Codex | `value-cost/<challenge>.md`: an evidence table plus the reframed packet version, as one PR |
| 2. Cost measurement (C1–C4) on the current or reframed route | Data Collection | a ledger per Challenge (local CPU, or one small grant box at a time, approved by the owner) |
| 3. Feasibility, value check and close-call rate (T1, T2, T4, T5) on a registered panel | Data Collection | per-Challenge results |
| 4. Power (T3), via the neutral power harness (#786) on the solved panel | optimizer Codex adapters + the Test Lead | per-Challenge power report |
| 5. The scorecard and the keep, reframe or replace recommendation | Test Lead → owner | one table, all 8 |

**Already measured:**
- **Battery:** T1 ✅ (the v3 map exists); T3 ❌ within one batch (8 questions; cross-batch pending); T4 ❌ (87.5%); C1 ✅ 91 CPU-s.
- **f02:** C1 ✅ 2–3 CPU-min.
- **f13:** C1 ❌ (> 2 h per curve) and T5 ❌ (4.7% power balance).
- **Cooling Set A:** panel running.
- **Motor:** stage 3 running.
