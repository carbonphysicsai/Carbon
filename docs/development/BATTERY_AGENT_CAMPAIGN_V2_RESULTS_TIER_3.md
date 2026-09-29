# Battery agent campaign v2: tier 3 results

**Status.** These are results under the frozen v2 pre-registration and its
amendment 3 (`BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2_AMENDMENT_3.md`).
Amendment 3 was merged at 09:02:42Z on 2026-09-29, before any tier-3
provider call. This document reports **stage 3A**. Stage 3B runs only under
amendment 4.
- **Maturity.** Exploratory engineering evidence. It feeds exam
  qualification and does not constitute it. There is no scientific
  qualification and no exam-adequacy claim. MQ-008 is untouched, and no
  reconstruction verdict is written.
- **Recorded gap.** Battery's `generate` gap was open throughout (v2 §3.1).
- **Cost.** Every call was metered from the provider's own `charged_micro`.
  Spend was well inside the 3A ceiling of USD 0.50; the figures are kept in
  private operator evidence.
- **Not published here:** exam scores. The agent received its evaluation
  outcome under `FULL` feedback, as designed, but this public document
  records only whether each submission was evaluated.

## 1. What ran

The run was campaign `cmp-e074e1b7`: one arm-A campaign, configured exactly
as amendment 3 C3 specifies.

| Setting | Value |
|---|---|
| Source | main `abf098cb` (contains `e25e23b4`: #415, #417, #419, #420, #422), from a clean checkout |
| Images | worker and analysis images built from that commit |
| Feedback | `FULL` |
| Model and transport | `deepseek-v4-flash-0731` on `engy-chat`, 16,384 output tokens, `low` reasoning effort |
| Caps | 48 calls and 8 trials per epoch, two epochs |
| Budget ceiling | USD 0.50, via the ledger's `provider_nanodollars` ceiling |

**The control was not run.** Amendment 3 C3 provides for this case. The
only way to script the loop is `research_campaign.run_agent(prepared,
transport=...)`, which is documented as "for deterministic acceptance only".
Launchpad, which owns it, declined its use for this, for a reason that holds:
- the campaign plan and every turn record are written under the campaign's
  model selection;
- so a scripted selection would reach the daemon as a real submission whose
  records say a model produced it.

**The missing seam** is a declared control door. It would record a distinct
"scripted, no model" policy in every record and in the submission. Whether a
scripted submission may reach the validator daemon at all is a
submission-authority question for the owner.

## 2. What happened

The campaign **completed both epochs**. In each, the agent selected a recipe
it had practised, and the controller submitted it.

| | Epoch 1 | Epoch 2 | Run 2, for comparison |
|---|---|---|---|
| Provider calls | 27 of 48 | 32 of 48 | 19 of 48, then stopped |
| How it ended | `SELECTED` by the agent | `SELECTED` by the agent | `STOPPED`, context ceiling |
| Practices executed | 8 | 8 | 0 |
| Trial slots used | 8 of 8 | 8 of 8 | 4 of 8, with no task started |
| Tool calls refused | 8 | 3 | 15 of 19 |
| Submission evaluated | **yes**: outcome `SCORED`, eligible | **yes**: outcome `SCORED`, eligible | none |

**The v2 §1 headline metric.** This is the fraction of calls that produced a
measurement of the physics, counted strictly as executed practices:
- **16 of 59 (27 %)**;
- run 2: **0 of 19**.

A further 16 calls read public data or the agent's own workspace:
- 7 successful `public_material` reads;
- 8 `read_file`;
- 1 `inventory`.

## 3. The predictions (amendment 3 C3)

| # | Prediction | Result | Basis |
|---|---|---|---|
| P1 | Not stopped by the parallel-call rule | **Held.** No turn had parallel calls. | No `parallel-refusal` record in either epoch |
| P2 | Not stopped by the context ceiling before 48 calls | **Held.** Both epochs ended in the agent's own `SELECTED`. | Each epoch's `outcome.json` |
| P3 | After an argument-contract refusal, the next attempt corrects the named field | **Held on its criterion**: no field was refused 3 times in a row. **But see N1:** most of these refusals named no field at all. | Tool intents and results, both epochs |
| P4 | Trial slots used equal tasks started, and no slot is charged to a refused request | **Held.** 16 trial charges, one per executed practice. The two practice requests refused at the ceiling, and all 9 argument refusals, cost no slot. **See N2** for the one uncharged task. | The `operations` table (16 `research_trials` charges) |
| **P5 (primary)** | At least one practice or `run_python` executes in epoch 1 | **Held.** 8 practices executed in epoch 1. | Tool results; the operations table |

**The gate to 3B (amendment 3 C4) is met.**
- P5 held.
- Epoch 1's submission was evaluated. Epoch 2's
  `permitted-final-feedback.json` carries epoch 1's outcome, in state
  `SCORED` with eligible screening.

So 3B may be pre-registered, as amendment 4. It still needs:
- **the two feedback modes** that do not exist yet: `ELIGIBILITY_ONLY`, and
  score without `pool_version`;
- **the owner's authority** for any new submission path. The existing path
  suffices for 3B.

USD 2.50 remains held for 3B.

## 4. New findings

**N1. The argument correction names the field only for `strategy_json`.**
- **What happened.** Six refusals in epoch 1 (calls 004, 005, 007, 008, 010
  and 024) came from the agent passing `arguments_json` as a JSON *object*
  rather than a JSON-encoded *string*.
- **What the agent was told.** Each came back
  `REJECTED_BEFORE_DISPATCH` with `field: null` and the generic detail
  "Request does not satisfy the disclosed argument/recipe contract".
- **Recovery.** The agent recovered by trial and error, at a cost of about
  six calls. It made no such mistake in epoch 2.
- **The gap.** #419 names the field for the `"null"` case (calls 002 in
  epoch 1, and 001-002 in epoch 2, report `field: strategy_json`), but not
  for the object-versus-string case.
- **This is the same class as tier 2's R1:** a correction that does not say
  what was wrong.
- **Supported change:** name `arguments_json`, and say it must be a string
  containing JSON. **Owner:** Launchpad (research surface). No disclosure
  decision is needed.

**N2. The agent's only `run_python` failed as infrastructure.**
- **What happened.** Epoch 2, call 008 created a workspace task
  (`DEVELOPMENT_WORKSPACE_V1`). It reached `FAILED_INFRA` within
  milliseconds.
- **Charging was correct.** It was not charged a slot (invariant 7).
- **The cause is not recorded.** The task view records the state and
  nothing about why.
- **What the agent lost.** Its one attempt to analyse the data with its own
  code. It did not retry.
- **Supported change:** record the cause of a workspace `FAILED_INFRA` in
  the task view, then find it. **Owner:** Launchpad (workspace executor).
  This is an engineering change.

**N3. The Demand family is now clean.**
- The run filed **0** `capability_request` notes and **11** `refusal` notes.
  They are separated, as #417 intended.
- **There were no genuine capability requests in tier 3A.**

## 5. Hypotheses, against their pre-stated predictions (v2 §6)

**H1: the agent cannot tell whether it is winning.**
- **Result: prediction partly met.** The agent wrote 35 hypothesis notes. Its
  only notebook write was refused (N1), so no stopping rule was written down.
- **But its selection reasons state a comparison.** Each compares practised
  recipes on the practice score and its components. In epoch 2 it also
  compares against epoch 1's evaluated outcome.
- **Refutation criterion:** not met. No notebook stopping rule exists.

**H2: aggregate-only feedback prevents attribution.**
- **Result: prediction met on its mechanical half.**
- Variables changed per consecutive practice:
  `[3, 2, 5, 5, 6, 4, 1, 2, 8, 7, 2, 3, 1, 2, 2, 2, 1]`. That is **13 of 17
  steps changing more than one variable**.
- The blind reader-scoring of whether each step is explained by the prior
  result was not done. This is reported, not scored.

**H3: the free query surface is under-discovered.**
- **Result: the ordering half is met.** The first practice (epoch 1, call
  013) came before the first `check_design` (call 024). `roadmap` was never
  called.
- **Practices that failed on a ground `check_design` would catch: 0.**
  Every practice was eligible.

**H4: an admissible design is refused as `strategy.identity_invalid`.**
- **Result: not observed.** No design came near the capture limits, and
  `limits_exceeded` never appeared.

## 6. The six recorded families

| Family | Recorded |
|---|---|
| Utilisation | 59 calls. `start_research_task` accounted for 44: 18 practice, 14 `public_material`, 8 `read_file`, 3 `check_design`, and one each of `notebook`, `run_python` and `inventory`. Also: `dry_validate` 4; `get_challenge_info` 2; `compile_strategy` 2; select 2; `get_interaction_manifest`, `get_mock_scaffold` and `inspect_resources` 1 each. **Never called:** `get_prior`, `inspect_prior_alignment`, `forecast_resources`, `cancel_research_task`, `roadmap`, `capability_request`, STOP. |
| Friction | 11 refusals: 9 argument-contract refusals (6 of them N1) and 2 practice requests at the trial ceiling. Plus 1 `FAILED_INFRA` (N2). Recovery: all argument refusals were recovered. |
| Discovery | All five `public_material` names were read in epoch 2, **including `reference_method`** (flagged, not judged). |
| Demand | 0 genuine capability requests, and 11 refusals, filed separately (N3). |
| Prediction quality | 35 stated hypotheses and 16 executed practices. The agent's own selection reasons compare measured components. Hypotheses were not scored against outcomes. |
| Economics | 59 calls, all from `charged_micro`. Reasoning tokens were 0 on every turn. **Cached-input fraction 0.89 (epoch 1) and 0.94 (epoch 2)**, `CACHING_OBSERVED`. |

## 7. What this says about the findings class

The three undisclosed limits in `BATTERY_AGENT_CAMPAIGN_V2_FINDINGS.md` §1
**did not recur** once the agent was told about them and the ceiling was
measured in tokens:
- **the one-call rule:** 0 parallel turns;
- **the context ceiling:** never reached;
- **the capture limits:** never approached.

**Before and after, on the same model and budget:**
- run 2 executed nothing, and three in four of its calls were refused;
- 3A executed 16 practices, and completed two evaluated submissions.

This is one run on each side. It shows that the environment no longer
stops research. It is not a measured effect size.

## 8. Next

1. **Amendment 4 for 3B.** The leak ladder: the rung order, the epochs and
   submissions per rung, what counts as a found channel, and the two
   feedback modes, which are built and tested before any 3B call. It is
   pre-registered before any 3B spend, within the remaining USD 2.50.
2. **N1 and N2** go to Launchpad.
3. **The control door** goes to the owner. Launchpad is raising it.
