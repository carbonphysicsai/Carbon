# VALIDATOR-26: battery rule v3, A-Q with the G-FEAS@0.05 gate, on the validator

**Status:** plan. The decision record OWNER-BATTERY-SCORE-RULE-01 is in this
PR. Security-sensitive (it changes what the validator scores and nominates).
It needs a dedicated review.

**Authority:**
- OWNER-BATTERY-SCORE-RULE-01 (owner, 2026-10-08, confirmed directly in the
  Carbon Validator session);
- OWNER-GRAPHITE-TEST-WAVE-08;
- OWNER-BANK-ARCHITECTURE-01.

It applies from rehearsal 3b. 3a stays on the rule in force.

**Executor:** the Carbon Validator session.

## Design

1. **Rules `v3` and `v3-bank`** (`exam.RULES`): v2 and v2-bank, plus a
   `score` term naming exactly the adopted candidate:
   - `{"candidate": "G-FEAS/A-Q", "cutoff": 0.05}`;
   - registry v4's sha256;
   - the legs `{a: 0.5, q: 0.5}` and the gate `feasibility ≤ 0.05`.

   They are pinned in the rule document, so the rule digest binds them. v2
   and v2-bank are untouched.
2. **The legs, computed exactly as the tuning study computed them.** The
   validator calls the same `score_tuning` functions (`member_legs`, the
   gate measures) on a submission's stored predictions. A second
   implementation could drift from the evidence the owner adopted.
   - **`a`:** accuracy, on the active pool's screening cases.
   - **`q`:** Q3 decision regret, on the Q3 scenarios of the active
     screening batches' quizzes, settled with their refined references.
     - Under v3, every screening batch must carry a quiz. The producer's
       quiz config becomes required for a v3 deployment, and a v3 validator
       refuses a quizless package (`answer_key_quiz_required`).
     - Under `v3-bank`, the quiz comes from the Q2 and Q3 banks (VALIDATOR-23
       slice 3).
   - **The gate:** the per-case false-feasible rate on the scoring set
     (`feasibility`).
3. **Scoring:**
   - `score = A-Q(a, q)`;
   - eligible only if `feasibility ≤ 0.05`;
   - a gate failure is `eligible: false`, ranked last, never offset;
   - an unmeasured `q` is split by cause (invariant 7; the Test Lead,
     2026-10-08):
     - **Caused by the candidate:** the model fails, or returns non-finite
       or invalid predictions on the Q3 inputs. This is the candidate's own
       typed failure (`q_candidate_failed`), and it is ineligible.
     - **Caused by a reference or by infrastructure:** a quiz reference
       unavailable, a solver failure, a missing batch quiz. This is never a
       miner penalty. The submission is `FAILED_INFRA`, retried, with its
       slot not consumed. Where the window itself is unusable, it is `VOID`
       with the slot restored, the same semantics as VALIDATOR-24's
       withdrawn windows. Otherwise the batch is scored once its quiz is
       restored.
4. **Nomination, finals and the incumbent** follow the v3 score and
   eligibility. Finals compare `A-Q` on the finalist batch and its quiz.
5. **Miner disclosure** is unchanged: sealed under v2's term.
6. **The hidden-score report** ranks by the rule's own score under v3, so
   the development score-variant view is no longer needed for it.

## Prerequisites

- **For `v3-bank`:** the quiz banks (VALIDATOR-23 slice 3).
- **For `v3`:** the producer's existing per-batch quiz path (slice Q).

## Tests

- **Parity:** the v3 score and eligibility equal `score_tuning`'s `G-FEAS/A-Q`
  at 0.05 on the same stored predictions, for a fixture panel.
- **Gate:** a model over 0.05 is ineligible and ranked last.
- **`q` failures, by cause:**
  - a candidate's non-finite Q3 predictions are `q_candidate_failed` and
    ineligible;
  - a missing quiz reference, a solver failure or a missing batch quiz is
    `FAILED_INFRA` or `VOID`, with the hotkey's slot not consumed, never
    ineligible.
- **Prospective:** v2 and v2-bank records are unchanged and never rescored.
- **Quiz required:** a v3 validator refuses a quizless package.
