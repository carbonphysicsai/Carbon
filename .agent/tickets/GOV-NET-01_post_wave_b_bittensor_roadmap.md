# Ticket GOV-NET-01 — post-Wave-B Bittensor wiring roadmap

**Lane:** repository planning and governance; outside the active Wave-B implementation board
**Status:** `done` only after the conditional completion gate below
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`
**Exact base commit:** `7161fe3c4a04821b7f676ab006bd5d313d0442d2`
**Exact base tree:** `619e366dead2288ccfd312f54ad09f17f86a1c62`
**Plan:** `.agent/plans/GOV-NET-01_post_wave_b_bittensor_roadmap.md`
**Stable evidence:** `.agent/evidence/governance/gov-net-01.md`

This is a contract-only roadmap ticket. It does not select a Wave-C, Wave-H,
or Wave-I ticket, change the active Wave-B sequence, authorize Bittensor code,
or provide scientific, security, network, economic, LIVE, or production
qualification.

## Goal

Ratify one internally consistent post-Wave-B launch-critical path that keeps
Bittensor behind typed Carbon policy and adapter boundaries, proves temporary
winner-triggered direct weights only on testnet, and requires frontier-backed
treasury settlement before mainnet economic activation.

## Owner direction

```text
Wave B unchanged
→ Wave C0 network foundation
→ G2 LOCALNET_READY
→ Wave C1 real scientific vertical
→ Wave C2 temporary direct-weight testnet integration
→ G3 TESTNET_ALPHA_DIRECT_WEIGHTS
→ Wave D first scientifically qualified Challenge
→ G4 QUALIFIED_TESTNET
→ Wave H frontier promotion and finality
→ Wave I treasury routing and settlement
→ G6 TREASURY_SETTLEMENT_QUALIFIED
→ G7 MAINNET_MECHANISM_COMPLETE
```

Waves E, F, and G may proceed after Wave D in parallel and do not block the
H/I launch-critical branch. G5 may establish deployment readiness while
economic activation remains off. Direct score-to-weight mainnet beta is
superseded; mainnet economic activation requires the treasury path.

## Definition of Done

- [x] Record `OWNER-NET-01` as the durable owner-selected roadmap and preserve
      the supersession/conflict ledger.
- [x] Reconcile the Build Out, protocol extension, master plan, launch path,
      open-question register, architecture decisions/rationale, maturity
      ledger, defensibility register, and directly conflicting protocol
      shorthands.
- [x] Version the launch path prospectively and retain the old path as an
      explicit historical/superseded record rather than silently deleting it.
- [x] Specify the C0/C1/C2 decomposition, NET family, C-W1 through C-W4,
      G2 through G7, typed chain intents, exact testnet provenance, explicit
      no-winner sink behavior, H/I ownership, validator-service evidence, and
      testnet-to-treasury migration rehearsal.
- [x] Leave the reward-window duration, exact sink identity/custody, validator
      quorum/stake/audit policy, treasury custody implementation, settlement
      values, operational SLOs, and security acceptance explicitly open and
      human/evidence owned.
- [x] Classify the Development Hub change as map-structural and specify the
      authority-commit-A then Hub-commit-H pinning, bounded-source, and
      deterministic-regeneration contract. Commit H executes that contract.
- [ ] Obtain scope-required exact-head CI, exact-head Greptile review with all
      valid findings repaired and zero unresolved review threads, normal
      exact-expected-head merge, exact-main Merge gate success, and post the
      completed normalized external receipt.

## Conflict and supersession ledger

| Prior statement | Classification | Prospective resolution |
|---|---|---|
| Raw/lean score magnitude maps to weight magnitude | `MIGRATION_REQUIRED` | C2 uses Challenge-local eligible-leader transition only; mainnet uses frontier-backed treasury settlement. |
| Direct-weight mainnet beta may be an optional launch branch | `MIGRATION_REQUIRED` | Superseded by treasury-before-mainnet owner direction. |
| Wave H waits for Waves E/F/G | `DOCUMENTATION_LAG` | H follows D on the launch-critical branch; E/F/G are parallel and non-blocking. |
| A generic chain publisher accepts score dictionaries/results | `IMPLEMENTATION_LAG` | Future publisher accepts only nominal typed intents from Carbon policy owners. |
| Omitted/invalid weights represent no winner | `NEW_OWNER_DECISION_REQUIRED` resolved structurally | An approved non-paying sink is required; exact identity/custody remains reserved. |
| Bittensor transport becomes the Miner MCP | `NO_CONFLICT` after clarification | Bittensor identity/discovery and authenticated transport wrap the Carbon Miner MCP. |
| Treasury receiver means one preselected custody topology | `NEW_OWNER_DECISION_REQUIRED` | Treasury receiver/vault boundary is required; exact custody topology remains security/economic-owner selected. |

## Must not

Do not implement any runtime; modify the active Wave-B ticket order/status;
select C/H/I work; invent network, scientific, security, or economic values;
expose the official exam; let SDK objects enter scoring authority; let a
caller-selected Boolean cross the economic boundary; or imply that a testnet
weight proves Wave-D qualification, frontier advance, settlement, or mainnet
readiness.

## Conditional completion gate

The ticket is authoritatively `done` only when the exact reviewed candidate
normally merges with reviewed-tree preservation, exact-main `Merge gate`
succeeds, and the completed normalized external receipt is posted. Dynamic
head, check, Greptile, merge, and receipt identities remain external evidence.
The repository's active implementation selection remains B-04 throughout.

```text
SPECIFIED: YES
OWNER_DIRECTION / RATIFIED_ROADMAP: YES after merge under current governance
BITTENSOR_IMPLEMENTED: NO
TESTNET_WEIGHTS_IMPLEMENTED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
TREASURY_IMPLEMENTED: NO
ECONOMICALLY_QUALIFIED: NO
LIVE: NO
MAINNET: NO
PRODUCTION_QUALIFIED: NO
```
