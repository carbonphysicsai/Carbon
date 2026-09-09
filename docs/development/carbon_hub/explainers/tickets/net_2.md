# NET-2: Authenticated application transport and durable receipts

**Wave:** C

**Map ref:** `WAVE-C/NET-2`

**Status:** IN_PROGRESS

**Target phase:** C0

## What and why

Wrap SDK btauth/1 and the unchanged seven-tool MCP core with contextual messages and a bounded durable replay journal.

A hotkey signature must remain bound to the exact network, challenge, snapshot and request without becoming scientific authority.

## What it adds

Canonical v1 ingress, SDK signatures, durable nonce/request receipts, identity and time watermarks, and precise bounded failures.

## Placement and handoff

- **Depends on:** NET-1
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + network/protocol engineering
- **Review route:** Network/protocol + security
- **Master questions:** MQ-054, MQ-056

## Explicit non-goals

No evaluator, accepted flag, public listener, public deployment, weight publication, scientific/security qualification or LIVE authority.

## Current stage

NET-2 candidate implemented with native diagnostics; canonical SDK/MCP acceptance and merge remain pending.

## Maturity ceiling

Local development implementation only; no scientific, security, network or production qualification.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/134280e39db0d5dfa3d4ce5e1f07fbea1b226994/.agent/tickets/NET-2_authenticated_transport.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/134280e39db0d5dfa3d4ce5e1f07fbea1b226994/.agent/evidence/wave_c/net-2.md)
- [Transport contract](https://github.com/carbonphysicsai/Carbon/blob/134280e39db0d5dfa3d4ce5e1f07fbea1b226994/docs/development/AUTHENTICATED_TRANSPORT.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/134280e39db0d5dfa3d4ce5e1f07fbea1b226994/.agent/WAVE_C.md)

> Transport authenticates who supplied bytes; existing owners still decide admission, scoring and disclosure.
