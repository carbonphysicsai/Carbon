# Graphite ladder wave, stage B plan (L2 and L3 on the dev-ladder)

**Status:** PLAN, ready to go to the owner the moment VALIDATOR-25 merges.
**Author:** Graphite Testing Manager. Dispatches nothing, authors no grant, spends nothing.
Parent: `GRAPHITE_LADDER_WAVE_PLAN.md` (#889). Stage A checklist:
`GRAPHITE_LADDER_STAGE_A_CHECKLIST.md`.

## 1. What VALIDATOR-25 is, and its status (checked 2026-10-09 against origin/main `8b19f012d`)

- **Status: NOT BUILT, no ticket and no PR found.** There is no `VALIDATOR-25` ticket under
  `.agent/tickets/`, no code mentioning `battery-dev-ladder` or `dev_ladder` on main, and no open
  or merged PR with that name. The Test Lead says the Carbon Validator is building it; that is
  the only source. Treat the status as unverified until a ticket or PR number exists.
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

1. **A deployment `battery-dev-ladder`** with its own root, journal, state, work and retained
   models, importing windows from the producer (it shares the main deployment's live windows
   with **one exposure account**, per the decision).
2. **A served-variants list.** It serves a development-only variant's recipe only when it says
   so, only for a level above its miner-facing level, always labelled DEVELOPMENT. Every other
   deployment keeps refusing variants (`development_variant_not_served`). L2 and L3 must be on
   the list; L4 stays refused until the owner and security owner accept (not stage B).
3. **A dedicated rehearsal hotkey.** The decision names `carbon-rehearsal-minerC` (the owner
   creates it), not minerA or minerB, because the chain allows one commitment per hotkey per
   tempo. **Open:** whether the owner-registered minerD-G UIDs 8 to 11 may also commit here.
   Stage B needs at least one hotkey per concurrent run; with one hotkey the L2 and L3
   confirmations are serial, one commit per tempo.
4. **A weights rule.** A `development_only` deployment never sets weights
   (`carbon/battery/deployment.py`). Whether the dev-ladder is one, or needs a new kind, is
   the Carbon Validator's design to bring to the owner. Stage B needs the answer, not a
   default.
5. **The Launchpad can send a variant's recipe there** (the amendment is in the decision) and
   the auto-confirm signer (#861, testnet-only) can commit for its hotkey(s).
6. **A way to read the hidden-path outcome and Q1 inputs** for confirmed candidates, so the
   level's value:score pair can be reported (V1 and V2 need a real-reference Q1 report per
   level).
7. **Controller designation** per level: an admission controller recorded for (battery, 2)
   and (battery, 3) (A4; only level 0 exists today and it is PENDING).

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

1. VALIDATOR-25 merged **and** deployed on valV2, with items 1 to 7 of section 2 answered.
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

- A VALIDATOR-25 ticket or PR number (none exists on main or in PRs today).
- Hotkey allowance for the minerD-G UIDs on the dev-ladder, and the weights-rule design.
- A4 designations for L2 and L3; V1 and V2 Q1 reports per level.
- Level 4 stays outside stage B (owner and security owner).
