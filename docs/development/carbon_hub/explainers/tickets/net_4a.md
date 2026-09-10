# NET-4A: Nominal publication intents

**Wave:** C

**Map ref:** `WAVE-C/NET-4A`

**Status:** DONE

**Target phase:** C0

## What and why

Issue nominal localnet references backed by immutable reward projections and the existing journal.

Fixture results and caller flags must never acquire public-testnet or treasury authority.

## What it adds

Context-bound validity, supersession, changed-state/quarantine checks and explicit no-winner burn intents.

## Placement and handoff

- **Depends on:** C-REWARD
- **Feeds:** NET-4B
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No SDK signing, runtime burn proof, public transaction, treasury deployment, science/security qualification or LIVE authority.

## Current stage

NET-4A merged with canonical nominal-intent, provenance, validity and supersession tests (PR #124).

## Maturity ceiling

Local fixture intent software only; reserved public-family issuers remain unavailable.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/tickets/NET-4A_weight_intents.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/evidence/wave_c/net-4a.md)
- [Operator contract](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/docs/development/WEIGHT_INTENTS.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/WAVE_C.md)

> Intent expiry does not erase stored chain weights; NET-4B owns execution and recovery.
