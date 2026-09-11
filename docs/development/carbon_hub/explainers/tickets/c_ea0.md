# C-EA0: Evidence capture contract

**Wave:** C

**Map ref:** `WAVE-C/C-EA0`

**Status:** DONE

**Target phase:** C1

## What and why

Specify EvidenceCaptureProfile, ArchiveEntry, ArtifactManifest, EvidenceUseAssessment, attempt dispositions, custody zones, required-artifact completeness and acknowledgement semantics using existing result owners.

A recorded result reference is not durable evidence; finalization must fail closed when required capture or acknowledgement is missing without relabeling infrastructure failure as physics failure.

## What it adds

An exact versioned documentation contract and machine-checkable case matrix for immutable attempt accounting, five independent axes, explicit missingness/dependence/unknowns and positive acknowledgement conditions.

## Placement and handoff

- **Depends on:** C-AUTH1, C-01, B-GATE
- **Feeds:** C-EA1
- **Driver:** Codex + evidence architecture
- **Review route:** Execution + Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

No archive implementation, invented retention period, custody deployment, scientific value, result owner, qualification, public network or LIVE authority.

## Current stage

Accepted head 62fbaad81081d87e70c8f438642b6529b6f93aff passed canonical run 34455987632 and merged in PR #131 as a3ca8cd111689329832131eac1460d579c7828b3.

## Maturity ceiling

Specified and contract-tested evidence-capture semantics only; archive implementation, durability acknowledgement, retention, custody, qualification and production remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/tickets/C-EA0_evidence_capture_contract.md)
- [Program authority](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/plans/C1_C2_BURGERS_PROGRAM.md)
- [Evidence capture contract](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/Design_Specs/Evidence_Archive_and_Custody.md)
- [Machine-checkable contract cases](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/Design_Specs/evidence_capture_contract_v1.json)
- [Stable evidence](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/evidence/wave_c/c-ea0.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/8757ef71e90a93ebdd28a1501352430774676e18/.agent/WAVE_C.md)

> C-EA0 reserves unsupported durability, required-artifact, retention, legal/IP, custody/key, deployment, capacity, recovery and security decisions as HUMAN_INPUT rather than inventing defaults.
