# EV3: does the score predict good designs? (pre-registration DRAFT)

**Status.** DRAFT for owner review, 2026-09-29.
- It is frozen, with a contract digest, **before any EV3 solve**, and only
  after EV2's results are recorded.
- Nothing here has run.

**Authority.** The owner approved, on 2026-09-29:
- Carbon supplies the optimizer;
- the first case is the continuous two-step charging design;
- the owner and Carbon choose the higher-value design competitions together
  (§6).

**Scope.** Public synthetic DEVELOPMENT evidence only:
- no chain action, reward or spend;
- no change to the testnet rule;
- no qualification claim.

## 1. The question

EV1 and EV2 ask whether the score agrees with *decisions made from a fixed
menu*. EV3 asks the question a design competition depends on: **when each
model drives the same design optimizer, do higher-scoring models produce
better verified designs?**

This is also the harness that will later run on real competition winners.

## 2. The design problem (first case)

- **Design space:** a continuous two-step constant-current protocol, with
  c1 ∈ [0.5, 2.0] C and c2 ∈ [0.2, 1.0] C. These are the generator's bounds.
- **Conditions:** EV2's 16, with the same development/verification split.
  One design per condition.
- **Objective, constraints, bands, costs, baseline:** EV2's, unchanged. They
  are:
  - time to CV onset;
  - plating margin ≥ 0 V;
  - peak temperature ≤ 45 °C;
  - reaching CV within the window;
  - false acceptance 10, missed opportunity 1, regret 1 per 120 s.

## 3. The optimizer (Carbon-supplied, identical for every model)

- **How it searches.** It is a deterministic dense search. For each condition,
  the model predicts every design on a grid of 31 × 33 points (c1 step 0.05,
  c2 step 0.025).
- **What it commits.** The optimizer commits the design with the lowest
  predicted objective among those the model predicts feasible, with ties
  broken by lower c1, then c2. If none is predicted feasible, it abstains.
- **Why a grid, not a smarter search:**
  - model evaluations are cheap, so a dense grid removes search luck;
  - any difference between models is then the model's, not the optimizer's.
- **Top-3 shortlist.** The optimizer also records a diverse top-3, three
  predicted-feasible designs at least 0.1 C apart in c1 or c2, for the
  secondary outcome.

## 4. Outcomes and verification

**Verification.** PyBaMM, pinned as in EV2, verifies every committed design
and every top-3 design. That is at most 15 members × 16 conditions × 3 =
720 solves, deduplicated.

**Primary outcome: design loss of the committed design, per condition.**
- **Verified FEASIBLE:** regret against the best known verified design for
  that condition, in units of 120 s.
- **Verified INFEASIBLE:** 10.
- **Abstained while a feasible design is known:** 1.
- **UNRESOLVED or unavailable:** excluded, not scored, as in EV1 and EV2.

**How "best known" is defined.** It is the best reference-FEASIBLE design
among:
- EV2's 35 verified grid designs;
- every model's verified proposals.

It is **not** a global optimum, and the report says so.

**Secondary outcome: best of the top-3 after verification.** This is the
design loss if the designer may verify three designs and keep the best. It
represents a model plus a small verification loop.

**Controls.** EV2's synthetic controls are not used. They are built from
reference outputs, which do not exist at arbitrary grid points. So EV3
compares reconstructed models only.

## 5. Hypothesis and reporting

- **H3 (primary).** Kendall τ, on the verification conditions, between two
  rankings of the reconstructed members:
  - the ranking by the EV2 development-chosen rule's score;
  - the ranking by mean committed-design loss.

  Every EV1 and EV2 rule's τ, and the secondary outcome, are reported beside
  it. No significance claim is made at this panel size.
- **Also reported:**
  - each model's rate of unsafe committed designs;
  - the gap between its best design and the best known;
  - whether the rule EV2 favours also favours the best designers.
- **Neither outcome changes the testnet rule.**

## 6. For owner review: which design competitions are most valuable

This first case is chosen because it is buildable now. These candidates are
for us to rank together; each gets its own pre-registration.

| # | Design problem | Why it matters to an engineer | What it needs first |
|---|---|---|---|
| A | **Fast charge to 80% state of charge** under plating and temperature limits | The real fast-charge question: how fast to 80% without damaging the cell | Reference v2 with a state-of-charge trajectory (programme-state item 13) |
| B | **Multi-step or tapered charge profiles** (3–5 steps) | Industry protocols are multi-step; this tests models off the two-step grid they were trained on | A wider design space and generator, and new TRAIN coverage |
| C | **Charge protocol robust across ambient temperatures** (one protocol for 5–40 °C) | A single protocol that is safe year-round is a common product constraint | Nothing new: the EV1-style worst-case decision over the continuous space |
| D | **Ageing-aware charging:** fastest protocol keeping 30-cycle capacity above a floor | It trades speed against lifetime, a core battery design trade-off | The capacity output exists; needs an owner-set capacity floor |
| E | **Cold-plate channel geometry**, **motor geometry**, **photonic component geometry** | The rest of the launch portfolio | Each needs its challenge, reference and construction contract first |

**Suggested order:** C (no new build), then A, then D, then B, then E as each
challenge becomes ready.
