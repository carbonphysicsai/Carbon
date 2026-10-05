# Graphite readiness gate: what a challenge must pass before any live Graphite run

**Owner:** Test Lead session. **Why:** the first wave on battery, cooling and
motor was costly, and its lessons are in `LESSONS_REGISTER.md`. The owner set
this goal on 2026-10-05: "This should be the messiest run we ever have." This
gate turns those lessons into checks a new challenge must pass **before** any
live Graphite Constructor or Attacker session spends money.

**Status:** specification. Every item names its check. Items marked
**[auto]** have, or must get, a command. Items marked **[review]** are
recorded Test Lead review steps.
- **The target command** is `python -m carbon.challenge_pipeline readiness
  --challenge <id>`. It prints this checklist with PASS / FAIL / NOT_BUILT
  for each item, and exits non-zero unless every item passes.
- **Until that command exists,** the Test Lead runs the gate by hand and
  records the result in the challenge's wave notes.
- **Who builds it:** owner to be assigned (see the end of this document).

The gate does not replace the per-run live-launch checklist
(OWNER-GRAPHITE-TEST-WAVE-05 §3). It runs **once per challenge, and again per
construction level**, before that checklist is ever used. A challenge that
fails the gate gets no live Graphite run, at any level.

## O. Ownership and coordination

| Item | Check | Kind | Lesson |
|---|---|---|---|
| O1 | An ownership map exists for the challenge: contract, scorer, validator adapter, attack adapter, decision study, references, gates, literature, grants. Each line names one owner session, and the map is committed. | [review] | C4 |
| O2 | No open branch on origin uses a name the onboarding plans to use. | [auto] | C1 |
| O3 | Every owner question raised during onboarding has a decision file. | [auto] the decision ids cited in the onboarding record resolve | C1, C5 |

## P. Plumbing: the challenge runs through every shared path

| Item | Check | Kind | Lesson |
|---|---|---|---|
| P1 | Registered in the challenge registry, with a Level 0 construction contract reachable in the Launchpad. | [auto] | N1 |
| P2 | `ChallengeScoring` and an Interface v1 validator adapter are registered, and an unnamed scoring call refuses. | [auto] | N1 |
| P3 | A fixture dry run of phase 3 for this challenge passes end to end: brief, published material, bundle writeup, clean rebuild. | [auto] (#606 pattern) | N1 |
| P4 | No battery-specific literal is reached on this challenge's path: tool text v2, literature snapshot, writeup. | [auto] a grep of the path's resolved modules, plus the v2 role record | N1 |
| P5 | The no-op audit passes for every rebuildable capability. Known no-ops are listed. | [auto] `test_construction_noop_audit.py` | I1 |
| P6 | Identity is by rebuilt artifact: no count, dedup or limit keyed on recipe text. | [auto] the audit; WAVE-04 §1 | I1 |

## R. Runtime: the real path, not a synthetic one

| Item | Check | Kind | Lesson |
|---|---|---|---|
| R1 | The real-path no-spend gate passes for this challenge: the provider with a fake transport, the controller, ledger, pods and carrier under live threading. | [auto] `phase4 prelive`, `real_path_check` | E1 |
| R2 | A deterministic containment check with a host canary passes on the lane this challenge uses (pod, CPU carrier or miner lane). | [auto] (containment PR) | A3 |
| R3 | An environment probe and its attribution policy are registered for every compute lane used. | [auto] | E2 |
| R4 | Model settings: full context for each role's model, an output cap sized from use, and an endpoint that reports charges. | [auto] the prelive `*_model` blocks | E3, E4 |
| R5 | Grants: a per-challenge grant bound to main's blob, priced with lost-run headroom, tokens-only where no pods run. | [auto] | I2 |
| R6 | Host: free disk at least the threshold, and a host window agreed in writing between the executor and Data Collection. | [auto] disk; [review] window | E5, E6 |
| R7 | Agent-facing budget text matches the real ledger; no "0 of 0". | [auto] | E9 |

## A. Attack instrument

| Item | Check | Kind | Lesson |
|---|---|---|---|
| A1 | Every research tool has an authority class (authoritative, advisory, miner-local) and a family mapping; no UNASSIGNED. | [auto] | A1 |
| A2 | Each family has an attack example that fires, a trained control, a held-out control, and a route the Attacker can reach. | [auto] | A2 |
| A3 | The coverage stop rule is configured: k attempts per family before the finish tool is available. | [auto] | A2 |
| A4 | A designated admission controller is recorded for (challenge, level). | [auto] (#615) | I3 |
| A5 | Every attribution or grading assumption is a registered, versioned policy, and the Attacker has a family that probes it. | [review] | G1 |

## S. Scoring and gates

| Item | Check | Kind | Lesson |
|---|---|---|---|
| S1 | The promotion rule exists: comparison settings plus an equivalence margin measured from the challenge's noise source. | [auto] | S6 |
| S2 | Gate failures rank last (admissibility before ranking), tested with a known-answer case. | [auto] | G4 |
| S3 | A margin study for every gate: the minimum reference margin and 1st percentile, with fragile gates flagged. | [auto] (the gate audit's margin study) | G5 |
| S4 | The noise source is declared per construction family: seed, bootstrap, or both. | [review] | S6 |
| S5 | Incomplete prediction sets are refused on every host. | [auto] | G3 |

## D. Decision evidence (Track B)

| Item | Check | Kind | Lesson |
|---|---|---|---|
| D1 | A frozen decision study exists, with a finite comparator, commitment before reference access, and representative and boundary groups. | [auto] | n/a |
| D2 | The equal-cost harness adapter is registered, with a B ladder confirmed by the Test Lead. | [auto] | n/a |
| D3 | A timing calibration on the target hardware has run, and counted-plan timeouts are at least 2× p95. | [auto] | E8 |
| D4 | The importer has run on at least one real solver output. | [auto] | E7 |
| D5 | Reference coverage of the decision set is reported, and the refinement policy for unresolved cases is decided. | [auto] report; [review] policy | S4 |
| D6 | Any confirmation study's analysis code is built, merged and pinned with every imported module before freeze. | [auto] | S5, N3 |
| D7 | A fresh confirmation-set role is registered, with size, law and strata set (VALIDATOR-03). | [auto] | n/a |

## V. Value alignment, checked before optimisation money is spent

| Item | Check | Kind | Lesson |
|---|---|---|---|
| V1 | A Q1 score-to-value check on the available panel (baselines plus constructed controls): τ/ρ with a band, and divergences listed. A negative or within-noise τ is NOT a blocker, but it is recorded, and the first Graphite runs are then framed as alignment measurements, never as improvement hunting. | [auto] the harness; [review] framing | S1 |
| V2 | Panel discrimination: at least two distinct decision outcomes among panel members on the decision study. If not, widen the construction families first (development variant). | [auto] | S3 |
| V3 | Promotion claims require multi-seed evidence. | [review] | S2 |

## How the gate stays current

1. **New lessons feed the gate.** When a lesson in `LESSONS_REGISTER.md` is
   preventable before a live run, it becomes a gate item here in the same
   PR that records it.
2. **Each onboarding records its result.** The run is recorded in the
   challenge's wave notes: the first-run failures per item and the date it
   went green. The per-challenge metrics in the register's §8 then show
   whether onboarding is getting cleaner.
3. **Gate items only get stricter.** Removing an item needs a recorded Test
   Lead decision saying which enforcement replaced it.
4. **The command is the target.** Every [review] item says why it isn't
   automated; the aim is to automate it.

## Owner of the command

The `readiness` command is a challenge-neutral engineering ticket. Most checks
already exist as tests or tools and only need wiring into one report. It is
proposed for a dedicated owner session (see the Test Lead's note to the owner).
