# The design optimizer: scope before building

**Status.** Built and run once. This document is the scope record required
before building, kept unchanged below. OWNER-CHALLENGE-ADMISSION-01 (amended
2026-10-01) §5.4: "SCOPE IT AND REPORT BEFORE BUILDING. What it searches, over
what, under which constraints, at what cost per search, and what it cannot find."
Internal development evidence only (§2): not a qualification gate, not mainnet.

- **Built:** `carbon/battery/value/optimizer.py`, as EV4's Problem C: one
  two-step fast-charge protocol for 15-35 °C, with Mode D and Mode X.
- **Run once:** in EV4 on 2026-10-01, under its frozen pre-registration
  (`BATTERY_ENGINEERING_VALUE_EV4.md` §6 and §12). Results and findings are in
  `docs/development/evidence/ev4-2026-10-01/optimizer/`.
- **§2 superseded for that run:** it ran on RunPod A40 pods, not local CPU,
  under EV4's own cap.
- **§4 gaps:**
  - The Mode X verification budget (K = 50 per member) and the Mode X
    condition grid (t_amb 5-40 °C in 5 °C steps × soc0 {0.05, 0.20, 0.35,
    0.50}) were fixed by EV4's pre-registration, under the owner's
    delegation. Any other run needs its own.
  - Mode D ran as Problem C, not under EV3. EV3 is still a draft.
  - The PB-INV and PB-ADV policy values remain unset. The optimizer still
    passes or fails nothing; it reports.

**Why it exists.** "Customer inverse design **is** an adversary: it searches for
in-envelope inputs that break constraints" (`Design_Specs/Specialist_Bank.md`
line 135). It finds score-value divergence before a miner monetises it (Track A),
and it separates real winners from leaderboard winners: "this regime's winners
die on inverse design" (line 153; Track B). The product battery already names
both uses as gates PB-INV and PB-ADV (lines 124-125).

**First Challenge:** battery (`battery-fastcharge-ageing-development-v1`), the
only Challenge with a decision contract. Every quantity below is that
contract's (`carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json`,
digest `sha256:18770910…ce743`) or EV3's draft
(`docs/development/BATTERY_ENGINEERING_VALUE_EV3.md`), cited.

## 1. Two modes, one search engine

| | Mode D: design search (Track B, PB-INV) | Mode X: adversarial search (Track A, PB-ADV) |
|---|---|---|
| **Searches for** | the design the model believes is best | in-envelope inputs where the model's PASS call is wrong |
| **Over** | c1 ∈ [0.5, 2.0] C, c2 ∈ [0.2, 1.0] C (generator bounds; EV3 §2) at each fixed scenario condition | the same designs **and** the contract's operating envelope: t_amb 5-40 °C, soc0 0.05-0.5 (`operating_conditions.envelope`) |
| **Model's role** | predicts every grid design; the optimizer commits the lowest predicted objective among predicted-feasible designs, ties by lower c1 then c2, else abstains (EV3 §3) | predicts every point; the optimizer ranks predicted-feasible points by their smallest predicted constraint margin (closest to a limit first) |
| **Objective** | time to CV onset, minimised (contract `objective`) | none of its own: it orders points by the contract's constraint margins |
| **Constraints** | reach CV within the window; plating margin ≥ 0 V; peak temperature ≤ 45 °C (contract `constraints`) | the same three |
| **Verification** | pinned PyBaMM on every committed design and the top-3 (EV3 §4) | pinned PyBaMM on the top K points |
| **Emits** | design loss per condition (EV3 §4); feeds the progress measure (spec §4.0) | a verified false acceptance is a finding: `SCORE_VALUE_DIVERGENCE` when the model also scores high, otherwise `OTHER_SIGNAL` (`carbon.battery.value.divergence`) |

Grid, not a smarter search: model evaluations are cheap, so a dense grid
(31 × 33, c1 step 0.05, c2 step 0.025; EV3 §3) removes search luck and makes any
difference the model's.

## 2. Cost per search

Basis: EV1 measured about 65 s per pinned-PyBaMM reference solve with 4 workers
on this host's CPU (`BATTERY_ENGINEERING_VALUE_EV1.md`, run table); model
predictions take seconds.

| | Model predictions | Reference solves | CPU time (at 65 s/solve) |
|---|---|---|---|
| Mode D, one member, 16 conditions | 1,023 × 16 = 16,368 | at most 3 × 16 = 48 | about 52 CPU-min (about 13 min on 4 workers) |
| Mode D, EV3's panel of 15 | 245,520 | at most 720, deduplicated (EV3 §4) | about 13 CPU-h (about 3.3 h on 4 workers) |
| Mode X, one member | 1,023 × the condition grid | K per member | K × 65 s |

Money: USD 0 on local CPU, as EV1 and EV2 ran (OD-5 untouched).

## 3. What it cannot find

- **Anything outside the declared space.** Designs beyond the generator's
  two-step bounds, conditions outside the contract envelope, or outputs the
  contract does not constrain (for example ageing beyond 30 cycles).
- **Failures finer than the grid.** A violation between grid points
  (0.05 C × 0.025 C) is missed unless a verified neighbour also fails.
- **Failures the reference shares.** A common-mode error in the pinned solver
  looks like agreement. Reference refinement and witness checks are the defence
  (spec §4), not this optimizer.
- **Unresolved calls.** Where the reference's call falls inside the contract's
  uncertainty band (UNRESOLVED), neither mode can count a violation.
- **Construction attacks.** It measures a model's predictions, not the
  construction pipeline: hidden assets, leakage and sandbox escapes are Track A's
  other attack families.
- **Every exploit.** A search that finds nothing is not an exploit-free bound
  (spec §3).

## 4. Gaps: unspecified values, not invented here

| Gap | Where it would come from | Effect until set |
|---|---|---|
| PB-INV "constraint satisfaction rate ≥ policy" | `Specialist_Bank.md` line 124, "v1 policy; tune per regime" | Mode D reports rates and losses; it passes or fails nothing |
| PB-ADV "max found violation ≤ policy" | line 125, same | Mode X reports found violations; every verified false acceptance is a finding (when in doubt, fire) |
| PB-INV "fixed query budget" | line 124 | Mode D uses EV3's dense grid; any other budget needs its own pre-registration |
| K, the verification budget per Mode X search | none yet | Mode X cannot run until it is set and priced |
| The Mode X condition grid (resolution over t_amb × soc0) | none yet; an engineering choice, priced for approval | as above |
| EV3 itself | still a DRAFT pre-registration awaiting the owner's ranking of its candidate problems (EV3 §6) | Mode D does not count toward any study until EV3 is frozen |
| Problems A (80 % SOC) and D (ageing floor) | EV3 §6: need reference v2 SOC output and an owner-set capacity floor | out of scope for the first build |
| Other Challenges (cold plate, motor, photonics) | each needs its decision contract first | out of scope |

## 5. What building it would mean

One module that reads a frozen decision contract and a model's prediction
interface, runs Mode D or Mode X, writes the verification jobs for the truth
container, ingests the verified results and emits outcomes and conditions. It
reuses EV2's reference path and the divergence detector. It is built only after
this scope is reviewed, and it runs only under a pre-registration.
