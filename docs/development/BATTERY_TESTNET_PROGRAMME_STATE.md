# Battery testnet programme: current state

**This is the single record of open work** for the battery testnet track
(parent #341) and its engineering-value experiments. Nobody, human or agent,
should depend on a conversation's memory.

**Update rule:** every PR in this track updates this file in the same PR:
- move finished rows to "Done";
- add any new open item it creates;
- keep the "Last updated" line current.

A row is done only when its evidence is merged or recorded here.

**Last updated:** 2026-10-03. Row 24: EV5 optimizer and H2 bootstrap settled (OWNER-EV5-Q2-01, OWNER-EV5-Q4-01); only the sealed confirmation batch remains.

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
| 10 | M5b Launchpad battery UI; M6 control center | Claude session | #351 (merged) | built as the Challenge-neutral Control Center: C-MLP-03 setup and C-MLP-04 (install, no operator file, Challenge choice); live fresh-machine run pending |
| 11 | M7 testnet window (handoff §4 R4), validators and approved all-burn publication | host session | 2 to 7 | not started |
| 12 | A real model-driven battery agent campaign (paid, within the OD-5 provider ceiling) | host session | provider key; run plan in the handoff | not run |
| 17 | Tier 3B, the leak ladder: pre-registered in `BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2_AMENDMENT_4.md`; four campaigns, one per feedback rung, USD 2.00 of the USD 2.50 held | Claude session | **approved 2026-10-01** (OWNER-BATTERY-3B-AND-EXPOSURE-01); runs on the v1 deployment as pre-registered, no v2 re-registration; `pscreen-T04`/`T05` prepared with complete references | **run 2026-10-01**: all four rungs FOUND (prediction confirmed), USED at rungs 3-4 by the mechanical rule with a stated limit; results in `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md` §9 |
| 18 | Battery intake (OD-7(b)): built (`carbon/battery/intake.py`, `intake_client.py`); design for the mainnet switch in `BATTERY_MINER_SUBMISSION_PATHS.md` | owner (exposure), operator (bind) | OWNER-INTAKE-EXPOSURE-01 recorded 2026-10-02: a public bind names it and terminates TLS in the intake; Launchpad posts through `intake_client` | built, exposure approved for testnet 567; binding a public host is the operator's step |
| 19 | Battery exam rule v2 (`exam.DEVELOPMENT_RULE_V2`): one scored submission per hotkey per tempo, block-based rotation, never stalls; the deployment selects it with `"rule": "v2"` on a fresh root | Claude session; Launchpad for the research disclosure | this PR; a fresh v2 deployment with its own batches; zero hidden-batch exposure to miners (OWNER-BATTERY-3B-AND-EXPOSURE-01 item 2): nothing computed from a hidden batch reaches a miner until Carbon releases it to the training pool | v2 seals hidden-batch results from miners (`exam.MINER_DISCLOSURE`, `daemon.outcome`), outside the scoring digest, so the prepared v2 deployment and its solved references stay valid; built and tested; deployment held |
| 20 | Owner decision: whether to propose a decision-aware component for the battery exam, prospectively, on the EV2 evidence (it removes the boundary-optimist blind spot; it did not rank real models better on this panel) | owner | EV2 results | **decided 2026-10-01** (OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01): registered as a prospective proposal (`value/proposal.py`), not deciding; both rankings reported; EV4 would settle it, not run |
| 21 | EV3 design competition: freeze the pre-registration after the owner ranks its candidate problems (EV3 doc §6) and sets problem D's capacity floor | owner, then Claude session | EV2 results | draft for owner review |
| 23 | Near-limit optimism admissibility gate (`carbon/battery/value/admissibility.py`) (TRACK-B-STUCK-01 outcome, 2026-10-03) | owner (testnet use) | cutoff set 2026-10-03: `THRESHOLD_BANDS = 2.0` (OWNER-GATE-CUTOFF-01, provisional DEVELOPMENT value); evidence in `evidence/admissibility-optimism-2026-10-03/` | active for value-study results only; confirmed once in EV5; putting it in the testnet rule is a separate approval |
| 24 | EV5: the battery Level 0 combined admission run (OWNER-ADMISSION-COMBINED-01); confirms the deciding rule, the SR-2 candidate and the gate once on fresh conditions | lead session | spend approved (OWNER-EV5-CAP-01: option A, cap USD 6, inside the USD 25 L0 cap); cutoff set (23); pre-freeze engineering built (#536); freshness, confirmation host, optimizer and H2 bootstrap decided (OWNER-EV5-Q1-01 to -Q4-01); remaining: the sealed confirmation batch, made and solved on the operator host | draft pre-registration (`BATTERY_ENGINEERING_VALUE_EV5.md`); nothing dispatched |
| 25 | Track A construction integrity at Level 0 (CI-BATTERY-L0-01) | Claude session | the scoring precondition (24) | harness families and worker-boundary attacks built; INCONCLUSIVE until the value precondition is resolved (OWNER-TRACK-A-L0-02 item 6) |
| 26 | A measurement for the localized sign-error failure, which no tested rule or the mean-optimism gate catches | SciML/technical lead (amend or accept); cutoff HUMAN_INPUT | 24 | commissioned 2026-10-03 (OWNER-EXEC-APPROVALS-01): near-limit false acceptance (`value/false_acceptance.py`) built, descriptive; sign-error control 0.95, other controls 0 (`evidence/near-false-acceptance-2026-10-03/`); proposed as EV5's H3 measurement; real members unmeasured until EV5 |
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
| EV4 (100-member panel) and the Problem-C design optimizer (item 22): 840 references, 99 eligible members; H1 UNRESOLVED; Problem C's chosen protocols showed no in-band violation, and Mode X emitted 29 in-band findings | the EV4 PR |
| Scoring-ratio studies SR-1, SR-2 and SR-3 on EV2 and on EV4 (regenerated, content-verified predictions): NO_PROMOTION; the deciding rule is kept for ranking (TRACK-B-STUCK-01 outcome, 2026-10-03) | #512, #513, #514, #515 |
| Battery challenge kit (item 16) | #505 |
| Track A Level 0 harness: attack catalogue, detectors, specimens, controls | #506 |
| EV1 engineering-value experiment: contract, run, results (the approved rule gives weak, indicative decision alignment; tau 0.165 on verification) | the EV1 PR |

## Never without its exact record

- Any chain write (OD-4a/OD-7 records).
- Any RunPod pod (fresh balance, journaled ID, verified termination).
- Changing a runtime pin.
- Winner weights (OD-4b).
- Changing the approved exam rule.
