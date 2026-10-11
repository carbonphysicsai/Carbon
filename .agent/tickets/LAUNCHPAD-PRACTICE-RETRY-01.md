# LAUNCHPAD-PRACTICE-RETRY-01: miner setting to auto-retry an interrupted practice

**Status:** DEVELOPMENT working contract. **Authority:** Test Lead decision,
2026-10-11. **Maturity ceiling:** tested Launchpad miner-local behaviour. No
chain, validator, exam-rule, gate or economic change.

## Decision

Observed 2026-10-11 on carbon-fresh: a practice was RUNNING when the lane's
Control Center restarted. Recovery set the campaign back to READY with
`last_refusal` `operation_interrupted` (practice), and nothing retried it. The
Test Lead's ruling: "it is the miner's compute, so it is the miner's choice."

## Scope

1. **Setting, off by default.** Optional runner-profile field
   `practice_auto_retry` (boolean). Setup's Review sets it
   (`carbon_setup_review` / the browser's Review form, field
   `practice_auto_retry`). Review writes it into the profile only when it is
   on. Without the field a profile reads and behaves exactly as before. Setup
   keeps the choice in its record so an update's Review keeps it. Both doors
   show it under `preferences`.
2. **Auto-retry.** When the setting is on, a supervisor that has just taken
   the lock and recovered a practice a dead process left RUNNING queues that
   practice again with the same recorded request (recipe, hypothesis,
   expected effect). It gets a fresh trial identity, because the old one is
   bound in the ledger to the lost attempt. This happens only when the
   campaign settled READY with nothing queued.
3. **Cap.** A fixed engineering cap of 2 retries per interrupted practice
   (`supervisor.PRACTICE_RETRY_CAP`). Each retry records the first item's
   `seq` in the additive `launchpad_dispatch.retry_of` column, and the cap
   counts those rows, so the retry never loops.
4. **One-step resume.** If the practice is not auto-retried (the setting is
   off, or the cap is reached), `last_refusal` stays `operation_interrupted`,
   and its catalog step names the one call:
   `carbon_resume {campaign, retry_interrupted: true}`. On the browser this is
   Retry practice (`POST /api/v1/research/{id}/retry_interrupted`), and
   `recovery` offers `{action: retry_interrupted, operation: resume}`. A retry
   passes the practice's own gates again.

## Non-goals

- Freeze, submit and commit are never retried, automatically or through
  `retry_interrupted`, because they touch the chain or the validator.
- A practice refused for a typed reason (budget, revision, design, busy and
  so on) is never retried. Only `operation_interrupted` qualifies.
- Agent runs (`campaign_interrupted`) keep their existing resume path.

## Definition of done

Tests in `tests/cpu/test_launchpad_practice_retry.py` cover:

- Setting off: the practice is not retried, and the one-step resume works.
- Setting on: the practice is retried with the same request and stops after
  the cap.
- A typed refusal is never retried.
- Freeze and submit are never auto-retried.
- Existing profiles parse unchanged, and Review writes the field only when it
  is on.

The touched Launchpad suites and `tests/invariants` also pass.

**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. Hub impact: mapped detail
only. The Hub's purpose, placement, status, dependencies, authority, maturity
and primary links are unchanged.
