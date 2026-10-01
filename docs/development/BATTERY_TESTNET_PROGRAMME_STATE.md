# Battery testnet programme: current state

**This is the single record of open work** for the battery testnet track
(parent #341) and its engineering-value experiments. Nobody, human or agent,
should depend on a conversation's memory.

**Update rule:** every PR in this track updates this file in the same PR:
- move finished rows to "Done";
- add any new open item it creates;
- keep the "Last updated" line current.

A row is done only when its evidence is merged or recorded here.

**Last updated:** 2026-10-01, with the EV2 results PR (after the battery intake PR, OWNER-BATTERY-INTAKE-01).

## Authority in force

| Record | What it settles |
|---|---|
| OWNER-BATTERY-TESTNET-01 (OD-1 to OD-8) | challenge, exam rule (OD-2), security review (OD-3), all-burn Phase A (OD-4a), no winner weights (OD-4b), USD 20 budget (OD-5), no validator hotkeys (OD-6), miner commitments (OD-7), per-challenge contracts (OD-8) |
| OWNER-BATTERY-TESTNET-02 / -03 | research vocabulary; exclusion scope; the battery agent; M3 direction |
| OWNER-BATTERY-TESTNET-04 | prior spend excluded (USD 20 intact); GPU image = `carbon-accelerator-worker@sha256:e4a2…`; OD-3 recorded approved |
| OWNER-LAUNCH-PORTFOLIO-01 (2026-09-26) | battery is a launch Challenge (portfolio: battery, motors, cold plates, photonics); EV1/EV2 are part of its launch-readiness path; OD-1 to OD-8, qualification, launch gates and spending are unchanged |
| Engineering-value direction (2026-09-25) | EV1 is off-chain DEVELOPMENT; the testnet rule is unchanged until a prospective change is approved |

All of these are in `.agent/DECISIONS.md`.

## Open work

| # | Item | Owner | Depends on | State |
|---|---|---|---|---|
| 2 | Host steps, the complete procedure in handoff §0: doctor, truth-materialize, truth-verify, runtime probe, service key, deployment, `operate init`, and a draft OD-4a request | host session on the authorized WSL host | #351 (merged) | not started |
| 3 | Decide whether to adopt runtime spec 471 (the live operator config pins 458), from the probe report | owner | 2 | open |
| 4 | Approve the exact OD-4a `request_digest`, regenerated from a fresh probe just before dispatch (the step 2 draft is for format review only); one publication per record | owner | 2, 3, 7 | open |
| 6 | M4: GPU backend for the daemon (device-attached carrier, host admission, device lease) | Claude session | #351 (merged) | not started |
| 7 | M4: two-host RunPod reproducibility run (handoff §4 R2, R3) | host session | 6; fresh balance and active-pod check | not started |
| 8 | M3 gaps: two-instance commit-reveal cross-check; chain `CommitmentReader`; retired-case release policy | Claude session | — | not started |
| 9 | OD-7 commitment posting (needed at the mainnet switch, where several validators must agree on one recipe) (count per day, window, fee cap and expiry need owner values) | Claude session + owner | 8 | not implemented |
| 10 | M5b Launchpad battery UI; M6 control center | Claude session | #351 (merged) | not started |
| 11 | M7 testnet window (handoff §4 R4), validators and approved all-burn publication | host session | 2 to 7 | not started |
| 12 | A real model-driven battery agent campaign (paid, within the OD-5 provider ceiling) | host session | provider key; run plan in the handoff | not run |
| 16 | Battery challenge kit (`carbon/challenge_kit/battery.py`): the pinned PyBaMM overlay and the public population in the miner research image, with miner seeds only; closes the battery `generate` gap (OWNER-RESEARCH-ENVIRONMENT-01) | Claude session | — | open gap, declared in `challenge_kit/standard.py` |
| 17 | Tier 3B, the leak ladder: pre-registered in `BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2_AMENDMENT_4.md`; four campaigns, one per feedback rung, USD 2.00 of the USD 2.50 held | owner, then Claude session | owner approval of amendment 4 (D9 item 1). Batches (D9 item 2) approved 2026-09-30: `pscreen-T03`-`T05` and `pfinal-T01` prepared, references solving | pre-registered, not run |
| 18 | Battery intake (OD-7(b)): built, loopback only (`carbon/battery/intake.py`, `intake_client.py`); design for the mainnet switch in `BATTERY_MINER_SUBMISSION_PATHS.md` | owner (exposure), Launchpad (campaign seam) | the §4 security review decision, recorded as an `OWNER-…INTAKE-EXPOSURE-NN` record, before any non-loopback bind; Launchpad posts through `intake_client` | built, NOT SECURITY_QUALIFIED, not exposed |
| 20 | Owner decision: whether to propose a decision-aware component for the battery exam, prospectively, on the EV2 evidence (it removes the boundary-optimist blind spot; it did not rank real models better on this panel) | owner | EV2 results | open |
| 21 | EV3 design competition: freeze the pre-registration after the owner ranks its candidate problems (EV3 doc §6) and sets problem D's capacity floor | owner, then Claude session | EV2 results | draft for owner review |
| 13 | Charging time to a target SOC (reference v2, surrogate output, re-solved references) | Claude session | owner go-ahead | designed only (EV1 doc §7) |

## Budget (OD-5)

| Ceiling | Total | Spent | Remaining |
|---|---|---|---|
| RunPod | 14.00 | 0.00 | 14.00 |
| Model provider | 6.00 | 0.00 | 6.00 |

## Done (evidence merged)

| Item | PR |
|---|---|
| M1 construction contract | #348 |
| M2 exam, truth and seed services; M5A challenge-scoped MCP research | #349 |
| M3 validator daemon, one evaluation path, battery agent, review fixes | #350 |
| M4P truth environment, runtime probe, `operate init`, OD-4a request, host handoff | #351 |
| EV2 engineering-value experiment (items 14 and 15): 560 references, 15 members. H2 PASS: every decision-aware rule ranks the boundary optimist below all 14 eligible members, while the current rule ranks it at or above all 14. H1: verification tau 0.202 for the development-chosen rule against 0.298 for the current rule; indicative only | the EV2 PR |
| EV1 engineering-value experiment: contract, run, results (the approved rule gives weak, indicative decision alignment; tau 0.165 on verification) | the EV1 PR |

## Never without its exact record

- Any chain write (OD-4a/OD-7 records).
- Any RunPod pod (fresh balance, journaled ID, verified termination).
- Changing a runtime pin.
- Winner weights (OD-4b).
- Changing the approved exam rule.
