# Graphite ladder wave, stage B plan (L2 and L3 on the dev-ladder)

**Status:** PLAN, ready to go to the owner the moment VALIDATOR-25 merges.
**Author:** Graphite Testing Manager. Dispatches nothing, authors no grant, spends nothing.
Parent: `GRAPHITE_LADDER_WAVE_PLAN.md` (#889). Stage A checklist:
`GRAPHITE_LADDER_STAGE_A_CHECKLIST.md`.

## 1. What VALIDATOR-25 is, and its status (checked 2026-10-09 against origin/main `8b19f012d`)

- **Status (updated 2026-10-09, per the Carbon Validator):** building, in PRs, not yet on
  main. The ticket is `.agent/tickets/VALIDATOR-25_development_ladder_deployment.md`, carried
  by **#895** (slice 1, admission) and **#899** (slice 2, door and daemon); operator steps are
  in `~carbon/shared/operator/LADDER_DEPLOYMENT_VALV2.md`. Both PRs were open when this
  was written. The ticket and operator file are not on main yet, so their content here is the
  Validator's statement, not something I read on main. Against the seven items below: 1, 2 and 4
  done; 3 pending the owner's record; 5 ladder side ready; 6 answered; 7 answered below.
- **Its definition** is a Test Lead statement recorded in OWNER-LADDER-THROUGH-LAUNCHPAD-01
  (2026-10-07): a separate testnet development-ladder deployment on valV2, `battery-dev-ladder`,
  never the main battery deployment, never mainnet until the owner locks a level.
- **What exists already:** construction levels in the Launchpad on both doors, built from data
  (LAUNCHPAD-LEVELS-01 S1, #789, merged); the development variants for L1 to L4
  (`reconstruction/development_variant_policies/`); battery attack adapters L0 to L4; Level 4
  graph-only code.

## 2. Exactly what stage B needs from VALIDATOR-25

Each line is something the Carbon Validator's deployment must provide, from the decision and the
variant rules. None is assumed to exist.

1. **DONE (#895/#899).** **A deployment `battery-dev-ladder`** with its own root, journal, state, work and retained
   models, importing windows from the producer (it shares the main deployment's live windows
   with **one exposure account**, per the decision).
2. **DONE.** `served_contracts` lists exactly the declared variants, labelled DEVELOPMENT; one door serves L1 to L3 and L4 stays refused. **A served-variants list.** It serves a development-only variant's recipe only when it says
   so, only for a level above its miner-facing level, always labelled DEVELOPMENT. Every other
   deployment keeps refusing variants (`development_variant_not_served`). L2 and L3 must be on
   the list; L4 stays refused until the owner and security owner accept (not stage B).
3. **DONE in the design; hotkeys are the owner's.** **Each hotkey is bound to exactly one
   deployment, enforced in code by the Validator (Test Lead, 2026-10-09).** The ladder's hotkeys
   are `carbon-rehearsal-minerC` (the decision's dedicated hotkey, which the owner creates) and,
   optionally, new minerH to K if the owner creates them. The owner-registered **minerD-G UIDs 8
   to 11 stay on main** (stage A's L0 confirmations) and never commit on the ladder; **there is no
   minerD-G ladder record, and this plan no longer waits for one.** The chain allows one
   commitment per hotkey per tempo, so the ladder's **confirmation capacity is its hotkey count**:
   with minerC alone, L2 and L3 confirmations are serial, one commit per tempo; with minerH to K,
   up to five per tempo.
4. **DONE** (OWNER-DEV-LADDER-KIND-01): a `ladder` sub-kind of `development_only`, never sets weights. **A weights rule.** A `development_only` deployment never sets weights
   (`carbon/battery/deployment.py`). Whether the dev-ladder is one, or needs a new kind, is
   the Carbon Validator's design to bring to the owner. Stage B needs the answer, not a
   default.
5. **Ladder side ready;** the Launchpad and the #861 signer belong to their owners. **The Launchpad can send a variant's recipe there** (the amendment is in the decision) and
   the auto-confirm signer (#861, testnet-only) can commit for its hotkey(s).
6. **ANSWERED:** outcome and score record come from the ladder operator surface (`operate status`, `score_record`); the Q1 inputs are the fields `readiness/Q1_PANELS.md` and `q1.py` consume. **A way to read the hidden-path outcome and Q1 inputs** for confirmed candidates, so the
   level's value:score pair can be reported (V1 and V2 need a real-reference Q1 report per
   level).
7. **ANSWERED:** the designation schema is `carbon/challenge_pipeline/admission_controllers.json` (`carbon.admission-controllers.v1`, #615; decisions GRAPHITE-ADMISSION-CONTROLLER-01 and A4-DEDICATED-ADMISSION-CONTROLLERS-01). **Controller designation** per level: an admission controller recorded for (battery, 2)
   and (battery, 3) (A4). Test Lead ruling 2026-10-09: battery L1 to L4 get dedicated
   zero-spend controllers, and the executor creates the L0 to L4 roots and identities after the
   WSL restart. A4 is therefore an executor-owned precondition, not an open blocker, and stays
   NOT passed until the entries are in `admission_controllers.json` on main.

## 3. Stage B's runs and price (from the parent plan, unchanged)

| | Runs | Worst case | With 0.25 cleanup |
|---|---|---|---|
| Constructor L2 x3, L3 x3 (kimi-k3, R4-style) | 6 x 14.91 = 89.46 | | |
| Attacker L2 x2, L3 x2 (kimi-k3) | 4 x 13.41 = 53.64 | | |
| **Stage B** | 6 Constructor, 4 Attacker | **143.10** | **143.35** |

Priced from the committed R4 (14.91) and PHASE4 (3.41) grant worst cases; the 13.41 Attacker
figure is the plan's assumption. Concurrency: up to 2, raised to 4 only after a host-load
check. Wall clock at the 11 h cap per run: 10 runs, serial 110 h; 2 at a time 55 h; 4 at a
time 33 h (upper bounds). Existing grants cover none of stage B: it needs R4-style grants for
L2 and L3 and the kimi-k3 Attacker share. The owner approves; the Test Engineer binds.

## 4. Entry conditions for stage B

1. VALIDATOR-25 slices (#895, #899) merged **and** deployed on valV2 (operator steps in LADDER_DEPLOYMENT_VALV2.md), plus the owner's valV2 ladder steps and the `levels` list slice. Nothing else: no minerD-G record is needed.
2. Stage A's L0 and L1 work has produced the level proposals' disposition (the ladder climb
   procedure: a drafted surface, development expansion record, Carbon's reconstruction, matched
   panels, single-permission ablations, combined-permission attacks, clean rebuilds).
3. Readiness items per level, run with `--level 2` and `--level 3` on a healthy host:
   the level-independent set (see the parent plan), plus A2 (adapters exist) and **A4 with a
   designated controller identity at each level**. NOT_BUILT items are decided by the Test
   Lead (build or waive by recorded decision), never silently passed.
4. The owner's stage B approval and the grants bound on main by the Test Engineer.
5. The same run discipline as stage A: fresh controller root per run, a written host window,
   no sealed host work, W2 (findings stop LOCK, not exploration), a lessons entry after each run.

## 5. What goes to the owner when VALIDATOR-25 merges

One page: the deployment's served-variants list and hotkeys (names only), the weights-rule
answer, the stage B figure (about 143.35 USD worst case, 10 runs), the wall-clock bounds, and
the open items below. This file is the source; nothing else is needed.

## 6. Open items

- #895 and #899 merging (VALIDATOR-25 slices 1 and 2).
- The owner's valV2 ladder steps, and the `levels` list slice. (The weights-rule design is
  settled; the minerD-G UIDs are not part of stage B.)
- A4 entries for L2 and L3 (executor-created identities, then recorded); V1 and V2 Q1
  reports per level.
- Level 4 stays outside stage B. **Level 4 permission is resolved** (owner, 2026-10-09, relayed by the Test Lead: "I approve level 4 runs. This is testing"; scope the testnet dev-ladder and the development door only, never main), but **its spend is not**: stage C (about 71.55 worst case, 71.80 with cleanup; `GRAPHITE_LADDER_WAVE_PLAN.md` section 4a) needs the owner's spend approval and, additionally, that the dev-ladder serve and label L4 DEVELOPMENT, an A4 designation for (battery, 4), a Q1 report per level, and a grant file that binds spend.

## 7. Stage B spend line for the owner (as of 2026-10-10)

**The ask:** approve stage B's spend, **about USD 143.35 worst case**, for L2 and L3 on the
dev-ladder. Nothing runs, and nothing is bound, until the prerequisites below hold and the
grant files are on main; the grant file binds spend, and this section authors none.

| | Runs | Worst case per run | Subtotal |
|---|---|---|---|
| Constructor, kimi-k3: L2 x3, L3 x3 | 6 | 14.91 (R4's committed worst case) | 89.46 |
| Attacker, kimi-k3: L2 x2, L3 x2 | 4 | 13.41 (stage A's Attacker worst case) | 53.64 |
| **Worst case** | 10 | | **143.10** |
| Cleanup allowance | | | 0.25 |
| **With cleanup** | | | **143.35** |

Arithmetic re-verified: 6 x 14.91 = 89.46; 4 x 13.41 = 53.64; 89.46 + 53.64 = 143.10; plus 0.25 =
143.35. **The 13.41 Attacker figure was an assumption in the parent plan; it is now the figure
the owner adopted in GRAPHITE-GRANT-STAGE-A-ATTACKER** (4 runs, ceiling 53.77, so no longer
unflagged-assumed, though it is still the stage A pricing reused for stage B). **Shape of the
grants:** stage A used one Constructor grant and one Attacker grant with the cleanup split 0.12 +
0.13. The same shape for stage B would be a Constructor ceiling of 89.58 (6 runs) and an Attacker
ceiling of 53.77 (4 runs), together 143.35, with Constructor runs capped at 39,600 s and Attacker
runs at 15,600 s as in stage A. That shape is a proposal for the Test Engineer's binding, not
authored here.

**Concurrency (peak simultaneous reservation):** at `max_concurrency` 2, up to 2 x 14.91 = 29.82
(two Constructors) or 28.32 (a Constructor and an Attacker); at 4, up to 4 x 14.91 = 59.64. Each
run keeps its own controller root, and each is capped on its own, so the ceilings above stand.
Worst-case wall clock from the runtime caps: serial 83.3 h (6 x 11 h + 4 x 4.33 h); at 2 at a time
about 41.7 h (Constructors 3 waves x 11 h = 33 h, then Attackers 2 waves x 4.33 h = 8.7 h). L2 and L3
confirmations additionally take the ladder's tempo-bound time (one commit per hotkey per tempo; minerC
alone is serial).

**Prerequisites, verified on origin/main (2026-10-10) unless noted:**

| Prerequisite | State |
|---|---|
| VALIDATOR-25 slice 1, admission (#895) | **merged** |
| VALIDATOR-25 slice 2, door and daemon (#899) | **merged** |
| The `levels` list slice | the ticket defines `ladder: {levels, hotkeys, variants}`; per the Test Lead the live door serves L0 plus L1 to L3; **not separately verified here** |
| valV2 ladder steps and the minerC lane | **live** per the Test Lead (door on valV2/r5, signer up); not verified from main |
| #902 (Launchpad levels) | **open** at the time of writing |
| A4 designations for L2 and L3 | **on main**: `admission_controllers.json` has (battery, 2) and (battery, 3) DESIGNATED with identities recorded |
| An L1 Q1 report from L1 exploration | **not yet**: only the Level 0 report exists (V1 and V2 fail at L1 until one is recorded) |
| Stage A's L0 and L1 results | stage A has not run; its gate waits on #907 |
| Grant files for stage B | **none yet**: stage A's two grants are on main; stage B's Constructor and Attacker grants are not |

**What the grant needs:** a Constructor grant and an Attacker grant (shape above, kimi-k3,
tokens plus the compute the stage A grants already include), each committed on main and bound by the
Test Engineer to the stage B route, with the per-run submission cap taken from the plan; the owner's
approval first. This plan authors neither file.

**Guardrails (unchanged):** L2 and L3 on the testnet dev-ladder and the development door only, never
main; hidden material never in an agent-visible output; a fresh controller root per run; stage B makes
no promotion, frontier or improvement claim.
