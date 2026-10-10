# Onboarding pipeline: from a brief to a tested Challenge (ONBOARDING-PIPELINE-01)

**Owner:** Graphite Testing Manager. **Status:** documentation and data, 2026-10-10.
**Standing owner goal (relayed by the Test Lead, 2026-10-10):** "I want to continuously
improve at taking a challenge from brief to tested challenge. This should be carbons
specialty."

This page builds on the [lessons register](../../graphite/LESSONS_REGISTER.md), the
[readiness gate](../../graphite/GRAPHITE_READINESS_GATE.md) and
`carbon/challenge_pipeline/`. It decides nothing scientific, spends nothing, authors no
grant, and registers no gate. "Tested" is the Test Lead's working definition below. It is
not scientific qualification, security acceptance, LIVE or a launch claim.

The data lives beside this page and is checked by
`tests/cpu/test_onboarding_pipeline_data.py`:
[`stage_map.json`](stage_map.json), [`blocker_taxonomy.json`](blocker_taxonomy.json) and
[`cycle_metrics.jsonl`](cycle_metrics.jsonl).

## 1. Stage map

Each stage has an entry, an exit and an owner session, with the repository record it was
checked against. UNVERIFIED marks a mapping the records do not settle.

| # | Stage | Exit (short) | Owner session | Status |
|---|---|---|---|---|
| 0 | Brief | One page: buyer role, decision, value at stake | Owner picks; Codex researches | VERIFIED |
| 1 | Design packet | Ten packet sections filled; the rest `OPEN` with an owner | Codex drafts; Test Lead reviews | VERIFIED (owner mapping inferred) |
| 2 | Solver package | Pinned reference package, measured cost, conservation checks | Data Collection | VERIFIED (specs are SPECIFIED, not built) |
| 3 | Feasibility and value panel | V1-V5, T1-T5, C1+ evidenced; keep, reframe or replace | Codex, Data Collection, Test Lead; thresholds the owner's | VERIFIED |
| 4 | Question law | Law sheet accepted or declined by the owner; design-value prerequisite met | Codex proposes; owner accepts | VERIFIED |
| 5 | Bank | Sealed bank prepared on the hidden host from a pinned image | Carbon Validator (producer, bank adapters, VALIDATOR-28 family sources); Data Collection supplies each family's reference package and panel; the owner approves startup spend | VERIFIED (Test Lead ruling, 2026-10-10) |
| 6 | Readiness gate | `launch_ready` at the exact main SHA | Graphite Testing Manager; Test Lead waives | VERIFIED |
| 7 | Graphite stage A (L0, L1) | Checklist runs, lessons entries, L0 confirmations, stage report | Executor, Launchpad, Test Engineer, Test Lead | VERIFIED |
| 8 | Graphite stage B (L2, L3) | Per the stage B plan; needs VALIDATOR-25 and the owner's spend approval | Executor, Carbon Validator, owner | VERIFIED |
| 9 | Graphite stage C (L4, graph only) | Per the wave plan section 4a; permission granted, spend not | Executor, Level 4 engineer, owner | VERIFIED |
| 10 | Tested Challenge | The seven conditions below, all holding | Test Lead | VERIFIED (Test Lead working definition, 2026-10-10) |

The full entries and exits, with the file each came from, are in `stage_map.json`.

### Definition of TESTED (Test Lead working definition, development, 2026-10-10)

A Challenge is TESTED when **all** hold:
1. the readiness gate is `launch_ready` at every enabled level (no FAIL; waivers expired or closed);
2. a sealed hidden bank exists, with exposure accounting;
3. Graphite stages are complete at every enabled level, with real Launchpad confirmations
   scored by a validator, and every Attacker finding dispositioned (fixed, or accepted with a reason);
4. score-value alignment is measured on confirmed recipes (a Q1 report exists); a negative
   result is allowed but must trigger a scoring iteration;
5. control detection (T3) meets its target at the chosen k and E;
6. the incentive canary shows the best model weighted (INCENTIVE-CANARY-01);
7. the stage-end report is filed.

TESTED is **not** scientific qualification, security acceptance, LIVE or a launch claim.
LIVE or qualification is a separate owner step.

What the map still shows:
- **The bank (5) has no single stage definition.** Its owner is now ruled (above); its entry
  and exit are still assembled from the hidden-pool runbook and register lessons S11 and S12.
- **Condition 3 and 5 depend on later stages.** Condition 3 needs stages B and C for the
  higher levels, and 5 needs a chosen k and E, which are owner values.

## 2. Metrics

The register's section 8 already names per-Challenge metrics. This adds per-stage cycle
time and cost, which the challenge protocol asks for as Phase 1 step 7 (still `todo`).

- **Cycle time** per stage per Challenge: the days from the stage's entry record to its
  exit record, both cited.
- **Cost** per stage per Challenge: recorded as a cap or a pointer to the grant, never a
  balance or an account detail (public-repo rule).
- **Recording:** `cycle_metrics.jsonl`, one object per event, with `cycle_days` and `cost`
  as `UNKNOWN` until a record gives them. The seed rows are battery's first dated record
  per stage from git history. They are dates, not durations, because a first record's date
  is not the time spent producing it.
- **Automatic where possible.** The dates already exist in machine-readable places: git
  history of the stage artifacts, `readiness/<challenge>/history.jsonl`, lessons entries
  (`recorded_at`) and the heartbeat files. A small recorder that reads them is backlog item
  A9 below. It is not built in this change.

## 3. Blocker taxonomy

Seeded with battery stage A. Cause and fix come from cited records only. **Time lost is
`UNKNOWN` for every row**, because no record states it. One batched question to the owning
session is in section 5.

| ID | Blocker | Cause (source) | Time lost | Fix status |
|---|---|---|---|---|
| B1 | Wrong lane | Run launched against a lane other than the one needed (preflight decision) | UNKNOWN | Fixed in code (#967), not yet exercised live |
| B2 | Keys in the wrong distro | Key files not where the executor runs (preflight decision) | UNKNOWN | Fixed in code (#967), not yet exercised live |
| B3 | One controller per root | Two runs shared one root (preflight decision; wave plan) | UNKNOWN | Fixed in code (#967), not yet exercised live |
| B4 | Pod ceiling below the offered price | Rate in the grant is a ceiling; pods above it are refused (grants README). **Live on the stage A first launch:** the ceiling was below the GPU class's offer (Test Lead note, 2026-10-10) | UNKNOWN | Fix in PR 969 (ceiling becomes a grant field; owner-approved standing ceiling), not merged, not yet exercised live |
| B5 | Token share and pod split | One full-window call of the start model can exceed the token share (wave plan D35; grants README). The stage A first launch also needed a different share (Test Lead note) | UNKNOWN | Value fixed in PR 969; OPEN: no check on the split |
| B6 | Reboot fragility | After a reboot the signers and tunnels were down until the owner restarted them (Launchpad note, 2026-10-10) | UNKNOWN | OPEN: detected, not recovered |
| B7 | Auto-mode permission blocks | The classifier blocked a build (OWNER-CANARY-MINER-01) | UNKNOWN | OPEN: workaround is the owner's approve-edits mode |
| B8 | Silent failures | A stalled run or all-refused pods went unseen (preflight decision) | UNKNOWN | Fixed in code (#967), not yet exercised live |

Full rows (stage, sources, occurrences, fix reference, automation) are in
`blocker_taxonomy.json`. Each is also a register row, B1 to B8, in section 7d of the
lessons register.

**Honesty notes.** "Four failures" in the preflight decision is a count of launch
conditions, not of hours. The probe pod has not run against the live account, so no B-row
fix is called ENFORCED beyond "in code".

## 4. Automation backlog

Ranked by expected time saved on the **next** Challenge: how often the blocker recurs at a
wave start and whether a tool already prevents it. Hours are `UNKNOWN`, so the rank is
ordinal and should be revisited when section 5 is answered.

| Rank | Blocker | Change | Kind |
|---|---|---|---|
| 1 | B6 reboot fragility | One lane-up command per lane: list what is down, print the single owner action, re-run the preflight when the owner says it is done. It never starts a signer or signs. | generator |
| 2 | B5 token and pod split | Compute the split from the start model's full-window reservation and pods x rate ceiling; the preflight refuses a grant whose split fails either. | generator + check |
| 3 | B4 pod ceiling | Run the probe before proposing a grant and state the observed offer against the proposed rate ceiling. The proposal stays the owner's to approve. | check |
| 4 | B7 permission blocks | A template list of edit classes known to need approve-edits mode, asked once with the wave's other owner needs. | template |
| 5 | B1 wrong lane | Generate the lane file from a lane registry instead of by hand per wave. | generator |
| 6 | B3 controller roots | Allocate one fresh root per planned concurrent run and print the `--root` list. | generator |
| 7 | B2 keys | The template names key slots, not paths; the preflight reports missing ones together. | template |
| 8 | B8 silent failures | A collector over the shared heartbeat directory that raises one line when a run reads STALLED. | check |
| A9 | Cycle-time recorder | Read git history, readiness history, lessons and heartbeats into `cycle_metrics.jsonl`. | generator |

Ranks 1 to 3 and 5 to 7 are the parts of the **Graphite wave template** (section 6), which
is why it waits for stage A results.

## 5. One batched question (to the executor, Launchpad copied)

For each of B1 to B8: the time lost in stage A (hours, or UNKNOWN), the number of
occurrences, and whether the fix has been exercised live. For B7: the edit classes the
classifier blocked. Answers replace `UNKNOWN` in `blocker_taxonomy.json` with a citation;
until then they stay `UNKNOWN`.

## 6. After stage A reports: the Graphite wave template

Not built here. One command, for any Challenge, generating:
- the lane file and the controller roots;
- grant **proposals** only (platform, ceiling, runs, split), never authored spend;
- the preflight command line;
- the stage plan, from the stage map and the Challenge's readiness wiring.

Motor is next after battery. The template is designed against stage A's real results, so a
design written before them would encode guesses.

## 7. What this does not do

- It changes no gate item, threshold, grant, ledger or runtime behavior.
- It does not define scientific qualification or approve any spend; stage B spend stays
  gated on the owner's approval and the bound grant.
- It claims no time saved. Every duration is `UNKNOWN` until a record states it.
