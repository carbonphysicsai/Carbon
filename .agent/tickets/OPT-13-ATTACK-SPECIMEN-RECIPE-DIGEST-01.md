# OPT-13 — recover a breached attack specimen

**Status:** working contract; DEVELOPMENT repair only. **Authority:** optimizer queue OPT-13, GRAPHITE-01 phase 4, `docs/development/graphite/PHASE4_ATTACKER.md`. **Base:** main `7f9d7a2fc99205b67d6e03393c68e1f85e716e58`. **Reviewer:** Graphite Testing Manager.

## Problem and bounded decision

The neutral verifier's default specimen writer assumes the full Graphite phase-3 recipe record. Battery's Level 2 declarative adapter returns its compiled reconstruction record, which lacks `recipe_digest`, so a recorded BREACHED verdict ends with `SPECIMEN_CHECK_FAILED`. This is an implementation mismatch, not a verdict on the L2 pool-sources check.

Keep the existing phase-3 bundle path for complete recipe records. For other registered adapters, write a versioned attack-only bundle of the construction, Carbon's rebuilt record, the artifact identity and the adapter contract. Rebuild it with the registered adapter and compare the exact record and artifact. The bundle grants no official or security authority. Failure remains a typed specimen refusal with raw journal digests; it never changes BREACHED to HELD or erases a finding.

Add a read-only campaign lookup and a `phase4 remint` command. It must bind session to `controller/campaign.sqlite3`, the completed `iteration-log.jsonl` entry, and a digest-checked finding evidence file; then locate the exact journalled attempt, verify its digests and recorded BREACHED artifact, and mint/check the specimen without rerunning the oracle, model, miner tool or reference solver. It writes only `attacker/specimens/`. A missing, redacted, changed or inconsistent source refuses with a typed code. Re-running the command is idempotent.

## Scope and evidence

Target `carbon/agent_campaign/attack/verify.py`, `carbon/agent_campaign/graphite/phase4.py`, focused tests and phase-4 operator docs. No change to `l2_pool_sources_and_weights`, its oracle, any grant, scoring, LIVE or hidden material. Use toy campaign fixtures shaped like the reported attempt; do not open the real campaign root. Existing phase-3 specimen behavior must remain compatible. Baseline focused tests could not collect in the available local WSL venv (`numpy` absent); canonical CI is required.

**Invariants:** fail closed on provenance mismatch, keep infra separate from attack outcome, protect withheld content, retain historical verdicts, and never count a specimen as security qualification. **Hub map_ref:** `WAVE-C/GRAPHITE-01`; no Hub edit because the Hub is retired by OWNER-WORKFLOW-SPEED-01 and purpose/placement/status are unchanged.

**Completion predicate:** toy re-mint fixture, malformed/protected/refusal and existing bundle regressions pass; canonical exact-head CI and Merge gate pass; one PR to main, exact-head handoff; Graphite Testing Manager triages the breach after the executor re-mints it. No live run or spend in this ticket.
