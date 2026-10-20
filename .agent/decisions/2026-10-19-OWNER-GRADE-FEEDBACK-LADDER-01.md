# OWNER-GRADE-FEEDBACK-LADDER-01: miner feedback from grades, η = 0.02 (cap C superseded to 20)

Date: 2026-10-19
Status: APPROVED by the owner ("Approve both. We have to make sure we have the right data and right questions for the exam."). Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Implementation:
- **The document builder is built** in `carbon/scoring/grade_feedback.py`, at `claude/grade-feedback-ladder` `570189455`:
  - an allow-listed document;
  - total, A and D floored to max(0.02, rebuild noise);
  - the ladder per exam version;
  - gate names from the registry only;
  - NOT_SCORED with no numbers for any result that doesn't count.
- **Not yet built:** storing each miner's best document and serving the documents to miners. Until that's built, no private-exam feedback reaches miners.
Design: `codex-queue/reports/RECIPE_GRADE_DISCLOSURE_PROPOSAL_20261019.md`.

## Decided

- **Public practice exam:** full detail.
- **Private (sealed) exam:** only the total, A and D, rounded to **η = 0.02**, under the **Ladder rule**.
  - A miner's shown private result updates only when a grade beats that miner's previous best total by at least the step. Otherwise it reads "no improvement".
  - The step is max(η, the Challenge's measured rebuild noise).
- **Gate failures** are named from the closed registry only.
- **Never shown from the private exam:** per-case values, which cases failed, the design picked, references.
- **Per-miner cap: C = 10 graded submissions per sealed exam version.** *Superseded the same day by OWNER-EXAM-CAP-ROTATION-01: C = 20 with daily rotation.*

## Wear

The worst case per miner per exam version is C × 1 + min(C, 1/η) × 3·log₂(1/η) ≈ **179 bits**; typically about 10. Exams with few cases (F02 and F08, 8 each) wear faster per bit than Motor (48).

**Not decided here:** the rotation trigger, the wear budget and the maximum age.
