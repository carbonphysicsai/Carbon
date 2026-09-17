# C-EA1: Durable evidence archive

**Wave:** C

**Map ref:** `WAVE-C/C-EA1`

**Status:** IN_PROGRESS

**Target phase:** C1

## What and why

Preserve the accepted synthetic runtime, alpha policy and unprovisioned AWS v1/v2 packages while deferring AWS deployment and spending. Keep provider-independent archive interfaces intact for a later bounded Hippius assessment.

The reviewable archive implementation remains useful historical preparation, but neither an unprovisioned package nor a provider preference establishes custody, retention, recovery or acknowledgement eligibility.

## What it adds

PR #180 accepted separate retained storage/envelope KMS keys; exact version, retention, context, IAM DB and restore-role policies; private AWS API paths; a closed account input schema; full-watermark verifier; corrected rollback and sourced cost estimates. Hippius is now recorded only as an unverified future preference.

## Placement and handoff

- **Depends on:** C-EA0
- **Feeds:** C-EA2
- **Driver:** Codex + evidence architecture
- **Review route:** Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

It cannot issue a real acknowledgement or satisfy C-EA2, and supplies no provider deployment, Hippius compatibility result, provider-observed IAM behavior, recovery proof, independent security acceptance, signer authorization, protected admission, production, network or LIVE authority.

## Current stage

PR #168's alpha preparation remains accepted at profile digest sha256:e7f9b86943d482ad5c0e92c386a6edf3cdc493049f912c88f7e5a25d5eb6f49c. PR #177 accepted AWS v1, and PR #180 accepted C-EA1-D4's unprovisioned AWS v2 manifest sha256:2bb9b7a668c776138e4dddf6a152226aa443c2c69cc6441ce085ff64f1cd75f2 at head a4395a3b3f7707fc9e2793e333cc5d101ea01c64, run 34915666663 and merge 1f9ead70c886f9d04804533eab3579083c4e358d. AWS deployment/spending are owner-deferred; Hippius is preferred but unverified. No provider deployment, recovery evidence or real acknowledgement exists.

## Maturity ceiling

Synthetic acknowledgement remains tested only in its accepted fixture scope. The alpha profile is specified and implemented as fail-closed preparation; real acknowledgement, durability/recovery, security, protected, production, network and LIVE maturity remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/.agent/tickets/C-EA1_durable_evidence_archive.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/Design_Specs/Evidence_Archive_and_Custody.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/.agent/WAVE_C.md)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/.agent/evidence/wave_c/c-ea1.md)
- [Synthetic archive runbook](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/docs/development/EVIDENCE_ARCHIVE_SYNTHETIC.md)
- [Private-alpha preparation runbook](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/docs/development/EVIDENCE_ARCHIVE_ALPHA_PROFILE.md)
- [AWS private-alpha package](https://github.com/carbonphysicsai/Carbon/blob/dcd4ecf918a066b36916fcb68f35c0b7a89a2863/docs/development/EVIDENCE_ARCHIVE_AWS_PRIVATE_ALPHA.md)

> The accepted synthetic acknowledgement and configuration-only alpha doctor are unchanged. The D4 AWS package is retained but deferred. A later Hippius milestone must assess its exact integrity, encryption/custody, retention/deletion/recovery, availability, cost, failure and acknowledgement behavior before selection; observed full-watermark recovery, scoped security acceptance and signer authorization remain required for any real provider.
