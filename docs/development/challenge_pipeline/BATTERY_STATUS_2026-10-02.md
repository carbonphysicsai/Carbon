# Battery status record, 2026-10-02

**Phase 1, step 1 of the Challenge Roadmap** (`Design_Specs/Challenge_Roadmap.md`),
ticket CHALLENGE-PROTOCOL-01.

The roadmap's statements about battery are dated 28 and 29 September. Each one
is reconciled here against the repository at `main`
`87c726d8ad70cd1147a4d2e1333ea042a1b07560` and GitHub, on 2026-10-02. Every
claim below names the file, PR or commit it rests on. Nothing here is a new
measurement, and nothing here is scientific, security or launch acceptance.

## 1. Contract and reference

| Item | State | Where |
| --- | --- | --- |
| Challenge and construction contract | `carbon.battery-fastcharge-ageing-development.v1`, version 1.0, recipe catalogue `carbon.battery-fastcharge-ageing-recipes.v1`, 400 TRAIN cases, full batching | `carbon/reconstruction/capability_registry.py` (`BATTERY_CONTRACT`) |
| Reconstruction backends | `jax` and `pytorch` (OWNER-PYTORCH-BACKEND-01). PyTorch is DEVELOPMENT-only until its reserved values are set. | `.agent/DECISIONS.md`, `.agent/tickets/RECON-TORCH-01_pytorch_backend.md` |
| Exam rule v1 (deciding) | `PROVISIONAL_DEVELOPMENT_NON_PAYING` (OD-2): screening batches of 100, 3 active, rotation after 3 admitted, relative equivalence margin 0.05699 | `carbon/battery/exam.py` (`DEVELOPMENT_RULE`) |
| Exam rule v2 (built, held) | v1 without the 3-admitted cap; one scored submission per hotkey per 360 blocks; rotation every 1,080 blocks. Merged in #452 (`a43fbbfebb48a7c7c11b747df1f2645b7cda7b7c`). Hidden-batch results are sealed from miners: #464 (`f1429b60ab20897c53cfadcc1ae19e248f48dd8e`). | `carbon/battery/exam.py` (`DEVELOPMENT_RULE_V2`); programme state row 19 |
| Reference | PyBaMM 26.8.0.0, DFN, OKane2022 parameter set, lumped thermal, IDAKLU solver (rtol 1e-5, atol 1e-7; refined 1e-6, 1e-8). The reference is the specified model, not a real cell. | `carbon/battery/reference.py`, `carbon/battery/truth.py` |
| Readiness record | `battery-fastcharge-ageing-development-v1` v3: `PROPOSED_DEVELOPMENT_DESIGN`, PROCEED, no limit approved | `carbon/challenge_readiness/records/battery-fastcharge-ageing-development-v1.v3.json` |

## 2. Engineering-value studies (Track B)

| Study | State | PR, head, merge | Evidence |
| --- | --- | --- | --- |
| **EV1**, fixed choice | **Complete.** Kendall τ for the approved rule: 0.341 on development, 0.165 on verification ("weak positive, indicative"). No verification scenario had a feasible protocol, so verification measures false acceptance only. The synthetic `boundary_optimist` control chose an infeasible protocol in 5 of 6 scenarios yet scored better than every reconstructed member (−0.046, against −0.051 to −0.171); with the controls included, the approved rule's τ falls to 0.000. | #352, head `4ccef255e7ec3bd69751ba3e4f62678e8ecaea07`, merge `9428c8c2f14eb718086c1e8bd23ac0a3e7f41103` | `docs/development/BATTERY_ENGINEERING_VALUE_EV1.md`, `docs/development/evidence/ev1-2026-09-25/` |
| **EV2**, boundary behavior | **Complete.** Pre-registered in `5f0756ad1301c005a9a3724ee9d330925d36805b`. H2 PASS: the decision-aware rule `dar-p0-r100-a0` scores the optimist below every one of the 14 eligible members, while under the current rule all 14 are at or below it. H1: the rule chosen on development scored τ 0.202 on verification, against 0.298 for the current rule, so it did not rank real models better. #458's audit caveat travels with these figures (OWNER-CHALLENGE-ADMISSION-01 §4.3). | #457, head `83639026324ca2e6fb0b21616853f516a5a4a8e2`, merge `50df50726cd119178c4eb7178836a79fccb567e8` | `docs/development/BATTERY_ENGINEERING_VALUE_EV2.md`, `docs/development/evidence/ev2-2026-10-01/` |
| **EV3**, design search | **Draft, never run.** Pre-registration draft for owner review (`9438ab86611d10f24a7652aa5299bcc338425b03`, landed with #457). It has no contract and no evidence. It waits for the owner to rank its candidate problems (programme state row 21). | not run | `docs/development/BATTERY_ENGINEERING_VALUE_EV3.md` |
| **EV4 and Problem C** | **Complete**, not named in the roadmap. EV4 used 99 eligible models. H1 is UNRESOLVED: Δτ (proposed − deciding) is −0.142, 95 % interval [−0.275, +0.121], against the deciding rule's τ of 0.403. H2 is confirmed: the proposed rule scores the optimist below all 99 eligible members. H3: 56 of 99 eligible members commit at least one reference-verified false acceptance. Problem C, taken from EV3's candidate list, ran the design optimizer for one fast-charge protocol over 15–35 °C. The deciding rule's best member chose c1 = 1.0 C, c2 = 0.7 C: 46 of 50 in-band points feasible, 0 infeasible, 4 unresolved. The conservative baseline fails 15 of 50. | #476, head `db5e5c382a4c0d7b65fa07bb963971afd01a1ee6`, merge `3807a75ef954ba77c59e56a8fd2b3bbd2627f0f4` | `docs/development/BATTERY_ENGINEERING_VALUE_EV4.md`, `docs/development/evidence/ev4-2026-10-01/` |
| Decision-aware rule | Registered as a prospective proposal. It decides nothing, and both rankings are reported. | #466, merge `22c4df8851cebfd44500d06993489ed1f4aa09ec` | OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01 |

## 3. Construction and threat work (Track A) and PR 458

- **#458 is shown as merged, but did not land as written.**
  - GitHub shows #458 MERGED at 2026-10-01T20:37:41Z, head
    `0e1e25c9b275e5e9902a69f53dbf9b92fa5b400a`. That is because #473's
    branch contained its head.
  - What landed is the split core, #473 (head
    `13d1bc32bb02740cc8fdb36bed494ed4eb0e83d8`, merge
    `aea352d38154bff5d7bfcad2d80f3374256e5392`): the admission protocol
    without the readiness gate.
  - The held remainder (readiness schema v3, the launch gate and
    `--require-admission`) is still open:
    - #477, head `c100bb295a343e22e751a855effe48f74f643f66`, held;
    - carried by #488, head `bf1ebd3e0a15d572da767cc007b8d911eb114677`.
  - Until they merge, the readiness gate is specified but not enforced
    (`.agent/tickets/CHALLENGE-ADMISSION-01.md`).
- **The trigger model's instruments are merged:**
  - score-value divergence detector: #470, merge
    `dc61a6e837a5a66f9147303624372ec1765117c7`;
  - construction expansion record: #468, merge
    `aadaf2331bc2658d02fdcc24328f089a5a5439b2`.
- **Adaptive exposure.**
  - The tier 3B leak ladder was pre-registered in #444 (merge
    `26b5ebefd6a145da0a9baf5619401680b6137c43`).
  - Its results are #472 (merge `7f13063b2c163e29b257413dfb5256dfea93e4f2`;
    `docs/development/BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`).

## 4. Current exam batch

- **The testnet runs exam rule v1 at pool version 3, which is open.**
  - The tier 3B ladder consumed the prepared screening batches `pscreen-T04`
    and `pscreen-T05`. No prepared screening batch is left, and 6 finals are
    open (`BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md` §9.3, §9.6).
  - Further v1 scoring needs new batches, and preparing them is the owner's
    call.
- **The batch identities and root commitments of the live deployment are
  not in the repository.** They are private by design, and this record does
  not need them.
- **Open PRs touching battery:**
  - #477 and #488 (above);
  - #492, battery practice on a Targon VM, head
    `96839067e5b1fbaa7634d967a91cdce0cf42b86a`;
  - #497, Control Center, which edits the programme state, head
    `3499b32a8aa0c936bc48874698fe3594ccab402c`.

## 5. The roadmap's dated statements, reconciled

| Roadmap (dated 28–29 Sept) | Repository on 2026-10-02 |
| --- | --- |
| PyBaMM DFN references | Confirmed (§1). |
| EV1 complete with weak positive ranking alignment | Confirmed: τ 0.165 on verification, "weak positive, indicative". |
| One boundary-optimist failure | Restated. `boundary_optimist` is a synthetic control, not a model. It exposes a scoring blind spot that EV2 and EV4 reproduced, and that the decision-aware proposal removes. |
| EV2 running | **Stale.** EV2 is complete (#457, merged 2026-10-01). |
| EV3 designed | Accurate. EV3 is still a draft and has not run. Its Problem C was run inside EV4. |
| (not stated) | **EV4 and Problem C are complete** (#476). |
| Construction and threat work around PR 458 | **Partly landed.** The core is merged in #473; the readiness gate is open in #477/#488. |

## 6. Inputs this gives the protocol (steps 2 and 3)

These are the starting materials for the suite. They are not a judgment
that any suite item is satisfied.
- **Track B.** EV1 (fixed choice), EV2 (boundary behavior) and a design
  optimizer run (EV4 Problem C) exist for battery under frozen
  pre-registrations. EV3 as the roadmap defines it (every model drives the
  same frozen optimizer, with reference-checked perturbations) has not run.
  The direct-solver, interpolation and reduced-order baselines of item 4 are
  not yet registered for battery.
- **Track A.** Existing instruments cover parts of these vectors:
  - admission (vector 1): the #473 protocol;
  - evidence integrity (vector 7): the divergence detector #470;
  - adaptive exposure (vector 8): the expansion record #468 and the tier 3B
    leak ladder #472.

  No artifact in the repository yet grades open findings critical, high,
  medium or low under a versioned suite.
- **Exam batches and sealed pool.** The battery exam has rotating screening
  batches and finals under rule v1, with a protected private pool. The
  roadmap's anchor set, disclosure budget and a sealed pool that never enters
  rotation are not yet registered as such.

## 7. Stale surfaces (follow-ups, outside this step)

- `docs/development/BATTERY_TESTNET_PROGRAMME_STATE.md`:
  - "Last updated" is 2026-10-01;
  - row 22 still shows EV4 as a draft.
  - The battery lane owns this file, and #497 also edits it.
- The battery readiness record v3: its `next_experiment` still names EV2.
- `docs/publications/PROJECT_STATUS.md` (28 September) mentions EV1 only.
