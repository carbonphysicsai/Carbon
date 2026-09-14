# C-EA1: Durable evidence archive

**Wave:** C

**Map ref:** `WAVE-C/C-EA1`

**Status:** IN_PROGRESS

**Target phase:** C1

## What and why

Preserve the accepted synthetic runtime and alpha policy while implementing one concrete, unprovisioned AWS provider/deployment/recovery package.

The alpha path needs exact provider adapters, private resource shapes, identities, roles, capacity accounting, recovery procedure and priced authorization inputs before external deployment can be considered.

## What it adds

Pinned S3/KMS/RDS adapters, exact object-version receipts, fresh IAM database tokens, atomic one-evaluation/20 GiB retained-byte capacity, private CloudFormation, least-privilege roles, component/source-use manifests, rollback/recovery commands and a sourced cost model.

## Placement and handoff

- **Depends on:** C-EA0
- **Feeds:** C-EA2
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

It cannot issue a real acknowledgement or satisfy C-EA2, and supplies no provider deployment, recovery proof, independent security acceptance, protected admission, production, network or LIVE authority.

## Current stage

After accepted C-10 PR #173, C-EA1-D3 selects an unprovisioned AWS private-alpha package: bounded S3/KMS/RDS adapters, exact object versions, atomic retained-byte capacity, private infrastructure, roles, recovery procedure and priced operating proposal. No provider deployment, recovery claim, real acknowledgement or C-EA2 authority exists.

## Maturity ceiling

Synthetic acknowledgement remains tested only in its accepted fixture scope. The alpha profile is specified and implemented as fail-closed preparation; real acknowledgement, durability/recovery, security, protected, production, network and LIVE maturity remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/.agent/WAVE_C.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/.agent/evidence/wave_c/c-ea1.md)
- [Synthetic archive runbook](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md)
- [Private-alpha preparation runbook](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/docs/development/EVIDENCE_ARCHIVE_ALPHA_PROFILE.md)
- [AWS private-alpha package](https://github.com/carbonphysicsai/Carbon/blob/246abc1cc823161da9366fce94e7edfdfa622832/docs/development/EVIDENCE_ARCHIVE_AWS_PRIVATE_ALPHA.md)

> The accepted synthetic acknowledgement and configuration-only alpha doctor are unchanged. The D3 package can be reviewed without credentials; actual account services, rehearsal, security acceptance and deployment authorization remain required.
