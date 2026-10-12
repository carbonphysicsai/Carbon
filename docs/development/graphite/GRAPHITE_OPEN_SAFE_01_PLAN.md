# GRAPHITE-OPEN-SAFE-01: make the ladder open for miners and safe for Carbon, and hunt Level 5

**Status:** PLAN for the Test Lead and the owner, 2026-10-12. **Author:** Graphite Testing Manager.
Documentation only: it authors no grant, dispatches nothing, spends nothing and runs no host job.
Everything here is DEVELOPMENT evidence. It makes no qualification, LIVE, security-acceptance or
launch claim, and adopts no Level 5 capability.

**Owner priority (relayed by the Test Lead, 2026-10-12):** "Let Graphite try and attack all levels to
get this as open for miners and safe for us as we can… and a round of Graphite hunting for valuable
Level 5 opportunities." The ladder L1 to L4 opens today (RELEASE_SCHED section 4b-early on r8.1; the
owner runs it).

Challenge: battery (`battery-fastcharge-ageing-development-v1`), the only Challenge with attack adapters
and development variants at L1 to L4. Cooling and motor are L0 only and are out of scope.

## 0. What exists, from main at `dcbc13d59` and open PRs (2026-10-12)

| Fact | State | Evidence |
|---|---|---|
| Constructor on kimi-k3 at Level 1 and above, R4 at the 0.65/h pod ceiling with a 10.99 token share per 14.91 run | VERIFIED | `.agent/decisions/2026-10-11-OWNER-GRAPHITE-PHASE3-R4-CEILING-01.md` (#1076) |
| Stage B grants (L2 and L3, USD 143.35) and stage C grants (L4, USD 71.80) approved by the owner | VERIFIED in the repo (committed owner records and grant files on main); run use is from the executor host's grant-runs ledger (not committed; run counts only here): stage B Constructor 6 of 6 claimed, Attacker 2 of 4; stage C Constructor 3 of 3, Attacker 1 of 2 | Stage B: `.agent/decisions/2026-10-10-OWNER-GRAPHITE-STAGE-B-01.md` (commit 1dfb93165), grants `GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR` and `GRAPHITE-GRANT-STAGE-B-ATTACKER`. Stage C: `.agent/decisions/2026-10-10-OWNER-GRAPHITE-STAGE-C-01.md` (commit 31f64e049), grants `GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR` and `GRAPHITE-GRANT-STAGE-C-ATTACKER`. Grant files are under `docs/development/graphite/grants/`. |
| Attack adapters for battery at L0 to L4; Levels 2 to 4 name only their own families | VERIFIED | `attack/adapters` `BUILTIN`; #1072 |
| The brief lists each development level's widened surface | VERIFIED | #1081 |
| Level 4 staging, route R1 (Graphite lowers a graph in its own sandbox; Carbon handles the envelope as data) | MERGED; the isolation acceptance is the owner's review | #1098, `level4/L4_STAGING_R1_CONTRACT.md` |
| Level 4 envelope transport through signed parts on the Launchpad | VERIFIED | #1060 |
| Refused-capability log with the Constructor wish channel | VERIFIED; stage A L0 rows (8) merged, L2 to L4 rows (5) in #1154 | #1063, `level4/REFUSED_CAPABILITY_LOG.md` |
| Per-level readiness Q1 reports (so V1 and V2 at L1 can pass) | OPEN PR | #1157 |
| Dev-ladder deployment serving the development variants (VALIDATOR-25) | Code accepts a `development` served-variants map (`challenge_validator/dispatch.py`); what the running deployment serves is host state, UNVERIFIED here | |
| RELEASE_SCHED section 4b-early, r8.1 | An operator sheet (`RELEASE_SCHED_VALV2.md` on the shared operator folder), not in the repo by design; the owner is applying it on r8.1 now (Test Lead, 2026-10-12). The scheduled bank rotation rule and its security acceptance are merged | #1079, #1149 |
| Launchpad lanes minerD to G (UIDs 8 to 11, main, L0 confirmations) | OWNER-REGISTERED (nothing on main names them, by design); lane to UID mapping is in the executor's stage A folder, UNVERIFIED here | `GRAPHITE_LADDER_WAVE_PLAN.md` section 0 |
| Ladder confirmation hotkeys | `carbon-rehearsal-minerC` (the dev-ladder rehearsal hotkey). minerH and minerI are VERIFIED by name in `proof-panel-l0-v1.json` as submitters; whether they are Launchpad lanes is to be confirmed with the Launchpad session. minerJ exists but is the INCENTIVE-CANARY-01 challenger, idle until its slice 3, so it is canary-only, not a ladder hotkey. There is no minerK (Launchpad, 2026-10-12) | |
| The Level 4 "graph-variant fix" the Test Lead says L4 waits for | The Test Engineer is diagnosing it; no PR yet (Test Lead, 2026-10-12) | |
| Executor stage A L0 results (4 of 4 confirmations scored, Attacker 1 finding and 20 INCONCLUSIVE, 7 plus 1 Constructor refusals) | Executor report, 2026-10-12; the refusals are in the committed log | |
| Executor L1 to L4 Constructor sessions (L1 D, L2 E, L3 F, L4 G) ran on 2026-10-11 | Executor report and host logs, not committed; refusals: L1 none, L2 one, L3 three, L4 one | #1154 |

## 1. The plan, per level (L0 to L4)

**Roles.** At each level the Constructor uses the level's maximum freedom, and the Attacker attacks the live
ladder path. Exploration runs on the development door first; confirmations go through the Launchpad
(OWNER-LADDER-THROUGH-LAUNCHPAD-01). Nothing here counts as a level passing.

| Level | Constructor, at maximum freedom within the level | Attacker, against the live path | Waits for |
|---|---|---|---|
| L0 | The widest recipe the L0 domains allow, including each cap (for example `ensemble_members` 4, `steps` 20000) and each documented alias | The L0 adapter's families, then the miner door | Nothing |
| L1 | The loss-expression surface of the L1 variant | L1 adapter | #1157 for V1 and V2 at L1 |
| L2 | The spectral and v2 surface | L2 adapter | Dev-ladder serving L2 (UNVERIFIED) |
| L3 | The numerics surface | L3 adapter | Dev-ladder serving L3 (UNVERIFIED) |
| L4 | Graphs through the R1 staging tool | L4 adapter, and the staging tool's envelope handling | The graph-variant fix (UNVERIFIED reference), the owner's isolation review of #1098, and the security sign-off for Attacker code on disposable hosts (HUMAN_INPUT) |

**The attack families, at every level.** Intake (the miner door and the signed parts), rebuild (the
carrier and the pod), scoring (the frozen rule), hidden-data access, resources (compute, memory,
filesystem, network, wall clock), and gaming (score gains with no honest gain). Each uses the level's own
adapter; none gets more authority than a miner has.

**OPENNESS: what a miner can legally build.** Every refusal the Constructor meets is classified, once, in
the refused-capability log's evidence column:
- **BRIEF_GAP:** the request is inside what the level offers, but the brief did not say so or used another name. The fix is the Constructor's brief. Example from the committed log: `weights` for `matrices`, `layer` for `layer_norm`, and `steps` not divisible by `ensemble_members`.
- **ENVELOPE_TOO_TIGHT:** the request is past a ceiling and has a plausible honest benefit that can be contained. It becomes a candidate for the next toolkit version, not a change mid-competition (OWNER-LEVEL5-INTERNAL-LANE-01). Example: `ensemble_members` 5 against a cap of 4, and `steps` past 20000 (4 of the 7 L0 `REFUSED_UNREBUILDABLE` rows).
- **CORRECT_BLOCK:** the request would break an invariant (hidden evaluation, untrusted execution, forbidden score input, a compute count that is not the true cost). It stays refused.
- **Declared but not served** is its own case: the L0 `fno` plus `pytorch` row was refused after compile (`backend_not_served:pytorch`). That is a brief gap or a serving gap, and #1032 (PyTorch on Carbon's Graphite pods) is the relevant change.

Success criterion: every refusal in the log carries one of these classes with a reason, and each
BRIEF_GAP has a brief change or an owner question.

**SAFETY: zero escapes.** An escape is any Attacker finding that reaches hidden material (seeds, draw ids,
protected samples), exceeds a resource bound, writes outside its root, runs code on a Carbon host, or
raises an official score without an honest gain. The success criterion is zero escapes across all levels. A
finding that is not an escape (an INCONCLUSIVE result, or a block that held) is recorded and dispositioned.
The Attacker is graded by the oracle, not by its own claims (#1031).

**Every finding goes to the lessons register** (`LESSONS_REGISTER.md`) as one of two dispositions:
- **widen:** open a freedom the finding showed is safe (BRIEF_GAP or a contained ENVELOPE_TOO_TIGHT);
- **fix:** close the hole, with a regression test.

Open Attacker findings from stage A L0 (1 finding) must be dispositioned before the stage A report is
filed (TESTED condition 3 in `ONBOARDING_PIPELINE.md`); that disposition is not yet recorded.

**What stays human.** The security sign-off for Attacker code on disposable hosts, the isolation
acceptance of Level 4, the per-run Level 5 grants, any adoption of a capability, and every spend
approval.

## 2. GRAPHITE-L5-HUNT-01: a round of Level 5 opportunity hunting (PROPOSALS ONLY; the runs are approved, the findings are not)

**Authority and frame.** The owner's direction is "for graphite to find all positive level 5
opportunities and add them into the base image for every miner" (OWNER-CHALLENGE-ONBOARDING-LADDER-01).
Level 5 is an internal lane: miners never run code in it, Graphite's Constructor explores honest gains,
the Attacker tries to break each, and attack findings never ship (OWNER-LEVEL5-INTERNAL-LANE-01). This hunt
**proposes**; adoption is the owner's. Level 5 is not built, and nothing here changes runtime behaviour.

**Method.** Graphite Constructor sessions at Level 4 with the wish channel on (`CARBON_CAPABILITY_LOG`,
#1063), so every capability it asks for is stored as data and widens nothing. The Attacker then tries to
break each candidate. Each candidate is classified as the Level 5 decision does: plain math (an allowed op
or library block), a solver need (the solver op), a speed kernel (a Carbon-owned, audited kernel registered
by name), or a library (wrapped if pure, else internal).

**Ranking rule.** Expected value to buyers divided by risk and the containment needed. The value column
below is qualitative, from the refusal evidence. No gain figure is invented: every expected gain is
UNMEASURED until a hunt run measures it with a stated tool.

| Rank | Candidate | Evidence | Class | Value to buyers (qualitative) | Risk and containment needed |
|---|---|---|---|---|---|
| 1 | More ensemble members and more steps than L0 allows | 4 of the 7 L0 `REFUSED_UNREBUILDABLE` rows ask for more members or steps (the log); L2 and L3 rows in #1154 are unclassified | Compute budget, not a new op | High if accuracy per compute improves; UNMEASURED | Low: every unit is counted at true cost; needs only a new cap in a new toolkit version |
| 2 | PyTorch-backed families (FNO) served on the same footing as JAX | L0 declares `fno` and `pytorch`; the refusal is `backend_not_served:pytorch`; owner backend-parity direction 2026-10-06; #1032 | Serving gap | Medium to high: opens a model family miners already try | Low to medium: backend-parity and device-class acceptance for each kernel |
| 3 | Solver-calling ops used in training only | OWNER-LEVEL5-INTERNAL-LANE-01 condition 4 (never at inference) | Solver op | Possibly high for physics-informed training; UNMEASURED | Medium: hard rule at the op, true-cost counting, an attack suite for inference-time calls |
| 4 | Carbon-owned fused kernels (loss and backward, spectral transforms) | Wish-channel example in the capability-log tests; the L2 spectral surface | Speed kernel | Medium: speed, not new accuracy | Medium: audited, determinism and parity checks, registered by name |
| 5 | Pure libraries wrapped as ops | The wish channel; unmeasured | Library | Low to medium | Medium: pure-only; otherwise internal |
| n/a | Vocabulary aliases (`weights` for `matrices`) | Two L0 rows | BRIEF_GAP | Not Level 5 | Brief only |

The ranking is a proposal. Each hunt run adds rows from live evidence (the wish lines, the L2 to L4
refusals, and the Attacker's failed attempts), and re-ranks.

**Output.** One proposal file per candidate with: the request, the class, the measured gain (or
UNMEASURED with the tool that would measure it), the containment, the attacks tried and their results, and
the owner question. No adoption, no base-image change, no grant authored.

## 3. The spend line (hunt and Constructor pass approved by the owner; the grant file binds spend, not this page)

Public repo: caps, rates and run counts only. Per-run worst cases are from the committed grants. The run
counts below are from the executor host's grant-runs ledger (read-only, 2026-10-12; the ledger is not
committed, and it holds ids, digests, timestamps and cost totals only).

**Per-run basis.** Constructor run 14.91 USD (R4 worst case, cleanup 0.12 per grant). Attacker run 13.41
USD (a stated assumption: 10.00 model share plus the 3.41 PHASE4 worst case; cleanup 0.13 per grant).

**What is approved and what is left.** The approvals are committed (section 0). The Constructor approvals
are consumed; the Attacker approvals are partly unused.

| Grant | Approved ceiling | Runs claimed (ledger) | Runs left | Worst case left |
|---|---|---|---|---|
| Stage B Constructor (L2, L3) | 89.58 | 6 of 6 | 0 | 0 |
| Stage B Attacker (L2, L3) | 53.77 | 2 of 4 | 2 | 26.82 |
| Stage C Constructor (L4) | 44.85 | 3 of 3 | 0 | 0 |
| Stage C Attacker (L4) | 26.95 | 1 of 2 | 1 | 13.41 |
| **Approved and unused** | | | 3 Attacker runs | **40.23** |

**Basis for usage (the figures are with the Test Lead, not in the repo).** Pods never settle at the
provider: every created pod ends in `pod_charge_unresolved`, and only the zero-cost refusals are
`pod_settled`. So a run's usage is its pod reservation plus the provider-reported model charge. The model
charge is partial: the session-1 outputs of the stage B and C Constructor runs were overwritten by a
relaunch (lessons register B14), so usage computed this way is a **lower bound**, and the USD left under
each ceiling is an upper bound. The Constructor runs of stages B and C were counted from the existing
controller roots (the ledger's migration), so the ledger holds their counts, not their cost. The weekly cap
ledger is reservation-based (a safety-conservative basis) and holds no settled pod charge. The run counts
are the binding limit here: a grant's ceiling is its permitted runs times the worst-case run cost, and the
runs actually cost less than that worst case.

**New money (approved 2026-10-12: OWNER-GRAPHITE-OPEN-SAFE-01-GRANTS, #1163; two separate ceilings, no transfer between them).**

| Item | Runs | Worst case |
|---|---|---|
| Hunt, Constructor at L4 with the wish channel, 4 themes (compute and steps; PyTorch families; solver ops; kernels and libraries): 4 x 14.91 = 59.64, cleanup 0.12 | 4 | 59.76 |
| Hunt, Attacker against each shortlisted candidate: 2 x 13.41 = 26.82, cleanup 0.13 | 2 | 26.95 |
| **Hunt total (the owner's "L5 hunt" ceiling)** | 6 | **86.71** |
| One more max-freedom Constructor pass each at L2, L3 and L4 after brief changes (3 x 14.91 = 44.73, cleanup 0.12), because the earlier Constructor runs are consumed (the owner's "L2-L4 Constructor pass" ceiling) | 3 | 44.85 |
| **Approved, hunt plus Constructor pass** | 9 | **131.56** |

**The one line:** "Graphite open-and-safe: the approved Constructor runs of stages B and C are used up (6 of 6, 3 of 3);
3 approved Attacker runs remain (USD 40.23 worst case); the owner approved USD 86.71 for the Level 5 hunt (4 Constructor
runs at 14.91, 2 Attacker runs at 13.41, cleanup 0.12 and 0.13) and USD 44.85 for one more Constructor pass
each at L2 to L4, USD 131.56 in all (#1163), at the 0.65 per hour pod ceiling."

**Assumptions.**
- The hunt runs under a new R4-style grant bound to Level 4 (and the wish channel), plus a kimi-k3 Attacker grant. The existing stage C grants cover three Constructor and two Attacker runs at L4 and cannot be borrowed for the hunt.
- The hunt Constructor costs the same as an R4 run; the Attacker is priced as in the wave plan.
- Stage A (L0 and L1) grants are separate and not repeated here; their remaining runs were not checked.

**The weekly cap (OWNER-TESTNET-WEEKLY-BUDGET-01, amended by OWNER-TEST-GRANT-01, #1167).** USD 300 across any
rolling seven days and USD 50 per run, pods plus model charges, enforced on the host ledger (#1067, #1168). The
ledger's constants follow the record once the cap PR (#1178) merges; until then the host ledger still reads 150.
The figures below were derived against 150 and fit within 300 with room to spare. A run is reserved at its worst case at launch and settled at
its reported cost, and a launch that would pass the cap is refused (`weekly_budget_reached`). The usage so far is a moving number: read it with
`python -m carbon.agent_campaign.grant_runs weekly` before each wave. The ledger's window starts with the
ledger, so spend before it (including the seeded Constructor runs) is not counted in it. Consequences:
- The approved Attacker runs left (40.23) plus the hunt (86.71) are 126.94 at worst-case reservation: one window at the old 150 cap if the rolling usage is at most 23.06 when they launch; the re-pass (44.85) makes 171.79, which needs the 300 cap or a second window.
- Settled costs are lower than worst cases, so real scheduling can be faster. Reservations are released as runs settle.

| Wave | Runs | Worst-case reservation |
|---|---|---|
| 1 | The 3 approved Attacker runs (L2, L3, L4 once the L4 prerequisites hold), then the hunt's 4 Constructor runs | 40.23 + 59.64 = 99.87 |
| 2 | The hunt's 2 Attacker runs, and the Constructor pass | 26.82 (+ 44.73) |

- L4 runs wait for the prerequisites in section 1; if they slip, the L2 and L3 Attacker runs and the hunt's non-L4 themes can move forward in their place.
- Server runs (CCX63), mainnet and anything over the cap are not covered by the weekly budget and stay the owner's.

## 4. Order of work

1. Merge #1157 (per-level Q1) and #1154 (L2 to L4 refusal rows).
2. L0 to L3: Constructor and Attacker at maximum freedom, classify every refusal, file every finding in the lessons register.
3. Ask the Test Lead for the graph-variant fix reference, then run L4 once the isolation review and the sign-off for Attacker code on disposable hosts are done by their owners.
4. The hunt, after L4's wish lines exist. Proposals only, then the owner decides.
5. A stage report per level: openness (refusals by class), safety (escapes, expected zero), and the hunt proposals.

## 5. Not decided here

No spend (every figure is a worst-case cap or a proposal), no grant file, no security acceptance, no
adoption of a Level 5 capability, no scientific, LIVE or launch authority. The grant files bind spend.
