# NET-4B: Verified complete-vector publication and recovery

**Wave:** C

**Map ref:** `WAVE-C/NET-4B`

**Status:** DONE

**Target phase:** C0

## What and why

Compile complete reward targets against fresh identity/runtime capabilities and journal guarded SDK dispatch, finality, reveal and readback.

A valid preview can be rebuilt at execute time; ambiguous dispatch and stale stored weights cannot be treated as cleared payouts.

## What it adds

Pinned runtime burn checks, explicit quantization tolerance, final SDK integer/call guards, durable transaction identity and heartbeat/recovery.

## Placement and handoff

- **Depends on:** NET-4A
- **Feeds:** NET-5
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No actual localnet burn/epoch proof, public transaction, treasury deployment, scientific/security qualification or G2/LIVE authority.

## Current stage

NET-4B merged with canonical final-vector, SDK signing, durable dispatch and recovery tests (PR #125).

## Maturity ceiling

Disposable-localnet publication software only; actual runtime integration and G2 evidence remain NET-5.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/tickets/NET-4B_verified_publication.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/evidence/wave_c/net-4b.md)
- [Operator contract](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/docs/development/WEIGHT_PUBLICATION.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/46465565d2b09ce4485344d23b321dae9d9c653e/.agent/WAVE_C.md)

> A finalized commit is not reveal, and a stored row is not settlement. Shutdown can leave prior weights effective.
