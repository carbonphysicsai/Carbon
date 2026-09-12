# C-EA1: Durable evidence archive

**Wave:** C

**Map ref:** `WAVE-C/C-EA1`

**Status:** DONE

**Target phase:** C1

## What and why

Implement a separately versioned runtime archive contract with admission, stage journaling, immutable object writes, manifest verification, catalogue transaction, outbox and positive availability acknowledgement.

The synthetic profile proves that acknowledgement follows exact required-artifact, policy, catalogue, key and current-object verification rather than an upload, pointer, row or digest.

## What it adds

A separately versioned closed runtime with pre-dispatch admission, PostgreSQL catalogue/migration and outbox, encrypted restart-safe journal, immutable loopback object storage, manifest/current-availability verification, idempotent effects, quotas and reconciliation.

## Placement and handoff

- **Depends on:** C-EA0
- **Feeds:** C-EA2
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

It rejects real/customer/protected/official evidence and does not supply production retention, custody/KMS, replication, correlated-loss durability, availability, RTO/RPO, security qualification, real finalization or network eligibility.

## Current stage

Done only for carbon.synthetic-evidence-archive.dev.v1 after accepted head a779af066f4bf9bc36b6d6ab23914fa19191e1de passed run 34558389185 and normally merged in PR #136 as 0e0714c8260ca482a0ba2b743b2eaefd50508da1. C-EA2 is not selected or implemented.

## Maturity ceiling

Specified, implemented and tested only for non-secret synthetic fixtures on one disposable host/tenant. No real archive durability, security, production, scientific qualification, network or LIVE maturity is earned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/1ebb255e8c135a7efb967cea6e96d572608a2f14/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/1ebb255e8c135a7efb967cea6e96d572608a2f14/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/1ebb255e8c135a7efb967cea6e96d572608a2f14/.agent/WAVE_C.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/1ebb255e8c135a7efb967cea6e96d572608a2f14/.agent/evidence/wave_c/c-ea1.md)
- [Synthetic archive runbook](https://github.com/carbonphysicsai/Carbon/blob/1ebb255e8c135a7efb967cea6e96d572608a2f14/docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md)

> Only synthetic INTERNAL_AUDIT is eligible. The profile-scoped acknowledgement cannot satisfy real C1 finalization, C-W1, weights, settlement or qualification.
