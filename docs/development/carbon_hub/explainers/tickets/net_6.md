# NET-6: Disposable operator lifecycle and recovery

**Wave:** C

**Map ref:** `WAVE-C/NET-6`

**Status:** IN_PROGRESS

**Target phase:** C0

## What and why

Explicit configuration, external keys, exclusive process ownership, health and consistent private backup/restore.

A tested publication function needs honest lifecycle and recovery controls before local operation can be reproduced.

## What it adds

Guarded operator CLI, retained private configuration, restart-safe node startup, bounded health, OS lease and no-overwrite restore.

## Placement and handoff

- **Depends on:** NET-5
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Operations + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No public operation, treasury, real scientific archive, production custody or G2 readiness claim.

## Current stage

NET-6 actual all-burn operator rehearsal passed with node restart, external key startup, heartbeat, shutdown and complete logical backup/restore. Canonical delivery acceptance remains pending. Shared-winner runtime evidence is missing; G2 stays NOT_READY.

## Maturity ceiling

Disposable synthetic operations only. Missing shared-winner runtime evidence keeps G2 NOT_READY.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/9079c14a9398355408de0543ee558bbbf705884a/.agent/tickets/NET-6_network_operations.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/9079c14a9398355408de0543ee558bbbf705884a/.agent/evidence/wave_c/net-6.md)
- [Operator contract](https://github.com/carbonphysicsai/Carbon/blob/9079c14a9398355408de0543ee558bbbf705884a/docs/development/NETWORK_OPERATIONS.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/9079c14a9398355408de0543ee558bbbf705884a/.agent/WAVE_C.md)

> Stopped publishers do not clear stored chain weights; backups preserve pending liabilities and credit age.
