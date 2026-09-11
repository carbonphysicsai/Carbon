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
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

It rejects real/customer/protected/official evidence and does not supply production retention, custody/KMS, replication, correlated-loss durability, availability, RTO/RPO, security qualification, real finalization or network eligibility.

## Current stage

PR #136 conditionally completes C-EA1 for the exact carbon.synthetic-evidence-archive.dev.v1 profile after applicable acceptance and normal merge. The synthetic acknowledgement is ineligible for real finalization, network use or qualification.

## Maturity ceiling

Specified, implemented and tested only for non-secret synthetic fixtures on one disposable host/tenant. No real archive durability, security, production, scientific qualification, network or LIVE maturity is earned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/WAVE_C.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/evidence/wave_c/c-ea1.md)
- [Synthetic archive runbook](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md)

> Only synthetic INTERNAL_AUDIT is eligible. The profile-scoped acknowledgement cannot satisfy real C1 finalization, C-W1, weights, settlement or qualification.
