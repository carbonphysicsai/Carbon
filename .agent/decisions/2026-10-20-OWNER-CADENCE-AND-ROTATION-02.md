# OWNER-CADENCE-AND-ROTATION-02: cadence follows rebuild capacity; exams rotate rarely

Date: 2026-10-20
Status: APPROVED by the owner. Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Supersedes, prospectively: OWNER-EXAM-CAP-ROTATION-01 (C = 20 per version with daily rotation).
Proposal: `codex-queue/reports/EXAM_ROTATION_RULE_PROPOSAL_20261020.md`, revision 2.
Implementation:
- **Built and approved** at `claude/cadence-final` `b4c599f9c`, landing with the step-2 recalibration.
- **The overfit check is measurable only where a case bootstrap works:** F08 1.1 today. For every other Challenge it's UNAVAILABLE, so only the 90-day limit rotates them. That's deliberate: it keeps the rule simple and never rotates falsely.
- **Until it lands,** the base still enforces C = 20 per version.

## Owner, verbatim

> submission cadence and exam rotation need to be dynamic and not fixed

> Need to be related to the sum of all challenges average rebuild time.

> why on earth would we need to turn the exam over that often with rounded scores and no exposed leader recipe.

> Yes. And we can version the exam when we want to look at different parts of the problem to build the best model card product.

## Decided

1. **Cadence:** each miner may make a = R ÷ (M × Σ t) graded submissions per Challenge per day, rounded down.
   - **R** is a validator's rebuild capacity in CPU-h a day, **M** is the number of active miners, and **Σ t** is the sum over Challenges of the rolling-mean rebuild time per graded submission, from the validators' receipts.
   - **Floor:** 1 a day. **Ceiling:** 1 per epoch.
2. **Rotation:** a sealed exam lives up to **90 days.**
   - **Weekly check:** the king is also graded on a fresh QA-passed draw.
   - **Early rotation:** if his sealed-exam total beats his fresh-draw total by more than **the registered margin plus 2 standard errors** of the exam total, the exam rotates early.
3. **There's no per-version per-miner cap.**
4. **Deliberate versions:** Carbon may also issue a new exam version on purpose, to probe different parts of the problem for the model-card product.
   - It's announced as a new evaluation version, and old results are never rescored.
   - The fairness controls of OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01 §3 apply: it never mutates an active batch, never targets a named miner, and never selects per-submission questions.

**Unchanged:**
- the Ladder disclosure (OWNER-GRADE-FEEDBACK-LADDER-01);
- the king's regrade on rotation;
- batch QA before any version goes live (`EXAM_BATCH_QA_SPEC_20261020.md`).
