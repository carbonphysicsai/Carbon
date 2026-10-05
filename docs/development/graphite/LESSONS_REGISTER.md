# Graphite test wave: lessons register

**Owner:** Test Lead session. **Authority:** the owner, 2026-10-05:

> I want you to keep a log of all lessons learned that we can use to make
> this process more efficient for every challenge we bring here. This should
> be the messiest run we ever have. Create a system to make sure that is the
> case.

## How this register works

The per-execution log already exists: every execution writes a
`carbon.challenge-pipeline.lesson.v1` entry under
`carbon/challenge_pipeline/lessons/` (242 entries at 2026-10-05). That log
records what happened. This register records **what we change so it never
happens again**. Each row is a *cross-cutting* lesson, a cost this wave
actually paid, with one disposition:

| Disposition | Meaning |
|---|---|
| **ENFORCED** | A test, gate or tool now fails when the mistake recurs. The reference names it. |
| **GATED** | An item in the Graphite readiness gate (`GRAPHITE_READINESS_GATE.md`) checks it before any live run on a new challenge. |
| **DOCUMENTED** | A rule or default in a runbook. It's weaker than ENFORCED, so each one says why it isn't enforced yet. |
| **IN PR** | The enforcing change is written but not yet merged. It becomes ENFORCED on merge. |
| **OPEN** | Not yet prevented. It has an owner and a next step. |

**The rules.**
- Every cross-cutting lesson enters here within one working day of being
  found.
- No lesson stays OPEN without an owner.
- The goal is to move rows from OPEN to ENFORCED or GATED. A lesson that can
  only be documented says why.
- At the end of each challenge's wave, the Test Lead runs a retrospective that
  re-checks every DOCUMENTED and OPEN row.

**Success measure.** For each new challenge onboarded, the Test Lead records
the metrics in §8. The target is that each challenge is cleaner than the one
before, and that none is as messy as this first wave.

---

## 1. Coordination and decisions

| # | Lesson | What it cost this wave | Prevention | Disposition |
|---|---|---|---|---|
| C1 | Owner answers given in different sessions diverged: the pod-thread fix went to two agents, and the R2 grant was written on two branches with the same name | Duplicate agents, a near branch collision | One routing point: engineering decisions for a wave go through the Test Lead, and every owner answer becomes a decision record the same day | DOCUMENTED (decision files `OWNER-GRAPHITE-TEST-WAVE-01…07`); OPEN: a check that a new branch name isn't already on origin (PR Head) |
| C2 | Sessions auto-archive when their PR merges, so coordinating sessions went dark | Lost messages; the Validator and Test Lead were offline for hours | Pin every standing team session | ENFORCED by practice (pinned); DOCUMENTED in memory `test-lead-session-pinned` |
| C3 | Messages sent to a stopped session are lost, and its idle notices are stale | Resends; work stalled | Resend to the session id; PR Head keeps the board; standing agents subscribe to idle notices | DOCUMENTED |
| C4 | Ownership of each component was unclear: the cooling scorer was built by Codex while also queued for the Validator | Duplicate branch dropped | An **ownership map per challenge component** written at onboarding (gate item O1) | GATED |
| C5 | Agents' "confirm with the owner in my own session" rule added latency to every relayed approval | Hours of waiting on routine items | Batch owner questions into one list, record answers as decision files, and let agents cite the file | DOCUMENTED |
| C6 | Merging main into branches was done by several agents | Merge-hygiene violations, repeated CI | Only PR Head merges or updates branches; agents push normal commits | ENFORCED by practice (OWNER-MERGE-HYGIENE-01) |
| C7 | Facts went stale between sessions: a PR merged, or a status changed, while a session was offline | Wrong premises in plans (my "six accepted level proposals") | Re-verify against origin/main before relying on any remembered fact; cite SHAs | DOCUMENTED |

## 2. Environment and execution

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| E1 | Dry runs with synthetic backends hid real-path defects: the sqlite cross-thread failure, the context ceiling, parallel calls | 3 of 3 phase-3 live sessions lost to harness defects | A **real-path no-spend gate** before every live run, with fakes only at the network boundary | ENFORCED: `phase4 prelive`, `pods.real_path_check` (#569, #571); GATED (R1) |
| E2 | A GPU driver mismatch on some pods was typed as candidate failure | 6 pods lost; wrong attribution | A Carbon-owned environment probe before the candidate program; relaunch; `allowedCudaVersions` | ENFORCED: pod-attribution-v2 (#604) |
| E3 | Defaults too small for the models: a 65,536-token context, 2,048 output tokens | Session 2 died after 2 calls; Attacker turns truncated | Full-context default per model (D34, D35); output cap sized from use | ENFORCED (D34/D35); OPEN: output cap (Test Engineer) |
| E4 | One provider endpoint (Engy messages) reports no charge, so the full reservation is booked | Distorted budgets | Use the endpoint that reports charges; test that charges settle | DOCUMENTED (GRAPHITE-D34) |
| E5 | The shared operator host ran Graphite, EV5 sealed work and data campaigns at once | Scheduling stalls; risk to sealed work | A **host-window protocol** (the executor and Data Collection agree windows) plus an internal resource profile for agent code | DOCUMENTED; ENFORCED: internal resource profile (containment PR) |
| E6 | A full C: drive makes WSL read-only | Install hold | Check free disk in the gate | GATED (R6) |
| E7 | The counted-campaign importer had only ever run on fixtures and rejected all 48 real records (empty solver logs) | A study version bump (V2) and a re-adoption | Every importer runs on at least one real solver output before a counted campaign is frozen | GATED (D4) |
| E8 | The 3600 s timeout was set from estimates; real host p95 was 1500 s, but the pilot max was 5983 s | A near-invalid counted plan | A **timing calibration on the target hardware** before freezing any counted plan | GATED (D3) |
| E9 | Graphite's status text said "0 of 0 trials left" | It misled the Attacker into skipping a family | Fix the text, plus a test that agent-facing budget text matches the real ledger | OPEN → Test Engineer (oracle-fix PR) |

## 3. Shared code and challenge neutrality

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| N1 | Battery-only literals were spread through "shared" code: scoring calls, pod data, writeups, tool text, published-material lists, literature topics, the dry run | 12 blocking gaps before cooling could run | A **neutrality audit** when a second challenge registers: an unnamed scoring call refuses; tests run the full Graphite path per registered challenge | ENFORCED: `--challenge` required, unnamed refusal (#584); versioned neutral tool text v2 (#610); IN PR: per-challenge plumbing (#606); GATED (P1–P4) |
| N2 | Frozen study manifests pin shared modules, so an innocent edit invalidates a freeze | Coordination overhead; risk to the counted motor campaign | A **pinned-file registry**, with CI refusing edits to files a live freeze pins unless the PR declares a new study version | OPEN → PR Head and the Test Engineer (CI check) |
| N3 | A freeze manifest pinned a cutoff value but not the module computing it (EV5 `admissibility.py`) | A silent drift risk to a one-shot confirmation | Freeze manifests pin **every imported module**, and analysis re-hashes them before running | ENFORCED for EV5 (EV5-RUN-01 pin step); GATED (D6) |

## 4. Identity, grants and accounting

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| I1 | Proposal ids repeat across runs; a "no-op" recipe flag was really a default; a KNN digest ignored k | Wrong cross-run identity; aliased and merged constructions | Identity by rebuilt artifact (OWNER-GRAPHITE-TEST-WAVE-04 §1), plus a standing no-op audit | ENFORCED: `test_construction_noop_audit.py` (#619); OPEN: KNN versioned digest (Test Engineer) |
| I2 | The controller counts every run and binds one grant document | Refund grants needed (R2, R3) | Price runs with lost-run headroom, use per-challenge grants, and bind grants to main's blob and the named challenge | ENFORCED: grant bound to main's blob (#569); IN PR: per-challenge binding (#612); DOCUMENTED: headroom |
| I3 | Admission findings lived in per-run controllers, so no record was canonical | The LOCK check could look at the wrong root | One designated admission controller per (challenge, level) | IN PR (#615) |

## 5. Attribution and grading integrity

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| G1 | Hard-coded attribution assumptions (crash = candidate, timeout = candidate) | Mis-typed outcomes; dodge vectors | Every attribution rule is a **registered, versioned policy** with its raw evidence kept, and the Attacker tests it | ENFORCED: pod-attribution v1/v2, baseline-retry, cooling candidate-fault v1 (#620, no charge to the candidate; replay baseline). OPEN: cooling candidate-fault v2, which charges the candidate, is a follow-up and a condition for any live cooling Graphite or Attacker run (readiness A5 condition) |
| G2 | Failure-stage claims were written where the candidate could write | A forgery vector at Levels 4–5 | Host-observed timing is the authority; candidate-writable files are evidence only | ENFORCED (#573) |
| G3 | Missing predictions were excluded instead of charged | An omission dodge | Every host refuses incomplete prediction sets | IN PR (#613, WAVE-07 §1) |
| G4 | A gate helper returned 0.0 on FAIL, so a failure ranked first under a negative-error score | A wrong τ in #609 | Admissibility before ranking: gate failures rank last, tested | ENFORCED (#617); EV5-RUN-01 ruling |
| G5 | A gate tolerance sat 0.0006 K inside the references | Live false-rejection risk | A **margin study for every gate** at onboarding | GATED (S3); cooling v2 at 0.1 K |
| G6 | A case-insensitive role guard could be bypassed | Possible recall of a sealed batch | Security review of every guard; case-folded comparison | ENFORCED (#583) |

## 6. Attack instrument

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| A1 | The oracle judged advisory and miner-local tool acceptance as boundary breaches | 35 false findings in phase-4 session 1 | Per-tool **authority classes**; FAILING_TRIGGER only at authoritative boundaries; regression tests | OPEN → Test Engineer (oracle-fix PR) |
| A2 | The Attacker stopped itself with 87% of its budget left, and 5 families were unreachable | Thin coverage | A coverage stop rule (k attempts per family) and a route for every family | OPEN → Test Engineer |
| A3 | Containment was evidenced only by self-reported output | Unverifiable isolation | A **deterministic containment check** with host canaries in the pre-live gate | OPEN → Test Engineer (containment PR); GATED (R2) |

## 7. Science: score, value and evidence

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| S1 | Practice scores were anti-aligned with decision value (battery τ −0.47; motor 0.37 on 16 members) | Graphite optimised a misleading target; the promoted bundle was worse in value | Run a **score-to-value (Q1) check on a diverse panel before** spending on Graphite optimisation; Graphite runs measure alignment from the start | GATED (V1); OPEN: score fixes (SR-B1/SR-M1 → diagnosis → score variants) |
| S2 | Promotions bootstrap over cases, not seeds | Seed-luck "improvements" were promoted | Multi-seed evidence for any promotion claim; seed bands on every τ | DOCUMENTED; OPEN: rule fix candidate (SR-B2) |
| S3 | Panels too narrow to discriminate (cooling KRR-only; all arms chose d03) | No alignment measurable on cooling | A **panel-discrimination check** at onboarding: at least two decision outcomes among panel members, or widen the families | GATED (V2) |
| S4 | Reference coverage gaps (6 of 12 battery scenarios resolvable) | Half the comparison lost | A **reference-coverage check** and a refinement policy decided before the study | GATED (D5); DOCUMENTED (WAVE-07 §2) |
| S5 | The analysis for a one-shot confirmation (EV5) was never built before freeze | A delayed run, and a post-hoc risk | The analysis code is built, merged and pinned **as part of the freeze** | GATED (D6) |
| S6 | Seed-noise margins don't exist for deterministic models (KRR) | A method decision mid-wave | Define each family's noise source at onboarding (seed, bootstrap or both) | GATED (S4) |
| S7 | A model with no information ties every candidate, so the selection is a tie-break artifact | A misleading "choice" | TIE_DETERMINED flag | ENFORCED (#601) |
| S8 | Graphite's own rationale credited a parameter that did nothing | Plausible but false explanations | Never accept agent explanations as evidence; ablate | DOCUMENTED |

## 7a. Added after the first gate runs and reviews

Owners are the sessions the Test Lead named. A proposal for a gate item is made
in the PR that adds the lesson and is approved by the Test Lead; it is not a
change to the gate tables.

| # | Lesson | Cost | Prevention | Disposition |
|---|---|---|---|---|
| X1 | Construction boundary behaviour was checked piecemeal, so a boundary could disagree between the contract, the compiler and the validator | Hidden inconsistencies found late | A standing construction-boundary consistency test over every registered contract | ENFORCED: `test_challenge_validator_boundary_consistency.py` (#624, VALIDATOR-10); owner Carbon Validator. Gate item proposed: P7 [auto] |
| X2 | Two attack vectors were identical in effect (`group_sacrifice` = `cooling_optimism`), so coverage counted one vector twice | Overstated attack coverage | A no-identical-vectors test across a challenge's families | IN PR: cooling adapter `cooling-l0.v3` with its no-identical-vectors test (Test Engineer; PR number to confirm, not on main at 2026-10-05); then fold into gate item A2 |
| X3 | A new compute lane (the CPU carrier) borrowed the GPU pod's attribution policy, whose probe does not apply to a CPU lane | The carrier's environment failures would have been mis-typed | Every compute lane registers its own attribution policy and environment probe; the gate never borrows one | ENFORCED: R3 refuses a lane with no policy of its own; the carrier policy `carrier-lane-v1` is in #630 (open, VALIDATOR-11). Owner Carbon Validator. GATED (R3) |
| X4 | An empty value (`strata: []`) was used to mean "intentionally none", so a missing value and a deliberate one looked the same | Battery D7 read as a gap that was a decision | A deliberate "none" is an explicit named value; an empty one is refused | ENFORCED: `NONE_UNIFORM_LAW` (#627, VALIDATOR-03), and gate D7 refuses an empty list. Owner Carbon Validator. GATED (D7) |
| X5 | Agent session restarts change the session's message address, so messages to the old address were lost | Resends and stalled work | Keep pins and the board current: list sessions before sending; PR Head keeps the board | DOCUMENTED (extends C2 and C3); owner Test Lead and PR Head. Not enforceable in code: it depends on the host's session manager |
| X6 | The gate wrote its runtime history under `carbon/`, so a gate run left shipped code dirty and the pre-live check (R1) then refused it | R1 failed on the second run of the gate; found in the Linux shakedown | Runtime outputs (history, reports) live outside shipped code, under `docs/development/challenge_pipeline/readiness/` | ENFORCED: `test_a_gate_run_leaves_carbon_clean` and the history-path test (readiness runner PR); owner Graphite Testing Manager. No gate item needed: it is a property of the gate itself |
| X7 | A gate check ran on another challenge's resource: cooling passed R1 on battery's phase-4 grant, which hid the missing per-challenge grant | A false PASS for a challenge with no grant | A check uses the challenge's own resources and fails closed when it has none; it never falls back to another challenge's | ENFORCED: R1 reads `grants.phase4` per challenge and `test_r1_never_passes_on_another_challenges_grant`; owner Graphite Testing Manager. Per-challenge grant binding is #612 (open). R5 (grants) is the gate item for it |

## 8. Metrics recorded per challenge onboarding

For each challenge, at the end of its wave:
- **Readiness gate:** the date it went green, and the number of items that failed on the first run of the gate;
- **Harness-lost live runs:** live runs lost to Carbon harness defects (target 0);
- **Post-start defects:** defects found after the first live Graphite run (target: falling each challenge);
- **Calendar:** days from the Level 0 contract to the first valid Graphite run;
- **False findings:** oracle false findings per Attacker session (target 0 after A1);
- **New lessons:** cross-cutting lessons added to this register, which should shrink each challenge;
- **Owner interruptions:** owner interruptions per wave, counting decision batches rather than single questions.

| Challenge | Gate green | Harness-lost runs | Post-start defects | Days to first valid run | False findings per session |
|---|---|---|---|---|---|
| Battery (wave 1) | n/a, no gate yet | 3 | ≥ 20 | not tracked | 35 |
| Cooling | | | | | |
| Motor | | | | | |
