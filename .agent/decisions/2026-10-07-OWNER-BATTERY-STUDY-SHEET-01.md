## 2026-10-07 — OWNER-BATTERY-STUDY-SHEET-01: the battery training budget study sheet and its grant, for testing

**Authority.**
- **The sheet.** The owner, 2026-10-07, relayed by the Test Lead: "team
  proposes all rows, I approve it for testing". This covers the battery
  training budget study sheet: the template's rows plus the study evaluation
  and confirmation set sizes (#738).
- **The grant.** The owner, 2026-10-07: "approve study grant USD 31.54". The
  Test Lead relayed it, and the owner confirmed it directly in the Test
  Engineer's session ("Approve USD 31.54").

**What is recorded.**
1. **The sheet:**
   `carbon/training_budget/sheets/battery-fastcharge-ageing-development-v1.json`.
   - **Status:** every value is TEAM-PROPOSED and OWNER-APPROVED FOR TESTING
     (`TEAM_PROPOSED_OWNER_APPROVED_FOR_TESTING`), never production. Each
     value carries a one-line rationale.
   - **The study seed root** stays unset until the producer creates it on the
     VM and records its commitment (#738). Until then every phase is refused.
2. **Two new sheet fields:** `study_eval_size` (200) and `confirmation_size`
   (120). The template gains both rows, plus a `status` and a per-value
   `rationale`.
3. **The grant:**
   `docs/development/training_budget_study/grants/TRAINING-BUDGET-GRANT-BATTERY-STUDY-01.json`,
   with a ceiling of USD 31.54. Its study limits are in the `.limits.json`
   beside it:
   - an A40 rate cap of USD 0.492739726 an hour;
   - 64 pod-hours;
   - a pause at USD 25.23;
   - a re-estimate after Phase A.

   The arithmetic is in that folder's README. No balance or account
   identifier is recorded.
4. **A Phase B ladder fix.** A setting whose default is 0 (`polish_steps`)
   looped forever in `study._ladder`. Its ladder now starts at the study
   range's top divided by 16.

**Not production.** No production budget, TRAIN size, margin or ceiling is set
here. The study's results go to the owner as before (runbook steps 9 and 12).
