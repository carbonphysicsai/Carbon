# C-EA1: Durable evidence archive

**Wave:** C

**Map ref:** `WAVE-C/C-EA1`

**Status:** TODO

**Target phase:** C1

## What and why

Implement a separately versioned runtime archive contract with admission, stage journaling, immutable object writes, manifest verification, catalogue transaction, outbox and positive availability acknowledgement.

A real result cannot finalize safely until its required evidence is preserved and verified under an approved fault and custody model.

## What it adds

Nothing yet. C-EA1 is unstarted and input-blocked even after C-EA0 merges.

## Placement and handoff

- **Depends on:** C-EA0
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

No database, object store, key system, deployment, retention policy, security qualification, archive acknowledgement or finalization integration exists.

## Current stage

Unstarted and input-blocked after C-EA0 delivery. Selection still requires approved durability, required-artifact, retention, custody/key, deployment, capacity and security inputs.

## Maturity ceiling

Future archive implementation only; no archive, durability, security, production, scientific qualification or LIVE maturity is earned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/e45be8ae28e20c471983b7f96165eb45dcc03b9e/.agent/WAVE_C.md)

> C-EA1 cannot use test-vector policy references or infrastructure convenience as approval for real custody or durability.
