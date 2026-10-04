## 2026-10-04 — OWNER-GRAPHITE-TEST-WAVE-01: Graphite's three-challenge test wave (battery, cooling, motor) builds test suite v1

**Authority.** The owner, 2026-10-04, answering the Test Lead session's eight
open questions:

> 1. approve 2. that works but validator build needs to start soon and
> shouldn't be hard 3. Codex is doing those you just give me what you need
> and I'll communicate. 4 yes 5 your best decision here 6 your best decision
> here 7 approve 8 agree

Earlier the same day the owner set the wave's order: freeze cooling, audit
battery, bring motor to the cooling study's standard, then test Graphite on
all three before building the other five portfolio challenges
(OWNER-LAUNCH-PORTFOLIO-02). The owner also decided to build and use
Graphite's Attacker. That decision is recorded separately as
OWNER-GRAPHITE-ATTACKER-01, with the build.

Items 5 and 6 were delegated ("your best decision here"). Item 4's "yes" is
recorded here as a delegation too. The rules below for those items are the
Test Lead's working decisions under that delegation. The owner or the science
owner may supersede any of them by a new decision.

**Scope.** Internal DEVELOPMENT testing under Challenge Admission
(`Design_Specs/Challenge_Admission.md`, the combined run of
OWNER-ADMISSION-COMBINED-01). Nothing here is scientific, security, network or
production qualification. It creates no reward, weight or LIVE authority.

1. **The wave builds test suite v1 (item 8).** Running Graphite's combined
   admission tests on battery, cooling and motor is how Phase 1 step 3 of the
   challenge pipeline gets built and proven challenge-neutral: Track A attack
   vectors with severity rules, Track B EV1–EV3, exam rotation and the sealed
   pool. Cooling and motor do **not** enter the family queue through this
   work. The queue, the protocol state and battery's role as Phase 1's worked
   example are unchanged.

2. **The Attacker's live grant is approved (item 1).** The approved values,
   as the Test Engineer proposed them for `GRAPHITE-GRANT-PHASE4`:

   | Field | Value |
   | --- | --- |
   | Monetary ceiling | USD 10.50, including RunPod pod time |
   | Cleanup allowance | USD 0.25 |
   | Permitted runs | 3, one at a time |
   | Worst-case run cost | USD 3.41: six 30-minute A30 pods at USD 0.2464 (USD 1.48), plus USD 1.93 of tokens |
   | Maximum runtime | 15,600 s per run |

   The grant file is written with the Attacker build. No live run may start
   before both have merged and the dry run passes.

3. **Scoring during the wave is on Carbon's pods (item 2).** Graphite's
   constructions are scored against each challenge's frozen rule on Carbon's
   own pods. Protected material never enters a pod plan. A general validator
   build starts soon as its own ticket and runs alongside the wave. The owner
   expects it not to be hard. Deploying the battery validator service (the
   Launchpad production work list's submission endpoint) stays separate.

4. **Cooling and motor prep belongs to Codex (item 3).** The Test Lead states
   the entry criteria Graphite testing needs, and the owner relays them. The
   Test Lead does not prep challenges.

5. **The equal-budget rule for the solver comparison (item 4, delegated).**
   - **Money is the unit.** Track B arms are compared at equal decision
     budget in measured compute cost. A query count is not the unit, and no
     exchange rate between a solver run and a model query is set.
     - Cost is measured core- or GPU-seconds on each arm's recorded hardware,
       priced in USD at the approved rate for that hardware. The CPU reference
       timing route is `runpod-cpu5c-16vcpu`; pods use their grant's rate.
   - **What an arm is charged for.** Each arm is charged everything it spends
     to reach its committed proposal:
     - training-data generation (reference solves);
     - fitting, calibration and selection;
     - compilation and inference;
     - solver runs inside its search, including retries;
     - any fallback.
   - **Verification is charged to no arm.** Verifying committed proposals
     against the reference is the evaluation, so it is charged separately and
     identically for every arm.
   - **Cache.** The solver-in-the-loop arm uses a case-keyed cache. A hit is
     recorded and costs its lookup, not a solve. A cached case still counts as
     an evaluation, as in CHALLENGE-AI-COOLING-STUDY-02.
   - **Three views.** Every study reports three, each labelled:
     - equal cost, the deciding view;
     - equal query count, a diagnostic;
     - amortised: the number of decisions after which a model's one-time
       training cost undercuts the solver arm's per-decision cost. This is the
       break-even count, computed and never assumed.

6. **Motor's decision values for the DEVELOPMENT decision study (item 5,
   delegated).** These are synthetic study assumptions. They are not physical
   requirements, customer limits, gates or qualification thresholds, and they
   make no claim about a real robot joint.
   - **Feasibility, at every registered condition** (`carbon/motor/exam.py`
     `feasibility`):
     - period-mean torque **≥ 4.0 N·m**;
     - peak-to-peak ripple **≤ 0.30 × the mean**.
   - **Objective.** Among designs feasible at every condition, minimise the
     worst-condition ripple fraction (peak-to-peak over mean). Ties go to the
     higher worst-condition mean torque, then to the lower design ID.
   - **Conditions** follow cooling's four-plus-two shape. Peak current density
     is in A/mm²; current angle in degrees.
     - Representative: (8, 0°), (10, 0°), (12, 0°), (10, 15°).
     - Boundary-stress: (15, 0°), the deepest saturation in the box; and
       (12, 30°), field weakening.
     - The two groups are reported separately and never combined.
   - **Where the values come from.** The public TRAIN pool only
     (`docs/development/evidence/motor-pools-v1/train.jsonl`, 150 OK cases).
     For current density 8–12 A/mm², the median mean torque is 4.30 N·m and
     the median ripple fraction is 0.275; the 4.0 floor and 0.30 limit are
     those medians rounded. Among the 72 TRAIN cases at 8 A/mm² or more, 33
     meet both limits, 54 meet the torque floor and 40 the ripple limit, so
     both constraints bind. No private-pool case and no PRACTICE score was
     used.
   - **Rules for the design set.** Codex chooses the eight designs from the
     declared geometry box by a rule written down before any reference solve
     of them. The designs must be buildable under `carbon/motor/domain.py`'s
     validity rules. Neither designs nor conditions may be chosen by looking
     at reference results for the design set. If the frozen set turns out all
     feasible or all infeasible, the design set is revised under a new study
     version; the values above stay.

7. **A fresh confirmation set for battery's Graphite tests (item 6,
   delegated).**
   - **Role:** `graphite-confirmation-v1`. A distinct role is required:
     `make_batch` derives its key from the role, so reusing
     `ev5-confirmation` would regenerate EV5's sealed batch (journal
     sequence 14).
   - **Size and population:** 120 cases plus 4 hidden duplicates, drawn from
     the population of the Level 0 study sheet. That is the same size and
     population as EV5's set, so the two are comparable.
   - **Custody:**
     - sealed in the testnet validator deployment's seed journal under its
       writer lock;
     - never recorded in the testnet pool;
     - solved, and predicted on, only on the operator host (as
       OWNER-EV5-Q3-01);
     - never entered into a committed pod plan, rented compute, the attack
       knowledge store or any Graphite session.
   - **Overlap check:** before sealing, a check confirms no case equals an
     EV5 case.
   - **Commitment:** sealing prints only the public commitment, a fingerprint
     and a journal sequence.

8. **The two smoke-run fixes are approved (item 7).** One fix applies to
   campaigns that have a retained, unevaluated candidate: they settle as
   waiting for their miner rather than INTERRUPTED, with the campaign state
   asserted in the journey tests. The other normalises the literal string
   `"null"` to JSON null, only where null is valid (`kind=workspace`), under
   a new frozen normalisation rule so earlier campaigns replay unchanged.
   Both go in their own PR for PR Head.

**Unchanged.**
- EV5's frozen pre-registration, contract, panel and sealed batch.
- Battery's live construction contract and expansion records.
- The challenge registry, beyond the reservations Codex lifts through its
  own tickets.
- The readiness records.
- Every scoring rule, gate and tolerance.

No level above 0 is opened to miners.

**No execution.** This record dispatches, provisions and spends nothing.
