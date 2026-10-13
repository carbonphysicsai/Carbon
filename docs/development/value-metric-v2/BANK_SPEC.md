# V2 question bank: Challenge-neutral specification

**State:** REGISTERED_SPEC, DEVELOPMENT, 2026-10-13. Companion to [`DEFINITION.md`](DEFINITION.md) (VALUE-METRIC-V2 rev 2). It says what a Challenge's V2 bank must contain so that V2 can be measured, its values chosen from curves, and the score confirmed on sealed questions. **Every number is HUMAN_INPUT unless stated.**

**Why a new bank:** RES-09 (#1241). Under V2's admission rule, battery's EV4 panel keeps only 2 nominal questions and 1 shifted question. Old panels lack complete action references.

## 1. Inputs a Challenge must register first

1. **The question law** (DEFINITION §1): the action grammar A, conditions, objective and unit u, feasibility checks and bands, fallback b(q), P and w.
2. **The verified reference:** a pinned solver image, with its MMS acceptance link. The link's verified scope and conditions must cover the objective and feasibility observables.
3. **The validity declaration** (VALIDITY-ENVELOPE-01): no question outside declared validity.
4. **The TRAIN separation rule:** how bank questions stay physically separate from public TRAIN data (geometry, conditions or distance). Seed separation alone is not enough.
5. **The strongest cheap arm** (DEFINITION §7), frozen before step 4.

## 2. Construction

1. **Draw the contexts from P** with a recorded seed. The drawer is deterministic, and its draws are committed before any solve.
2. **Solve every action under every condition of every question on the verified reference**: |Q| × |A| × c condition-solves. **No partial solves.** A failed solve is retried, and stays FAILED_REFERENCE if it keeps failing. It is never imputed.
3. **Classify each question by reference alone, before any model sees it:**
   - SCORED: complete, with the fallback FEASIBLE;
   - RESCUE: the fallback is INFEASIBLE;
   - NONE: no FEASIBLE action;
   - INCOMPLETE: any failed or missing reference, or an UNRESOLVED (in-band) action whose reference objective could beat the best feasible action.

   **Decision-determined questions are SCORED** (DEFINITION §4). That covers any question where every UNRESOLVED action is in-band, has a known objective, and is no better than the best FEASIBLE action. Near-limit candidates don't remove a question when they can't change its best answer. The manifest reports, per class, how many questions were admitted only because they are decision-determined.

   **Rule:** at least half of the questions should be SCORED. If fewer are, the fallback or population needs redesign before the bank is worth its cost (RES-07: the battery default was feasible on only 5–7 of 12).
4. **Split into halves by a sealed random assignment at the block level** (§5):
   - **The development half:** public. Used for curves, the owner's value choices, and the winnability check (§4).
   - **The confirmation half:** sealed under custody, the same as current custody records. It is never read by anyone choosing values. It is opened once, after the owner's value record is merged.

## 3. Records (one per question; JSONL; digest-bound)

Each record holds:
- `question_id`, `block_id`, `half`, `context` (the conditions), `fallback_action`, `class`;
- for each action and condition: `status` (FEASIBLE / INFEASIBLE / UNRESOLVED / FAILED_REFERENCE), `objective`, the constraint margins, and the solve provenance (image digest, overlay lock, record sha);
- the manifest: drawer seed commitment, question-law digest, definition digest (`definition.v2.json`), image digest, MMS acceptance link digest, TRAIN-separation check result, counts per class, and the per-stage wall and core time (the onboarding metric).

**Sealed-half records live only in custody.** Only their manifest digest and class counts are public before opening.

## 4. The winnability check (development half only)

This decides whether the Challenge can carry V2 value evidence (DEFINITION §7):

| Measure | Pass when |
|---|---|
| Cheap-arm ceiling capture on SCORED questions, at the registered k | below the owner's threshold (HUMAN_INPUT) |
| A development reference model's paired net margin over the cheap arm | positive, with the paired lower bound above 0 |
| Always-abstain | scores exactly 0 |
| Learnability | a reference model's accuracy improves with TRAIN size (the OPT-12 harness) |

**A failure means the Challenge is not a proof Challenge.** Widen the action space, add conditions, or pick another family (PRIORITIES 2026-10-13, Track A step 3). A fail is a legitimate, reported outcome.

## 5. Size: blocks, not just questions

- **A block** is a group of questions that share no reference case or condition. Blocks are the unit of the paired test.
- **The confirmation half needs B ≥ ⌈log₂(1/α)⌉ blocks**, just to make α attainable with a one-sided sign test. That's 7 blocks at α = 0.01 and 10 at α = 0.001, every one favourable.
- **Plan at least 2× that,** so a few unfavourable blocks don't make the test impossible. The final B comes from the development half's measured between-block variance, at the owner's Δ_min.
- **The development half needs enough SCORED questions** for stable curves across k and κ. Proposal: as many blocks as the confirmation half.

**Cost:** |Q| × |A| × c reference condition-solves × the measured seconds per solve. **Add any refinement the Challenge's reference policy requires for near-limit results** (for example battery-plating-ref-v2: one fine-mesh solve per in-window action × condition, plus a 10 % trigger subsample). Size it from the measured in-window share **before** the bank is cut; a bank concentrated near limits pays most of it. Use the Challenge's measured solve time from its readiness evidence, on RunPod under the standing test grant. Anything larger goes to the owner as a figure.

## 6. Disclosure and use

- **The development half:** public. Released with references for TRAIN-separation audit and curve reproduction.
- **The confirmation half:**
  - only aggregates are shown after opening;
  - per-question release follows the Challenge's normal release policy;
  - it is never used for training, selection or value choice.
- **The bank is versioned:** any change to the question law, the reference image, the drawer or the definition is a new bank version. Old versions keep their meaning.

## 7. Battery first (Track A)

Battery's v3 design bank already solves every action for its Q3 questions. It becomes a V2 bank if it meets §2.3's SCORED share and §4's winnability check. RES-10 says which battery families could. Otherwise the proof moves to the best Track B pilot, under this same spec.

## 8. Neighbour-task questions (the owner, 2026-10-13)

**Value must count the target task and the task "if it changes a little".** So a V2 bank also carries **neighbour tasks**: the same Challenge with its objective weights, constraint limits or operating conditions nudged.

- **Declared with the question law.** Each neighbour is a registered variant of the question law, with its id, which knob is nudged, by how much, and why a buyer could face it. It is declared **before** the bank is built, never chosen after looking at models.
- **Solved like the target.** Every action is solved under every condition, it is classified by the reference alone, and it is split into development and sealed halves by block, alongside its target questions. The neighbour must stay inside declared validity.
- **Cost.** A nudge to objective weights or constraint limits re-uses the target's solves: only the classification and objective are recomputed. A nudge to conditions needs new solves. Prefer the first kind where it is representative.
- **Use.** The score lab, and later a registered score, may compute value on the target and average it over the neighbours with a neighbourhood weight ρ_n. That weight is HUMAN_INPUT and is read from curves. The definition's reuse rule applies: ρ_n = 0 in any registered score until independent neighbour strata pass their own confirmation.
- **Records.** Each question record gains `task: "target" | "<neighbour id>"`. The manifest lists the neighbour declarations and their counts per class.

## 9. REF-RESOLVE: a reference-policy proposal for near-limit candidates (owner decision)

**Why.** Near-limit decisions are where customer value lives. PDD shows the battery question law draws many candidates right at plating onset, inside the reference band (±1.97 mV), and re-solving at the same rung never resolves them. Decision-determination (§2.3) keeps questions where those candidates can't be the best. It can't keep questions where they could, and plating-onset designs are often the fastest.

**The proposal:** a tighter band per refinement rung, only where the solver's verified precision supports it.
1. **Solution verification of the observable first.** For each decision observable (battery: the plating margin), measure its numerical error ε_r at each refinement rung r on the pinned image: a rung-to-rung convergence study with an observed order of convergence. **The accepted MMS doesn't cover this:** it verifies particle diffusion and lumped heat, not plating overpotential.
2. **The band at rung r:** band_r = c · ε_r, with c ≥ 1 (HUMAN_INPUT). It is never tighter than ε_r (PHYSICS_CONTRACT_01 §0, guardrail 1).
3. **Adaptive refinement.** Only in-band candidates are re-solved at finer rungs, until they resolve or reach the finest verified rung. A candidate still in-band at the finest rung stays UNRESOLVED (§2.3 then applies).
4. **Records** carry the rung and band each status was decided at. The manifest reports the refinement solves spent.
5. **Binding.** The bands, rungs, c and the convergence evidence are bound to the image digest, re-measured on any rebuild, and adopted only by an owner reference-policy record.

**Cost:** extra solves for in-band candidates only, at finer rungs. Estimate it from PDD's in-band share before the owner decides.
