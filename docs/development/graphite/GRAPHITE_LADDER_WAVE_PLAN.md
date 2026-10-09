# Graphite ladder wave plan: kimi-k3 at every level (battery, L0 to L4)

**Status:** PLAN for Test Lead review, 2026-10-09. **Author:** Graphite Testing
Manager. Dispatches nothing, authors no grant, spends nothing, runs no WSL job (the
host is unhealthy). **Owner priority (relayed by the Test Lead):** "kimi-k3 graphite
hammering at this challenge at every level", mainnet-adjacent, real scores for
value:score. Everything here is DEVELOPMENT evidence: no qualification, LIVE, reward or
production claim; the owner locks any level.

Challenge: battery (`battery-fastcharge-ageing-development-v1`), the only challenge with
attack adapters and development variants at L1 to L4. Cooling and motor are L0 only and are
out of this wave.

## 0. What is verified on main, and what is not

Checked against origin/main `8b19f012d` (2026-10-09).

| Fact | State | Evidence |
|---|---|---|
| kimi-k3 is wired as the top Engy ladder rung | VERIFIED | `development_session/model_provider.py` `ENGY_LADDER`; D34/D35 full-window figures (1,048,576-token window, 2.0646912 USD reserved per full call) |
| Constructor starts on kimi-k3 at Level 1 and above | VERIFIED | OWNER-GRAPHITE-PHASE3-R4-01; `grant_binding.PHASE3_GRANTS`: R4 is bound to battery, Level 1 and above, start model kimi-k3; a Level 0 run under R4 is refused (`grant_requires_construction_level_1_or_above`) |
| A Constructor at **Level 0 on kimi-k3** is possible | NOT AVAILABLE | R4 refuses Level 0; Level 0 keeps the cheap start rung. A Level 0 kimi-k3 run needs a new binding and grant (section 6) |
| An Attacker on kimi-k3 | NOT AVAILABLE under today's grant | D35: one kimi-k3 call reserves more than GRAPHITE-GRANT-PHASE4's token share, so an Attacker session stops before its first call. A larger token share is a grant value, the owner's |
| Battery attack adapters at L0, L1, L2, L3, L4 | VERIFIED | `attack/adapters/__init__.py` `BUILTIN` (battery_level1 to battery_level4) |
| Development variants L1 to L4 | VERIFIED (policies) | `reconstruction/development_variant_policies/`: l1 loss expressions, l2 spectral/v2, l3 numerics, l4 graph v1/v2. Levels 4 and 5 stay refused by the variant registry until the security owner accepts isolation (LEVEL4 decisions); **whether a Level 4 live run is permitted is the owner's and the security owner's, not assumed here** |
| Auto-confirm signer (#861) | VERIFIED | merged: SIGNER-AUTOCONFIRM-01, opt-in, testnet-only |
| Development door (`battery/dev_submit.py`) | VERIFIED | OWNER-LADDER-THROUGH-LAUNCHPAD-01 |
| The Launchpad `minerD-G` lane, UIDs 8 to 11, one commit per tempo each | **OWNER-REGISTERED; chain check after the WSL restart** | the owner created and registered them on 2026-10-08 (Test Lead, relayed). Nothing on main names them, by design: no account or address detail is in the repo. They are verified with Carbon's reader once the WSL host is back. The commit-per-hotkey-per-tempo rule is verified (OWNER-COMMITMENT-POSTER-01 D4) |
| VALIDATOR-25 `battery-dev-ladder` deployment | **UNVERIFIED / NOT BUILT** | decision records its design (rehearsal hotkey `carbon-rehearsal-minerC`); no code or deployment on main; "building now" is the Test Lead's statement |
| The Level 1 hidden-path check, owner's score-variant pick, Level 0 run 3 on the same variant | **UNVERIFIED** | R4's entry conditions, recorded as conditions only, not wired |

## 1. The wave

**Roles.** For each level L in 0..4 (battery):
- **Constructor:** a Graphite phase-3 session on kimi-k3 that builds recipes inside that
  level's development variant (Level 0: the current contract).
- **Attacker:** a phase-4 session against that level's adapter (`BUILTIN` key `(battery, L)`).

**Two routes, in this order per level (OWNER-LADDER-THROUGH-LAUNCHPAD-01):**
1. **Explore on the development door.** Fast rebuilds through `battery/dev_submit.py`;
   Graphite's internal hidden route (VALIDATOR-13) as the evidence path. Attacks also run
   here. Nothing here counts as a level passing.
2. **Confirm the best candidates through the Launchpad.** A few real freeze, commit,
   submit, verdict runs per level with the auto-confirm signer. **Each hotkey is bound to
   exactly one deployment (enforced in code by the Validator).** The **minerD-G lane** (UIDs 8
   to 11, one commit per tempo each, so up to 4 confirmations per tempo) stays on **main** and
   serves **L0 confirmations only**. L1 to L4 confirm on the dev-ladder with its own hotkeys:
   `carbon-rehearsal-minerC`, plus new minerH to K if the owner creates them (optional). A level is "passed through the Launchpad" only when these runs pass
   (OWNER-LADDER-THROUGH-LAUNCHPAD-01 item 3).

**Deployments.**
- **L0: the main battery deployment** is the only level that confirms on main today (Test
  Lead, 2026-10-09). L1 is a development variant, so L1 confirms on the dev-ladder like L2 to L4.
- **L1 to L4: the dev-ladder deployment** (VALIDATOR-25), never mainnet until the owner locks
  a level. Its hotkeys are the dedicated rehearsal hotkey `carbon-rehearsal-minerC` and, if the
  owner creates them, minerH to K; the minerD-G UIDs 8 to 11 are bound to main and never commit
  on the ladder (Test Lead, 2026-10-09; there is no minerD-G ladder record). **L1 to L4 confirmation is
  blocked on VALIDATOR-25 being built.** (L1 exploration on the development door and the
  Constructor and Attacker runs do not wait for it.)
- Development variants are served only by the dev-ladder deployment (the decision's
  amendment), which is why L1 to L4 confirm there.

**Sequence (each step needs the previous level's entry conditions, section 5):**

| Step | Level | Deployment | Constructor | Attacker |
|---|---|---|---|---|
| 1 | L0 | main (confirmation); dev door (exploration) | kimi-k3 (needs a Level 0 binding, section 6) | kimi-k3 (needs a larger token share) |
| 2 | L1 | dev-ladder (confirmation); dev door (exploration) | kimi-k3 under R4 (exists) | kimi-k3 |
| 3 | L2 | dev-ladder | kimi-k3 | kimi-k3 |
| 4 | L3 | dev-ladder | kimi-k3 | kimi-k3 |
| 5 | L4 | dev-ladder | kimi-k3, graph-only | kimi-k3; the owner and security owner decide whether it runs |

A level's explore phase may overlap the previous level's confirmation phase; two levels never
share a controller root (one controller root per run; the W2 rule that an open finding blocks
LOCK, not exploration, applies per level).

## 2. What "real scores for value:score" needs

Each level reports the three verdicts that never compensate (construction integrity,
adversarial score, engineering value). The value:score pair for a level is the hidden-path
score of its confirmed candidates (main or dev-ladder deployment) against the decision value
(Q1/Track B). Q1 reports follow the readiness gate's V1 rules: a report built from
real-solver references only. **UNVERIFIED:** whether a battery Q1 report exists for each level;
none is recorded under `readiness/` today (V1 and V2 fail everywhere in the first baseline).

## 3. Controls

Honest rate and no hidden leakage rules from the rate study apply unchanged to any
agent-visible output; the agent sees only the mainnet allow-list on every hidden route.
Findings stop LOCK, not exploration. Each run follows the OWNER-GRAPHITE-TEST-WAVE-05 section 3
checklist, in a fresh controller root, with a lessons entry after it.

## 4. Grant PROPOSAL (not authored; the owner approves, the grant file binds spend)

Public repo: caps and rates only. Per-run worst cases come from the committed grants, not from
any spend ledger. The executor's private ledgers (phase-3 R2 to R4) hold actual per-run
costs; they are **not** in this repo, so this proposal prices at the **grant worst case** and
the Test Lead or executor can tighten it from actuals.

Basis (all verified in the committed files and decisions):
- R4 Constructor run: worst case **14.91 USD** (10.00 model + 4.91 compute-inclusive), 11.93
  token share, 5 full kimi-k3 reservations in it; runtime cap 39,600 s.
- Attacker run (PHASE4): worst case **3.41 USD** at the cheap model; a full kimi-k3 reservation
  is 2.0647 USD, so a kimi-k3 Attacker needs a token share of at least N x 2.0647 for N full
  calls. **Assumption:** priced like R4's model share, 10.00 (4 full reservations) plus the
  3.41 PHASE4 worst case = **13.41 USD per Attacker run**.

| Stage | Runs | Worst case | Stage ceiling (+0.25 cleanup) |
|---|---|---|---|
| A: L0 and L1 (L0 confirms on main, L1 on the dev-ladder) | Constructor L0 x2, L1 x3 (R4 exists for L1) = 5 x 14.91 = 74.55; Attacker L0 x2, L1 x2 = 4 x 13.41 = 53.64 | 128.19 | 128.44 |
| B: L2 and L3 (dev-ladder) | Constructor 2 levels x 3 = 6 x 14.91 = 89.46; Attacker 2 x 2 x 13.41 = 53.64 | 143.10 | 143.35 |
| C: L4 (graph-only) | Constructor x3 = 44.73; Attacker x2 = 26.82 | 71.55 | 71.80 |
| Total A + B + C | 14 Constructor runs, 10 Attacker runs | 342.84 | about 343 |

Platform: the Graphite provider route (Engy kimi-k3), tokens plus the carrier or pod compute the
existing R4 and PHASE4 grants already include; concurrency below. The
owner may approve stage by stage. **Stage membership is by runs, so the figures do not change:**
stage A is still 5 Constructor and 4 Attacker runs, about 128.19 (128.44 with cleanup). Moving
L1's confirmation to the dev-ladder changes only where L1 confirms and what it waits for:
stage A's L1 confirmations wait for VALIDATOR-25 (its L1 explore, Constructor and Attacker
runs do not). Stage B waits for VALIDATOR-25 and stage C for the security decision. ### Concurrency (Test Lead: "hammering" means more than one run at a time)

Proposal: **`max_concurrency` 2 for stage A** on the shared WSL host, raised to **4** after a host-load check with Data Collection (the host has been saturated; a
raise is not assumed). Each run keeps its own controller root. Cost is unchanged: the per-run
worst case and the stage ceilings stand (each run is capped on its own); concurrency only
raises the peak simultaneous reservation (2 x 14.91 = 29.82 USD at 2; 4 x 14.91 = 59.64 at 4,
inside the stage ceiling), which the grant gate must be checked against (the R4 arithmetic
assumed one run at a time).

Wall-clock effect on stage A (9 runs: 5 Constructor and 4 Attacker), at the grant's 39,600 s
(11 h) runtime cap per run, **worst case**:

| Concurrency | Waves | Worst-case wall clock |
|---|---|---|
| 1 (serial, the earlier assumption) | 9 | 99 h |
| 2 | 5 | 55 h |
| 4 | 3 | 33 h |

Real runs finish well inside the cap (the earlier phase-3 runs did); these are upper bounds.
L1 confirmations on the dev-ladder add their own tempo-bound time and wait for VALIDATOR-25.

Existing grants cover only part of this: R4 (45.00 ceiling, 3 runs, battery L1+)
covers 3 of stage A's Constructor runs if its 3 runs are unused (unverified); **everything else needs new grants** (a Level 0
kimi-k3 Constructor binding, a kimi-k3 Attacker token share, and R4-style grants for L2 to L4).
Grant files and runner bindings are the owner's and the Test Engineer's, not authored here.

## 5. Readiness-gate items per level

Run `python -m carbon.challenge_pipeline readiness --challenge battery-fastcharge-ageing-development-v1
--level N`. Item ids are the real ones (41 items). "Must PASS before the level's live run"
means the live-run entry gate; items about decision evidence (D, V) and the score-to-value
report gate **claims**, not a run, and are listed separately. No threshold is invented: each
item is a registered check or a recorded review. Status is from the first baseline
(`docs/development/challenge_pipeline/readiness/BASELINE_2026-10-06.md`) plus the later wiring
(#698), unless marked; **the second baseline has not run** (the WSL host is down), so statuses
are "last known".

**Level-independent items that must PASS before any live run (every level):**

| Items | Why | Last known (battery) |
|---|---|---|
| O1 (ownership review), O2, O3 | coordination and decisions recorded | O2, O3 PASS; O1 REVIEW_REQUIRED |
| P1, P2, P4, P5, P6, P7 | registered, neutral, no-op audit, boundary consistency | P1, P2, P5, P6, P7 PASS; P4 PASS after #698; P3 NOT_BUILT (battery) |
| R1, R3, R6, R2, R4, R5, R7 | real-path no-spend gate, lanes, disk and window, containment, model settings, grants, budget text | R3 PASS; R1 FAIL (containment needs the analysis image manifest); R6 REVIEW_REQUIRED; R2, R4, R7 NOT_BUILT; R5 NOT_BUILT (binding verified, headroom is a review) |
| A1, A3, A5 | tool authority classes, coverage stop rule, attribution policies | A1 PASS after #698; A3 NOT_BUILT; A5 REVIEW_REQUIRED |
| S1 to S5 | promotion rule, rank-last gates, margin study, noise source, incomplete predictions | S5 PASS after #698; S1, S2, S3 NOT_BUILT; S4 REVIEW_REQUIRED |
| H1, H3 | hidden-pool scoring through the real validator, no leakage | PASS (battery) |

**Level-dependent items (the runner takes `--level`):**

| Level | Extra items that must PASS | Notes |
|---|---|---|
| L0 | A2 (adapter at (battery, 0)), A4 (designated admission controller at level 0) | A2 NOT_BUILT only for the Attacker route-to-family check; A4 FAIL: identity PENDING_OPERATOR_IDENTITY |
| L1 | A2 and A4 at level 1 | A4: **no L1 entry exists** in `admission_controllers.json` (only level 0); needs designation. R4's four recorded entry conditions also apply (section 0). L1 confirmation additionally needs VALIDATOR-25 |
| L2 | A2 and A4 at level 2 | no L2 designation; also needs VALIDATOR-25 |
| L3 | A2 and A4 at level 3 | no L3 designation; also needs VALIDATOR-25 |
| L4 | A2 and A4 at level 4 | no L4 designation; VALIDATOR-25; security-owner acceptance of G5 compile isolation (LEVEL4 decisions) is the owner's, not a gate item |

**Items that gate value:score claims, not the live run:** D1 to D7 (decision studies; D7 PASS),
V1 and V2 (Q1 report and panel discrimination, both FAIL until a real-reference Q1 report is
recorded per level), V3 (review, FAIL by the Test Lead's ruling until a multi-seed promotion
policy lands), H2 and H4 (NOT_BUILT: tuning and confirmation sets disjoint; gates on hidden
and tuning data).

**NOT_BUILT items stay explicit.** Before the first live run the Test Lead decides, per item,
whether it must be built or waived by a recorded decision (gate items only get stricter; a
waiver names the replacement). This plan proposes no waiver.

## 6. Blockers and open items

1. **VALIDATOR-25** (dev-ladder deployment): blocks L1 to L4 confirmation. UNVERIFIED status.
2. **minerD-G lane, UIDs 8 to 11:** owner-registered 2026-10-08; to verify with Carbon's reader
   after the WSL restart. They stay on main for L0 confirmations only. L1 to L4 confirmation
   capacity is the ladder's hotkey count (minerC alone is one commit per tempo; more only if the
   owner creates minerH to K).
3. **Grants:** new Level 0 kimi-k3 Constructor binding, kimi-k3 Attacker token share, L2 to L4
   grants (section 4). The owner approves; the Test Engineer binds.
4. **Gate:** A4 designation per level (only level 0 exists, PENDING); R1 containment image; V1
   and V2 reports per level; O1, A5, S4 reviews (Test Lead).
5. **Level 4 permission** (owner and security owner), and L1 on main needing a live variant
   (section 1) are open decisions.
6. **Host:** the WSL host is unhealthy; no run, no gate rerun until Data Collection or the Test
   Lead says it is healthy. The second readiness baseline is outstanding and would refresh
   section 5's "last known".
