## 2026-10-07 — OWNER-BANK-ARCHITECTURE-01: hidden batches drawn from pre-solved banks

**Authority.** The owner, 2026-10-07: "approve bank plan". The Test Lead
relayed it to the Carbon Validator session the same day.

The plan approved is:
- the Carbon Validator's bank model (its message to the Test Lead, 2026-10-07);
- Data Collection's quiz-load memo, §3 (`claude/quiz-load-memo`,
  `docs/development/evidence/battery-quiz-designs/quiz-load-v1/README.md`).

The owner's objective, recorded in the memo: "A path to all 8 challenges
that DRIVES the miners at learning the full distribution."

It supplements:
- OWNER-SHARED-ANSWER-KEY-01;
- OWNER-VALIDATOR-MAINNET-PARITY-01;
- OWNER-REHEARSAL-AND-RELEASE-01;
- OWNER-MOTOR-HIDDEN-POOL-01;
- OWNER-BATTERY-3B-AND-EXPOSURE-01.

**Scope** (VALIDATOR-23):
1. **Banks.** The producer solves each Challenge's hidden cases once, into
   banks:
   - a pool bank, drawn faithfully from P (Q = P);
   - steered quiz banks: Q2 near-limit, and Q3 per registered condition
     stratum.

   A bank grows in **tranches**. Each tranche is drawn from the producer root
   and committed to its journal before use, then solved, then sealed with a
   Merkle root over its cases and references.
2. **Windows.** Each rotation window's batch is a **seeded draw without
   replacement** from the live bank:
   - no case is shared with another batch active at the same time;
   - it is identical for every validator, because it is one signed package.

   The window's v2 commitment names the tranche roots it draws from.
   Validators verify each case's Merkle membership on import.
3. **Exposure.** Each draw of a case counts one exposure. At **E** exposures
   the case retires into the release queue. Retired cases are replaced by
   new tranches, so the live bank stays at **B**.
4. **Reporting.** Per-stratum reporting for the Q3 banks, and a coverage
   diagnostic: the P-mass of the input cells the live bank occupies, per
   registered stratum.
5. **The canary detector** for the CFD class (memo §1): every submission is
   scored, unreported, on a disjoint near-limit canary, and a submission is
   flagged by a one-sided test. Its alpha is HUMAN_INPUT.

**Testing values, owner-approved for development** (B as a multiple of the
window batch size n; E as appearances before retirement):

| Class | B | E | Notes |
|---|---|---|---|
| Cheap (CPU-minutes per case; battery) | 20n | 5 | Q3 stratified |
| Motor-like (about 0.6–1 core-h per case) | 10n | 10 | |
| CFD-class (core-hours per case) | 5n | 20 | with the canary |

**Rule versions.** Each Challenge takes these values in a **new rule version**
when it moves onto a bank. That is prospective (invariant 10). **Battery's
current first run continues unchanged** on rule v2.

**Order:** the bank core and battery first; motor once its design space is
revised. Cooling stays on hold (#752).

**Release, unchanged.** A case retired at E enters the existing release
queue. Publishing it to training stays the existing release decision
(OWNER-BATTERY-3B-AND-EXPOSURE-01; HUMAN_INPUT). This record approves
retirement into that queue, not automatic publication.

**Not granted here:**
- qualification, LIVE, reward or production claims;
- the canary's alpha;
- any change to an exam, gate, scale or population;
- adopting the quiz as a gate (rule v3 stays the owner's).
