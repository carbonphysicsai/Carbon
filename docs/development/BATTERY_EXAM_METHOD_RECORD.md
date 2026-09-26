# Battery: the exam-method and launch-readiness record

**Status.** Battery is a **launch Challenge** in the portfolio of battery,
electric motors, AI-chip cold plates and silicon photonics
(OWNER-LAUNCH-PORTFOLIO-01, `.agent/DECISIONS.md`, 2026-09-26). That decision
supersedes #341's exclusion of battery. This record is battery's baseline on the
way to launch:
- what its study established, and at what maturity;
- what it cost;
- what its method carries to the other three Challenges;
- its limits;
- what still stands between it and launch.

Portfolio membership is intent to launch, not a launch approval.
- Everything below is public, synthetic DEVELOPMENT evidence.
- Nothing is scientifically, security or production qualified.
- The OD-1 to OD-8 battery authorities are unchanged, including non-paying
  DEVELOPMENT status and Phase A all-burn only.

**How to read it.** Every figure carries its basis:
- **Verified** means recounted from the retained raw records for this record,
  and the command is given.
- **Relayed** means stated in an existing record and not independently rerun
  here.

The sources are:
- `EXAM_DESIGN_CAMPAIGN_RESULT.md` (the campaign, 2026-09-24/25);
- the evidence in `evidence/exam-design-2026-09-24/`;
- the five `BATTERY-TESTNET-*` tickets;
- `BATTERY_TESTNET_PROGRAMME_STATE.md`;
- EV1 (#352), which was **not merged** when this was written. Its figures are
  relayed from PR head `d2345239c`.

## 1. What the study established, and at what maturity

| Claim | Basis | Maturity |
|---|---|---|
| 2,604 main-run reference jobs, all `OK` | **Verified.** The status fields in `refs-a-part1`, `refs-a-part2` and `refs-b` `records.jsonl` count 12 + 1,004 + 1,588 = 2,604 `OK`, across 2,588 unique `case_id`s (the rest are refinement pairs). The `DONE.json` files for part2 and refs-b agree (0 failed, 0 timed out). | Reference **execution** is tested. It agrees with the specified PyBaMM DFN model only, not with real cells. |
| All 7 pre-registered verification criteria passed on 200 fresh private cases after the freeze | **Verified.** `verification.json` records `pass: true` for V1 to V7, with `n_cases` 200, bound to `freeze.json`. | Tested for this campaign's scripted candidates. It is not a false-promotion rate (§3). |
| The fresh finalist comparison stops screening memorization | **Relayed** (RESULT §4). Memorizing candidates were nominated 27/27 and promoted 0/27, across 9 replayed settings. | Scripted attackers only. Adaptive miners were not measured. |
| Every authored fault is rejected by its own gate, and correct plating or hot predictions are never failed | **Relayed** (RESULT §3). | Tested. Two gates pass by construction (§3). |
| The CPU and GPU backends reach the same exam decisions | **Partly verified.** `backend_comparison.json` records identical decisions for V1, V3, V4, V5 and R1. It does **not** record V2, V6 or V7, so RESULT's "every frozen verification decision is identical" is backed for 5 of 8 entries. It records bit-identical same-seed repeats on each backend and non-identical CPU/GPU bytes. | Supplementary. The frozen results themselves ran on the CPU backend by accident. |
| Screening rank predicts fresh-case rank | **Relayed** (RESULT §4): Kendall τ 0.93 at batch 100, across 16 trained models. | Development evidence, for this model family. |
| Error scores can rank a dangerous model highly | **Relayed from EV1** (#352, unmerged, §5.2 Finding 2): a synthetic `boundary_optimist` picks an infeasible design in 5 of 6 scenarios yet outscores every reconstructed model under the approved rule. | Indicative: small panel, one synthetic control. |
| The approved rule weakly prefers models that decide better | **Relayed from EV1** (§5.2): τ 0.165 on verification, and no reweighting beats it. | Indicative, not established. The verification split measures only false acceptance (EV1 Finding 1). |

**Discrepancies found while verifying**, recorded rather than resolved:
- The M2 ticket says "2,600 retained cases", which matches neither 2,604 nor
  2,588.
- `refs-a-part1` has no `DONE.json`. Its 12 records were salvaged from a
  stopped run.
- The pilot runs are outside the main count. `pilot-battery-v1` had 4
  `FAILED_INFRA` of 16.

## 2. What it cost

- **Pod time: USD 4.78, verified.** The 12 pods have `created` and
  `terminated_verified` events in `accounting/ledger.jsonl`, all at USD
  0.49/h. Adding the USD 0.011 connectivity test gives USD 4.79.
- **The billed figure of USD 4.80 is relayed.** The ledger records no billed
  amount; that figure appears only in the RESULT prose.
- **All 12 pods are recorded as terminated and verified.**
- **About USD 0.23 of it produced nothing**: three pods were discarded
  outright (relayed).
- **EV1 cost USD 0**: its 384 references ran locally (relayed).
- **The M1 to M5A engineering** cost no RunPod or model-provider money (host
  handoff §4, relayed).

Per-unit costs, all relayed (RESULT §7, one A40 pod):

| Item | Cost |
|---|---|
| A 30-cycle reference | USD 0.0014 per case |
| Screening one submission | about USD 0.001 on the GPU backend |
| A finalist comparison | about USD 0.29, dominated by the fresh references |

## 3. What the method carries to another domain

The battery physics is not the durable asset. The method is. These are the
parts the motor, cold-plate and photonic exams can reuse, each
with where it lives.

1. **Construction contract per Challenge (M1, OD-8).** A candidate declares
   what it builds against a versioned, digest-pinned contract. Research-only
   families are labelled as such, not silently admitted.
2. **Separate truth, seed and exam services (M2).**
   - The reference solver, the private seed root and the scoring rule are
     separate components, each with its own identity.
   - Private cases derive from a committed root.
   - The root is revealed only after every dependent use closes, and must
     re-derive the cases.
3. **Freeze, then verify, then publish.**
   - Rule, criteria and code digests are frozen before the verification set
     is opened.
   - The set is read once.
   - The campaign got this order wrong by one minute: private references
     were committed before the freeze. The deviation is disclosed (RESULT §4)
     and the order is fixed.
4. **The fresh finalist comparison is the safety mechanism, not screening.**
   Screening ranks well but is fooled by memorization. Only a comparison on
   fresh private cases made promotion safe.
5. **Admissibility before ranking.** Mandatory gates run on the full batch and
   cannot be offset by a good soft score.
   - The trained `mlp_raw` looked competitive (0.058) while predicting
     impossible voltages, and the gate stopped it.
   - EV1 Finding 3 is the same behaviour, working as intended.
6. **Typed failures.** `FAILED_INFRA`, solver failure and timeout are kept
   apart from candidate failure, and reference failures are never charged to
   a candidate.
7. **Backend identity is part of the result.** Same decisions do not imply
   the same bytes. A validator must pin and record the backend.
8. **Hidden duplicates in every private set.** Nondeterminism is only
   checkable where duplicates exist.
9. **The validator daemon (M3), the truth environment and host tooling
   (M4P), and challenge discovery through MCP (M5A).** These are the
   operator-side machinery. It is Challenge-agnostic in shape and
   battery-specific in content.
10. **OD-4a dispatch discipline.** One numbered, digest-approved request per
    publication:
    - fee and spend fixed at 0;
    - a block window anchored to a fresh read-only runtime probe;
    - `authorizes_dispatch: false` until the owner approves that exact digest.

    Approval is of a specific artifact, never of a class of actions.

## 4. The method's limits

### Where it would have rewarded the wrong thing

- **Small errors near a constraint boundary.**
  - An error-based score cannot tell a model that is slightly wrong in a safe
    direction from one that is slightly wrong across a constraint boundary.
    EV1's `boundary_optimist` outscored every real model while choosing
    infeasible designs.
  - Any domain with hard engineering constraints (cold-plate peak
    temperature, motor winding temperature) inherits this blind spot unless the
    score is made decision-aware.
- **Screening alone rewards memorization.** It nominated every pool-leak
  candidate. Without the fresh finalist stage, the exam would have promoted
  them.
- **Protocol-control gates pass by construction.** The voltage gates are
  satisfied through a declared construction choice (a soft ceiling head).
  Passing them is not physics evidence, and a reader could mistake it for
  one.

### What it could not measure

- **Adaptive miners.** The harness exists (`adaptive_agent.py`) but was never
  run without a model-provider budget.
- **Rare false-promotion rates.** Zero false promotions in 28 relevant finals
  gives an upper 95 % bound of about 11 %, for scripted candidates only.
- **Real cells.** All agreement is with the specified PyBaMM model.
- **The physics of the plating margin.** Its sign is scored, not gated.
- **Charge conservation.** Current is not an output.
- **Improvements near the margin.** Improvements at about 1× the 5.7 %
  margin were found about half the time. That is the margin's price, not a
  measured detection power for other domains.
- **Reference uncertainty for plating.** Score differences below about 0.015
  case error sit inside it.

### Choices that were expedient rather than principled

- **The equivalence margin.** It is 2 × the largest seed-to-seed SD from
  three seeds. Three seeds are diagnostic, not a reliability estimate.
- **The batch=100 / rotate-after-3 / 5.7 % settings.** They are
  battery-specific, and the rotation choice is conservative for adaptive
  agents that were never measured. #341 and #347 both say not to import them
  as defaults, and this record agrees.
- **The CPU backend.** The frozen results ran on it because the image selects
  CPU unless `JAX_PLATFORMS` is set. That was found late, not chosen.
- **The private root.** It lived in a container home directory rather than an
  official seed service.
- **Execution containment.** It came from the provider's runtime, not
  `validator_launch`. The isolation acceptance is still owed.
- **Traffic assumptions.** The 30-cycle horizon, the fee estimates and the
  rotation-to-time conversion rest on assumed traffic, not measurement.

## 5. What remains unexperimented

"Fully experimented" is **not** reached from where the study stopped. Now that
battery is a launch Challenge, the items below are its launch-readiness
queue, together with the launch gates in RESULT §11. The cost estimates are relayed where a
record gives one and marked unknown where none does.

| Missing | Why it matters | Cost basis |
|---|---|---|
| Adaptive-agent campaign | The main threat model, and unmeasured | Needs an owner model-provider budget. The programme's is USD 6, unspent. Unknown per campaign. |
| Decision-aware robustness score, tested against `boundary_optimist` | Closes the blind spot in §4 | Relayed as designed in EV1 §8. Local compute, USD 0 at EV1's scale. |
| EV2 with a design set feasible in every scenario | EV1 could not exercise regret on its verification split | Relayed as proposed in EV1 §8. Scale not yet stated. |
| Time-to-SOC output | The engineering objective EV1 could not measure | Relayed (EV1 §7): a new reference version and about 1,200 re-solves at about 70 s each. |
| Validator isolation (`validator_launch`) and an official seed service | Required before any reward-bearing use | Engineering work, not costed. |
| A GPU-backend run of the frozen pipeline, and M3 on a GPU host | The frozen results are CPU-backend | Part of the programme's M4 two-host run (USD 14 RunPod ceiling, unspent). |
| Hidden duplicates in the verification set | V2's nondeterminism check fired only incidentally | Cheap: a set-design change. |

**EV continues.** EV1 (#352) and its proposed EV2 are part of battery's
launch path (OWNER-LAUNCH-PORTFOLIO-01). The decision-aware robustness score
is the most important of them, because it closes the one blind spot in §4
that could reward a dangerous model.

## 6. What this record does not do

- It does not rerun any reference, reconstruction or verification.
- It does not rescore or reinterpret any frozen result.
- It does not set a threshold, margin or tolerance for any other Challenge.
- Every number in it is battery's, measured under battery's contract.
