# B-E2: Julia and reference failure contract

**Wave:** B

**Map ref:** `WAVE-B/B-E2`

**Status:** TODO

**Target phase:** WB-2

## What and why

Implement the complete typed reference outcome and failure contract for Julia and other registered reference paths.

A required truth service can diverge, time out, disagree, or become unavailable. Carbon must preserve those failures instead of silently substituting a score or a different reference.

## What it adds

Fail-closed reference failure semantics and fixtures.

## Placement and handoff

- **Depends on:** B-04
- **Feeds:** B-GATE
- **Driver:** Codex + SciML
- **Review route:** SciML
- **Master questions:** MQ-004

## Explicit non-goals

It does not permit an unregistered fallback or relabel infrastructure failure as candidate science.

## Current stage

No more specific stage is supported; use the captured status and repository evidence.

## Maturity ceiling

Planned on the controlling board; not current implementation permission.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/a785799d6de2715ed3993a744ac16b7c7a572638/.agent/tickets/B-E2_reference_failure.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/a785799d6de2715ed3993a744ac16b7c7a572638/.agent/WAVE_B.md)

> This explainer describes placement and purpose. The linked ticket, domain contract, PR, review, and evidence record own exact implementation detail.
