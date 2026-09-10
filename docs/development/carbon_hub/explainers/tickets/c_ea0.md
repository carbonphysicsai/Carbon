# C-EA0: Evidence capture contract

**Wave:** C

**Map ref:** `WAVE-C/C-EA0`

**Status:** TODO

**Target phase:** C1

## What and why

Specify EvidenceCaptureProfile, ArchiveEntry, ArtifactManifest, EvidenceUseAssessment, attempt dispositions, custody zones, required-artifact completeness and acknowledgement semantics using existing result owners.

A recorded result reference is not durable evidence; finalization must fail closed when required capture or acknowledgement is missing without relabeling infrastructure failure as physics failure.

## What it adds

A selected-next contract ticket with explicit missing human-owned durability, retention, legal/IP, deployment and custody inputs.

## Placement and handoff

- **Depends on:** C-AUTH1, C-01, B-GATE
- **Feeds:** No downstream ticket captured.
- **Driver:** Codex + evidence architecture
- **Review route:** Execution + Operations + data/security + scientific integration
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

No archive implementation, invented retention period, custody deployment, scientific value, result owner, qualification, public network or LIVE authority.

## Current stage

After C-AUTH1 delivery, ratify capture, custody, retention-class, completeness and durability-acknowledgement semantics before archive implementation.

## Maturity ceiling

Specified future evidence-capture contract only; archive durability, retention, custody, qualification and production remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/f46e76743913e3af36ed30275afc400d70aaf42e/.agent/tickets/C-EA0_evidence_capture_contract.md)
- [Program authority](https://github.com/carbonphysicsai/Carbon/blob/f46e76743913e3af36ed30275afc400d70aaf42e/.agent/plans/C1_C2_BURGERS_PROGRAM.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/f46e76743913e3af36ed30275afc400d70aaf42e/.agent/WAVE_C.md)

> C-EA0 must reserve unsupported retention, legal/IP, custody and durability decisions rather than invent defaults.
