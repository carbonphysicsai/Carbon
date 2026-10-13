## 2026-10-13 — VALIDATOR-PLATING-REF-V2-02: D3's stop triggers fired; battery-plating-ref-v2 is re-derived before sealing (band 1.0 mV, window upper edge 4.5 mV)

> **Read this first: count by `source`, never by the `case_id` prefix.** Every `case_id` in these files begins `ev4:`, PDD rows included. On 2026-10-13 the prefix misled three readers, the Validator among them, into attributing PDD cases to EV4. The `source` field is authoritative.
>
> **What v2 is:** a battery plating reference adequate for **development and testnet** decisions within a 1.0 mV band, with 103 newly in-window cases pending and a known, achievable narrowing deferred to a later version. **What v2 is not:** a qualified reference, a production or LIVE claim, or a claim about deep plating or about |m20| ≥ 15 mV.

**Authority.** VALIDATOR-PLATING-REF-V2-01 §7, under OWNER-PLATING-REFERENCE-01 D3: "If any m80 − m160 exceeds 0.359 mV, or a FEASIBLE case lands at m160 < 0.73 mV, the band is re-derived before v2 is sealed. It's never kept by default." This record re-derives the band **by the same method**, on D3's evidence. Changing the reference *method* (an extrapolated reference) or spending on a finer mesh is not decided here; both are the owner's (§6).

**Evidence.** Data Collection's D3: 669 near-onset EV4 cases solved at mesh 160 on cpu5m, code `a48a74ef9`. Files in `shared/evidence/plating-rereference-01/d3-results/`: `labels.json` sha256 `dc156608…`, `records.jsonl` `ef8c6260…`, 19 receipts. The stratified subsample of 67 cases was solved at meshes 40/80/160.

### 1. What D3 found

- **Mesh 20 overstates the margin in all 669 cases.** m20 − m160 runs from 0.32 to 3.18 mV and is never negative. The worst bias among positive-m20 cases is 2.95 mV, above D2's 2.46.
- **Mesh 160 still overstates the margin, in all 67 subsample cases.** m160 − (Richardson extrapolation) runs from 0.11 to 0.57 mV.
- **All three pre-registered triggers fired:**
  1. m80 − m160 exceeded 0.359 mV in 6 of 67 cases, max 0.394. The max among cases with m160 in (−2, 3.5) mV is 0.374.
  2. The observed order fell below 0.7 in 4 of 67, min 0.47 (T24-S0.48). Some low-order cases sit inside the decision window: T5-S0.12 at 0.59, D-0158 at 0.57.
  3. 11 FEASIBLE labels had m160 between 0.62 and 0.727 mV.
- **No subsample case labelled FEASIBLE at 0.6 extrapolates below 0.** The lowest was D-0139: m160 0.623, extrapolated 0.405. T5-S0.12 (m160 0.846, extrapolated 0.53) is still safe. The safety target is a true margin ≥ 0, not ≥ 0.6, so 0.6 was not observed to fail. **But its derivation assumed a residual ≤ 0.359 and an order ≥ 0.7, and both assumptions are now false.** Per §7, it is not kept.

### 2. The re-derived parameters

The same formula as V2-01 §3: mesh 160's own error ≤ (m80 − m160)/(2^p − 1), at the lowest observed order and the largest decision-relevant residual.

- **c = 1/(2^0.47 − 1) = 2.60. Band = 2.60 × 0.374 = 0.97 mV, rounded up to 1.0 mV.** That covers the largest observed mesh-160 error (0.57) by 1.75×.
- **Window upper edge 3.5 → 4.5 mV.** The rule `m20-above-window` labels FEASIBLE from mesh 20 alone, so the edge must exceed the worst bias plus the band: 2.95 + 1.0 = 3.95. At 3.5, a case could reach a true margin of about −0.02 mV (3.5 − 2.95 − 0.57). Rounding to 4.5 keeps V2-01's ≥ 0.44 mV allowance for unsampled cases. **Cases with m20 in [3.5, 4.5) become `pending-m160` (UNRESOLVED) until they are solved.**
- **The lower edge stays at −1.97.** The bias was positive in 669 of 669 cases, and mesh 160's error is also positive. A case at or below −1.97 at mesh 20 is more negative at mesh 160 and more negative again in truth, so it can't be FEASIBLE.
- **The claim still holds only for |m20| < 15 mV.**

| m20 | Label | `rule` |
|---|---|---|
| ≥ +4.5 mV | FEASIBLE (mesh 20) | `m20-above-window-r1` |
| in (−1.97, +4.5) mV, re-solved | FEASIBLE if m160 ≥ 1.0 mV; INFEASIBLE if m160 < 0; otherwise UNRESOLVED | `m160-d3-r1` |
| in (−1.97, +4.5) mV, not yet re-solved | UNRESOLVED; never usable as FEASIBLE | `pending-m160-r1` |
| ≤ −1.97 mV | INFEASIBLE (mesh 20) | `m20-below-window` |

**The version name stays `battery-plating-ref-v2`.** Nothing was sealed at 0.6. V2-01 §7 makes re-derivation part of cutting v2, so v2 is defined by these sealed parameters. The rule IDs change (`-r1`) so D3's draft labels at 0.6 (`m160-d3`) can never be mistaken for sealed v2 labels. The draft labels at 0.6 stay as DEVELOPMENT evidence and are not sealed.

**What this does to D3's 669 cases** (counts from `labels.json`):
- FEASIBLE: 160 at 0.6 → **114** at 1.0;
- UNRESOLVED: 62 → **108**;
- INFEASIBLE: unchanged at **447**.

All five of D3's UNRESOLVED→FEASIBLE cases (m160 0.62–0.90) and all 11 below-floor cases return to UNRESOLVED.

### 3. New stop triggers (pre-registered for every later solve under v2)

v2 is re-derived again, never kept by default, if any of these happens:
- a new subsample case in the window has m80 − m160 > 0.374 mV;
- its observed order is < 0.47;
- its extrapolation is < 0 while m160 ≥ 1.0;
- a case newly solved in [3.5, 4.5) has m20 − m160 > 3.5 mV.

The 10 % mesh-80 subsample applies to the newly opened [3.5, 4.5) cases as it did to D3.

### 4. EV4 and the PDD development set under D4: specific annotations, never a re-score

**Count rows by the `source` field, never by the case-id prefix.** Every one of the 772 `case_id`s starts with `ev4:`, which is a naming artifact of the contract.
- The table has **772 rows**:
  - **669 decided** under `m160-d3-r1`: 611 PDD and 58 EV4;
  - **103 pending** under `pending-m160-r1`: 84 PDD and 19 EV4.
- The two sets are disjoint.

Transitions from the old 1.97 mV band to v2 (`-r1`). **This is the one audited pair:** `labels.json` `old_label` against `labels-v2-r1.json` `label`, joined on `case_id`. `labels.json` `new_label` (0.6 mV and 3.5 draft) and `labels-v2-r1.json` `draft_label` are other quantities, not this transition.

| source | F→F | F→I | F→U | U→I | U→U |
|---|---|---|---|---|---|
| EV4 (58) | 9 | **0** | 8 | 35 | 6 |
| PDD (611) | 105 | **5** | 54 | 407 | 40 |

- **The five known false-safe labels are all PDD development cases, not EV4:**
  - D-0073 (c1 = 1.75; c2 = 0.2, 0.4, 0.6): m20 2.243 → m160 −0.016, extrapolated about −0.3 to −0.45;
  - D-0109 (c1 = 1.25; c2 = 0.2, 0.4): m20 2.316 → m160 −0.335.
- **None of EV4's 58 re-solved cases is false-safe.** 8 of EV4's old FEASIBLE labels are UNRESOLVED under v2.
- **The annotations:**
  - every record or result that used a PDD development label for D-0073 or D-0109 (the score-lab and score-proof development inputs) names those five as known false-safe;
  - EV4's annotation names the 8 FEASIBLE→UNRESOLVED cases and states zero known false-safe;
  - EV5's sealed batch is never read, and it keeps the general optimism note only.
- Nothing is re-scored.
- **The D2 panel's "0 of 31 flipped" did not hold at scale** (5 of 669, all PDD). The OWNER-PLATING-REFERENCE-01 record gets an additive note saying so, because the owner's approval partly rested on it.

### 5. What waits on this record

- **Sealing v2 needs no new compute.** It waits only for Data Collection's relabel at `-r1` (with the count of EV4 cases in [3.5, 4.5), labelled `pending-m160-r1`) and the `v2_label` reader with tests over all four rules. Solving the pending cases later only adds decided labels, as a recorded relabel under the same rules.
- **Two alternatives considered and rejected:**
  - **A band of 1.2 mV** ("double the worst residual") is safe but ad hoc, and it drops 29 more labels than the registered formula.
  - **Keeping the edge at 3.5 on a local bias of 2.60** fails the registered test: 2.60 + 1.0 = 3.60 > 3.5. The bias isn't monotone in m20 either (max 3.18 at negative m20).
- **The CONFIRM-02 USD 37 and Track A's bank** stay held until v2 is sealed.

### 6. For the owner: the trade (not decided here)

- **A band of 1.0 mV is safe on the evidence but costs usable questions:** 46 fewer FEASIBLE labels in D3's set alone, and near-onset is where the buyer value is. Two ways to narrow it again later, each a new version going forward:
  - **(a) A convergence study at mesh 320** on the in-band cases, on a larger-memory pod. Mesh 160 used 6.3 GB, and mesh 320 ran out of memory on the earlier machine. The cost needs its own figure.
  - **(b) A Richardson-extrapolated reference** (meshes 80 and 160 per case). That changes the reference method, and at an observed order below 0.7 the extrapolation is itself uncertain.
- Until he chooses, 1.0 mV governs and fails closed.

**Not decided here:** the sealed bank's re-reference (the owner's); any deep-plating band; (a) or (b).

### 7. Sealing

- **Sealed on the merge of #1316** (head `b201dbe3e`). The sealed label file is `docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json`, sha256 `cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069`.
- **Inputs:** `labels.json` `dc1566085226710e…` and `records.jsonl` `ef8c6260b866a106…`.
- **Counts:** `m160-d3-r1`: 114 FEASIBLE, 447 INFEASIBLE, 108 UNRESOLVED; `pending-m160-r1`: 103 (84 PDD, 19 EV4).
- **Reader:** `scripts/dev/battery/plating_rereference.py:v2_label`, which exposes `V2_RULES`. A consumer of v2 labels must require `rule ∈ V2_RULES`.
- **Solving the 103 pending cases** is a later recorded relabel under the same rules and the §3 triggers. Data Collection's estimate is about 7 CPU-h, about USD 0.65 expected and USD 1.31 worst case, with a USD 2 cap. The figure goes to the owner via PR Head.
- **Sealing preconditions:** #1316 is merged; the D4 annotations (§4) and the additive note on OWNER-PLATING-REFERENCE-01 are on main. Sealing at 1.0 rests on V2-01 §7 and this record's re-derivation, which fails closed. It needs no further owner decision.
- **Narrowing is a separate future version (v3), not a condition on v2.** The sequence:
  1. **Richardson-extrapolated reference first.** That needs a mesh-80 solve per in-band case: D3 has 40/80/160 rungs only for its 67-case subsample. An extrapolated value carries its own band, derived from the observed spread of orders. At p < 0.7 the extrapolation is itself uncertain.
  2. **Mesh 320 on a larger-memory pod only if (1) can't close the band.**

  Adopting an extrapolated reference changes the reference method. That is the owner's, given in his own word in the session that records it. Each run's figure is also his.
