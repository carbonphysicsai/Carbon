# C-EP2: Variant-A measurement and offline Variant-B decision

**Wave:** C

**Map ref:** `WAVE-C/C-EP2`

**Status:** DONE

**Target phase:** C1 development

## What and why

Run a private, repeatable observation harness on C-EP1 and analyze zero-fill-wait, already-admitted compatibility groups in a detached counterfactual replay.

Reference sharing should be considered only after Carbon can separate measured singleton work from missing physical phases and modeled assumptions, including added closure delay and B overhead.

## What it adds

A frozen observation protocol, public-safe and private traces, persistent success/failure/retry/restart accounting, an exact C-01 claim repair, detached assumption-conditioned A/B replay, profiler summary and owner-facing decision report.

## Placement and handoff

- **Depends on:** C-EP1
- **Feeds:** C-EP3
- **Driver:** Codex + measurement/execution engineering
- **Review route:** Execution + scientific integration + data/security
- **Master questions:** MQ-048, MQ-051

## Explicit non-goals

No shared membership, fill wait, early result, public answer, production entropy, real reference/backend, reward route, scientific/security qualification, real finalization, public network, production or LIVE authority is supplied.

## Current stage

Completed in bounded DEVELOPMENT scope after corrected head 89f06eda74b15dd336e57a512f228c6b37cca77d passed RUNTIME_FULL run 34718392697 and normally merged in PR #144 as 96099aeac9e5022bda9d94730b1d7d955cb6c1d5.

## Maturity ceiling

Specified, implemented and locally tested only as DEVELOPMENT measurement and detached replay tooling. Observations and simulations are unqualified supporting evidence; Variant B runtime and every scientific, reference, security, archive, reward, network, production and LIVE qualification remain unavailable.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/7fbf13ebb2629d738432069ee48a88737dcf3242/.agent/tickets/C-EP2_variant_a_measurement_and_b_decision.md)
- [Stable measurement evidence](https://github.com/carbonphysicsai/Carbon/blob/7fbf13ebb2629d738432069ee48a88737dcf3242/.agent/evidence/wave_c/c-ep2.md)
- [Owner-facing decision report](https://github.com/carbonphysicsai/Carbon/blob/7fbf13ebb2629d738432069ee48a88737dcf3242/docs/development/C_EP2_VARIANT_B_DECISION_REPORT.md)
- [Study runbook](https://github.com/carbonphysicsai/Carbon/blob/7fbf13ebb2629d738432069ee48a88737dcf3242/docs/development/C_EP2_STUDY_RUNBOOK.md)
- [Wave C board](https://github.com/carbonphysicsai/Carbon/blob/7fbf13ebb2629d738432069ee48a88737dcf3242/.agent/WAVE_C.md)

> The recommendation is COLLECT MISSING INPUTS FIRST. A8 measures no physical reference or candidate inference, B overhead and compatible demand are unknown, and the offline replay implements no sharing.
