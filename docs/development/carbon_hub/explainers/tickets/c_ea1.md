# C-EA1: Durable evidence archive

**Wave:** C

**Map ref:** `WAVE-C/C-EA1`

**Status:** IN_PROGRESS

**Target phase:** C1

## What and why

Preserve the accepted synthetic runtime, alpha policy and AWS v1 history while prospectively repairing the unprovisioned provider package as v2 for account-bound deployment and recovery review.

Retained encrypted evidence needs retained split keys, permissions matching executable calls, explicit private AWS API paths, retention from last eligible use/open obligations and a complete acknowledgement recovery watermark before an external rehearsal can be authorized.

## What it adds

Separate retained storage/envelope KMS keys; exact version, retention, context, IAM DB and restore-role policies; private S3/KMS/STS/Secrets Manager/Backup/Logs paths; PostgreSQL 17.11 Multi-AZ db.t4g.medium; closed account input schema; full-watermark verifier; corrected rollback and sourced USD 140.628 incremental/USD 155.022 complete estimates.

## Placement and handoff

- **Depends on:** C-EA0
- **Feeds:** C-EA2
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

It cannot issue a real acknowledgement or satisfy C-EA2, and supplies no AWS deployment, provider-observed IAM behavior, recovery proof, independent security acceptance, signer authorization, protected admission, production, network or LIVE authority.

## Current stage

After accepted PR #177, C-EA1-D4 selects a prospective AWS v2 correctness repair: retained split keys, exact IAM and private API paths, last-use/obligation retention, a complete recovery watermark, account-bound inputs and corrected costs. No provider deployment, observed recovery, real acknowledgement or C-EA2 authority exists.

## Maturity ceiling

Synthetic acknowledgement remains tested only in its accepted fixture scope. The alpha profile is specified and implemented as fail-closed preparation; real acknowledgement, durability/recovery, security, protected, production, network and LIVE maturity remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/.agent/WAVE_C.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/.agent/evidence/wave_c/c-ea1.md)
- [Synthetic archive runbook](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md)
- [Private-alpha preparation runbook](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/docs/development/EVIDENCE_ARCHIVE_ALPHA_PROFILE.md)
- [AWS private-alpha package](https://github.com/carbonphysicsai/Carbon/blob/c26585a03b0d6e4c7eaf1c36b42bfea9026d35c9/docs/development/EVIDENCE_ARCHIVE_AWS_PRIVATE_ALPHA.md)

> The accepted synthetic acknowledgement and configuration-only alpha doctor are unchanged. The prospective D4 package is a no-credentials execution handoff: account, region, network, execution location, IAM/custody principals, USD 175/month and USD 5 rehearsal approvals, observed full-watermark recovery, scoped security acceptance and signer authorization remain required.
