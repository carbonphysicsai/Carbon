# B-E2: Julia and reference failure contract

**Wave:** B<br>
**Status:** TODO<br>
**Target phase:** WB-2

## What this ticket is

Implement the complete typed reference outcome and failure contract for Julia and other registered reference paths.

## Why it exists

A required truth service can diverge, time out, disagree, or become unavailable. Carbon must preserve those failures instead of silently substituting a score or a different reference.

## What it adds to Carbon

Fail-closed reference failure semantics and fixtures.

## Where it fits

- **Depends on:** B-04
- **Unlocks or feeds:** B-GATE
- **Driver:** Codex + SciML
- **Accountable review route:** SciML
- **Master questions:** MQ-004

## What it does not do

It does not permit an unregistered fallback or relabel infrastructure failure as candidate science.

## Current stage

Use the status and evidence links below for the captured state.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/.agent/tickets/B-E2_reference_failure.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/b86daa5d8b0f8b3e86bb82c2661f405747a200df/.agent/WAVE_B.md)

> This explainer describes placement and purpose. The linked ticket, domain contract, PR, review, and evidence record own exact implementation detail.
