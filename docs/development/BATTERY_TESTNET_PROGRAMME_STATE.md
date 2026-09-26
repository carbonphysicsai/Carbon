# Battery testnet programme: current state

**This is the single record of open work** for the battery testnet track
(parent #341) and its engineering-value experiments. Nobody, human or agent,
should depend on a conversation's memory.

**Update rule:** every PR in this track updates this file in the same PR:
- move finished rows to "Done";
- add any new open item it creates;
- keep the "Last updated" line current.

A row is done only when its evidence is merged or recorded here.

**Last updated:** 2026-09-25, with PR #351 (BATTERY-TESTNET-M4P).

## Authority in force

| Record | What it settles |
|---|---|
| OWNER-BATTERY-TESTNET-01 (OD-1 to OD-8) | challenge, exam rule (OD-2), security review (OD-3), all-burn Phase A (OD-4a), no winner weights (OD-4b), USD 20 budget (OD-5), no validator hotkeys (OD-6), miner commitments (OD-7), per-challenge contracts (OD-8) |
| OWNER-BATTERY-TESTNET-02 / -03 | research vocabulary; exclusion scope; the battery agent; M3 direction |
| OWNER-BATTERY-TESTNET-04 | prior spend excluded (USD 20 intact); GPU image = `carbon-accelerator-worker@sha256:e4a2…`; OD-3 recorded approved |
| Engineering-value direction (2026-09-25) | EV1 is off-chain DEVELOPMENT; the testnet rule is unchanged until a prospective change is approved |

All of these are in `.agent/DECISIONS.md`.

## Open work

| # | Item | Owner | Depends on | State |
|---|---|---|---|---|
| 1 | Merge PR #351 (M4P: truth environment, runtime-471 probe, OD-4a request) | Claude session | green Merge gate | CI running |
| 2 | Host steps, the complete procedure in handoff §0: doctor, truth-materialize, truth-verify, runtime probe, service key, deployment, `operate init`, and a draft OD-4a request | host session on the authorized WSL host | 1 | not started |
| 3 | Decide whether to adopt runtime spec 471 (the live operator config pins 458), from the probe report | owner | 2 | open |
| 4 | Approve the exact OD-4a `request_digest`, regenerated from a fresh probe just before dispatch (the step 2 draft is for format review only); one publication per record | owner | 2, 3, 7 | open |
| 5 | EV1: 384 pinned-PyBaMM reference solves, then panel reconstruction, evaluation, report and PR | Claude session | — | solves in progress (local, resumable) |
| 6 | M4: GPU backend for the daemon (device-attached carrier, host admission, device lease) | Claude session | 1 | not started |
| 7 | M4: two-host RunPod reproducibility run (handoff §4 R2, R3) | host session | 6; fresh balance and active-pod check | not started |
| 8 | M3 gaps: two-instance commit-reveal cross-check; chain `CommitmentReader`; retired-case release policy | Claude session | — | not started |
| 9 | OD-7 commitment posting (count per day, window, fee cap and expiry need owner values) | Claude session + owner | 8 | not implemented |
| 10 | M5b Launchpad battery UI; M6 control center | Claude session | 1 | not started |
| 11 | M7 testnet window (handoff §4 R4), validators and approved all-burn publication | host session | 2 to 7 | not started |
| 12 | A real model-driven battery agent campaign (paid, within the OD-5 provider ceiling) | host session | provider key; run plan in the handoff | not run |
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

## Never without its exact record

- Any chain write (OD-4a/OD-7 records).
- Any RunPod pod (fresh balance, journaled ID, verified termination).
- Changing a runtime pin.
- Winner weights (OD-4b).
- Changing the approved exam rule.
