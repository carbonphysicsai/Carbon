# Graphite test wave: battery, cooling and motor (test matrix)

**Owner:** Test Lead session.

**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-01, -02 and -03;
- OWNER-GRAPHITE-ATTACKER-01;
- OWNER-GRAPHITE-PHASE3-REFUND-01;
- `Design_Specs/Challenge_Admission.md`, the combined run;
- `Design_Specs/Challenge_Roadmap.md`, the climb procedure and the common suite.

**Status:** PLAN, maintained as the wave runs. Results are added when they are
evidence. Nothing here is scientific, security or production qualification.

## 1. What the wave decides

The owner's stance (OWNER-GRAPHITE-TEST-WAVE-03):

> Max freedom, Max scoring alignment with value, and Minimum attack surfaces

Attack surface is something the test **measures**, not a precondition it
imposes. For each challenge and construction level, the wave produces one row
of a frontier:

| Column | Meaning |
|---|---|
| Freedom | The capability manifest served at that level (development variant above the miner contract) |
| Score-to-value | τ (Kendall, with its seed-noise band) and ρ (Spearman) between score and reference decision value; regret; false-feasible bound; top-k selection value |
| Attack surface | Verified findings per Track A family, split into **repaired**, **fixable (open)** and **no known fix** |
| Cost | Measured cost to a correct decision, at equal cost against solver and cheap baselines |

The owners choose each challenge's level from this frontier, which need not be
the highest (Challenge Roadmap).

Every level reports **three verdicts that never compensate for one another**:
construction integrity, adversarial score and engineering value.

## 2. Rules that stay fixed

These rules protect measurement validity. They do not restrict what
participants may try.

- No Graphite access to sealed or confirmation material:
  - EV5 journal sequence 14;
  - `graphite-confirmation-v1`;
  - motor's private pool;
  - cooling's six final conditions;
  - fresh confirmation sets to come.
- Grader, ledger and reference stay separate from what they grade.
- Participant code runs only under isolation the security owner has accepted.
  This is the Level 4–5 gate.
- Held-out controls, pinned knowledge-store snapshots, honest coverage. A
  timeout is never a pass. Zero findings means attempted coverage, never a
  bound.
- Test-side rules that encode an assumption are registered, versioned policies
  with their raw evidence kept, so the Attacker can test them:
  - pod-attribution-v1;
  - baseline-retry-v1;
  - conditional-evidence-v1;
  - repair-attestation-v1.

## 3. Readiness by component

Status uses `DONE` / `IN PR` / `BUILDING` / `TODO` / `BLOCKED (reason)`.

| Component | Battery | Cooling (chip-cold-plate) | Motor |
|---|---|---|---|
| Level 0 contract reachable in the Launchpad | DONE | DONE (#566) | IN PR (#579) |
| Validator scoring and adapter | DONE (VALIDATOR-01 #559/#573/#578) | BUILDING (Carbon Validator) | TODO, after #579 |
| Graphite Constructor at L0 (phase 3) | DONE, runs 4–5 under R2. Run 5 held for #580 | TODO, after scoring (executor gap list) | TODO, after scoring |
| Attacker engine and L0 adapter (phase 4) | DONE (#563); pre-live #569 | TODO (Test Engineer) | TODO (Test Engineer) |
| Phase-4 live-run gate (`phase4 prelive`) | PASS at 6806e522 | per challenge, once its adapter exists | per challenge |
| Development variants L1–L3 (W1) | BUILDING: foundation, then L1, L2, L3 | TODO, after L0 adapters | TODO |
| Findings stop LOCK, not exploration (W2) | IN PR (#577) | shared | shared |
| L4–L5 isolation | assessed (#576); the security owner gates execution | shared | shared |
| Decision study (fixed choice, finite comparator) | EV1/EV2/EV4 done; EV5 frozen, not run | DONE: 48-case counted CFD (#557) | counted GetDP campaign RUNNING (Data Collection) |
| Equal-cost design-search harness (Track B, EV3) | BUILDING (Data Collection) | BUILDING | BUILDING |
| Model panel for score-to-value | 100-recipe EV panel + controls | **too small:** analytic + KRR, all arms chose d03 | analytic + KRR |
| Constructed controls (attack constructions) | boundary optimist, sign error, always-abstain | false cooling optimism, hidden flow imbalance, under-predicted pressure drop, group sacrifice, out-of-regime Re | flat curve with correct mean, phase-shifted ripple, flipped period/orientation, saturation-blind linear iron, ripple-scale gaming |
| Fresh confirmation set (sealed, operator host) | `graphite-confirmation-v1` specified, not sealed | TODO: fresh conditions | TODO: fresh set (the private pool is already used) |
| Training-budget study | TODO | TODO | TODO |

## 4. Construction ladder per challenge

| Level | Adds | Battery | Cooling | Motor |
|---|---|---|---|---|
| 0 | Current recipe and registered operations | live contract | live contract | #579 |
| 1 | Bounded loss expressions | drafted surface, widened beyond GA-D6 to what Carbon rebuilds deterministically | draft after L0 | draft after L0 |
| 2 | Schedules, optimizers, TRAIN sampling | drafted surface (none proposed yet) | draft | draft |
| 3 | Training-time numerical routines | **declarative menu only** until isolation is accepted | same | same |
| 4 | New architectures behind a constrained inference interface | NOT_RUN: isolation gate | NOT_RUN | NOT_RUN |
| 5 | Custom inference in an isolated stage | NOT_RUN: isolation gate | NOT_RUN | NOT_RUN |

Every level above 0 follows the climb procedure:
1. a drafted surface, reviewed by the Test Lead and recorded as a versioned
   policy with its bounds;
2. a development expansion record;
3. Carbon's reconstruction for the level (the reconstruction rule);
4. valid and attack panels under the previous and expanded profiles;
5. single-permission ablations;
6. combined-permission attacks;
7. clean rebuilds of promising results.

An open finding blocks LOCK and opening to miners, not exploration. Results
are tagged `conditional_on`.

Each drafted surface comes to review with five items:
- the capabilities and bounds;
- the expected attack surface per Track A family, naming any vector believed
  unfixable;
- how Carbon rebuilds it, with bit-identity or tolerance evidence;
- the matched panels;
- the ablation and combined-permission plan.

## 5. Track A: attack checks

The eight shared checks (`carbon/challenge_readiness/admission.py`) run at
every implemented level, each with:
- an attack example that proves the detector can fire;
- trained and held-out valid controls, with the wrongful-rejection rate
  reported on held-out controls only.

| Check | Shared vectors |
|---|---|
| artifact and dependency | hidden assets, embedded weights, undeclared dependencies, loaders, malformed or nonfinite output, parser abuse |
| baseline and permission ablation | every new permission removed one at a time; combined-permission attacks |
| adaptive feedback and state | case or seed inference, repeated-query learning, collusion, leaderboard, error or timing feedback, near-duplicates |
| score exploitation and tail failures | scaling, averaging and denominator games, always-abstain or always-safe, boundary optimism, rare catastrophic errors, subgroup sacrifice |
| resource and failure accounting | overruns, **selective crash/retry abuse** (which tests pod-attribution-v1 and baseline-retry-v1), partial artifacts |
| construction–evaluation isolation | canaries, evaluator access, answer-key or log exfiltration, staged bytes |
| reconstruction and recipient rebuild | rebuild identity, ignored-field smuggling, delivery rebuild by a second operator |
| fresh attack confirmation | re-run of found attacks on fresh cases (needs the fresh confirmation sets) |

Challenge-specific vectors are in §3's "Constructed controls" row. The
Attacker (phase 4) is benchmarked against each challenge's deterministic
harness at an equal attempt budget (B2).

## 6. Track B: score to value

Three studies per challenge, at each level that reaches them:

1. **Fixed choice (EV1).** A diverse panel chooses from one finite candidate
   set, and every choice is reference-scored.
2. **Boundary behavior (EV2).** Near-limit and boundary-stress cases and
   flawed controls. It measures false-feasible decisions, missed feasible
   options and abstention.
3. **Design optimization against solvers (EV3).** This is the equal-cost
   harness (OWNER-GRAPHITE-TEST-WAVE-01 §5).
   - **Arms:**
     - solver-in-the-loop with a case-keyed cache;
     - cheap baselines (analytical, interpolation, random or Latin-hypercube
       search);
     - learned models (KRR now; Graphite constructions as they arrive).
   - **Methods:** registered search methods (fixed_grid,
     screen_then_confirm, coarse_to_fine).
   - **Custody:** every proposal is committed before any reference access.
   - **Equal measured cost.** Each arm is charged its data generation,
     fitting, inference, in-search solves and fallback. Verification is
     charged identically to every arm.
   - **Three views:** equal cost (deciding), equal query count (diagnostic)
     and the amortized break-even decision count.

**Score-to-value per level.** For every eligible panel member, take its
challenge score and its EV decision quality, then report:
- τ and ρ, with the seed-noise band (progress only beyond the band);
- `SCORE_VALUE_DIVERGENCE` conditions;
- top-k selection value;
- regret;
- the false-feasible one-sided bound.

Representative and boundary-stress groups stay separate. Gate-failing models
are reported but excluded from the primary ranking. Reference failure is never
a candidate penalty.

**Panel diversity is a known gap.** Cooling's counted study had two models,
and all four arms chose the same design, which cannot establish alignment
(Challenge Admission §4). Cooling and motor panels need Graphite Constructor
constructions plus the constructed controls. Cooling also needs a wider design
set or fresh conditions where models can disagree.

**Confirmation.** Each challenge's final evidence uses its fresh sealed set
once, after the panel, the score rule and the analysis are frozen, under
independent custody.

## 7. Entry gate for any live Graphite run

1. The run's code is merged on main, and the owner confirms the REF.
2. The real-path no-spend check passes at that REF: `phase4 prelive` for the
   Attacker, and `pods.real_path_check` with the phase-3 dry run for the
   Constructor.
3. The grant is bound to main's committed blob; runs are within the grant's
   permitted runs.
4. The operator host window is agreed between the Graphite Test executor and
   Data Collection.
5. A lessons entry after every execution. Step-9 reconcilers are clean before
   the next run.

## 8. Work queue (overnight 2026-10-04 → 05)

| Session | Work |
|---|---|
| Test Engineer | #580 run-4 fixes → W1 foundation (development variants) → L1 drafted surface for review → cooling and motor Attacker L0 adapters |
| Carbon Validator | cooling scoring and adapter → motor scoring and adapter (after #579) → explicit `--challenge` selection |
| Data Collection | counted motor campaign (import, evaluate, report) → equal-cost design-search harness (Track B, EV3), motor and cooling adapters |
| Graphite Test executor | no-spend: phase-4 live-run handoff draft, cooling Graphite readiness gaps, R2 run-5 checklist |
| PR Head | merge sequencing; holds named per PR |
| Codex (via owner) | motor Level 0 Launchpad (#579) |
| Test Lead | reviews (#577; each drafted surface; each adapter's families), this matrix, owner decisions |

## 9. Owner decisions pending

- Confirm the REF for R2 run 5, after #580.
- Phase-4 live runs: confirm the REF, and the executor's handoff.
- Cooling and motor: grants for Graphite Constructor and Attacker sessions on
  those challenges. The current grants are battery runs; new grants will be
  proposed with prices.
- Sizes and laws for the fresh confirmation sets of cooling and motor.
- The security owner's isolation acceptance before any Level 4–5 or code-based
  Level 3 execution.
- The training-budget study sheets (per challenge).
