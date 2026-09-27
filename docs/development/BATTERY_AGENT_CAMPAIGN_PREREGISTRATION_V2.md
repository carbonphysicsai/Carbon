# Battery agent campaign v2: is the research environment optimal for an agent?

**Status.** **APPROVED by the owner on 2026-09-27** (restart brief, 21:45Z):
"the v2 design as put to him". That covers environment-first, step zero then
tiers 0 and 1, the campaign third at USD 3 with USD 3 reserved, the leak ladder
designed but not run, the firewall and the maturity ceiling. Written before
any v2 provider call.
- v1 (`BATTERY_AGENT_CAMPAIGN_PREREGISTRATION.md`) stays exactly as approved.
  Its adaptation question is **deferred, not answered and not withdrawn**. No
  v2 result bears on whether adaptation helps.
- No v2 provider call had been made at approval. This version is now frozen;
  changes need v3.
- **Corrections made at approval**, before freezing. They are recorded here so
  that no one reads them as silent edits:
  - §3's claim that no sampling law is published was wrong. See the corrected
    §3.
  - The `generate` gap recorded by #397 is added to every tier (§3.1).

**Authority.**
- The owner's v2 brief of 2026-09-27 13:05Z ("Tiered Environment
  Experiment").
- Engy through the Anthropic-Messages transport (#369), a launch path that
  carries the model and feedback mode (#390), and the frozen feedback modes
  (#389).
- The owner's inference order: accounting from `charged_micro`, provenance
  recorded per call, caching asserted.

**Maturity ceiling for every v2 claim:**
- exploratory engineering evidence;
- **feeds** exam qualification (AGENTS.md §7.1) and does not constitute it;
- no scientific qualification, no exam-adequacy claim;
- MQ-008 (reconstruction of the exam population) untouched.

## 1. The question

**Does Carbon's research environment let an agent spend its budget on physics
rather than on Carbon?**

Environment friction is a **confound in Carbon's core instrument**, not a
usability issue. If winning depends partly on fluency with Carbon's
interface, the exam measures that fluency on top of construction-method
quality and cannot separate the two. Findings are reported as **confound
reduction**, never as friction complaints.

**Headline metric:** the fraction of the agent's tool calls that produce
information about the **physics**, versus information about **Carbon**. A call
spent learning the interface is a lost experiment.

## 2. Step zero: what each call really costs (done; no provider calls)

**Sources:**
- the code at `c991db911`;
- the metering test `tests/cpu/test_research_surface_costs.py`. It uses a real
  `CampaignLedger` and the real charging decision in `ResearchMinerTools.call`,
  with only the downstream service stubbed;
- the existing `test_cw1_research_agent_policy` for provider-call counting.

**Correction to the brief.** `check_design`, `roadmap`, `capability_request`
and `run_python` are not among the twelve research operations
(`carbon/research/model.py:116`). They are **workspace actions** passed through
`start_research_task kind=workspace`.

| Call | What it consumes (per epoch) | Basis | Can an agent learn this in advance? |
|---|---|---|---|
| **Every tool call**, any kind, including SELECT, STOP and a free-text turn | 1 of **48 model calls**, plus a ledger reservation of 1 provider attempt, nanodollars and 3 MiB | `research_loop.py:198,241`; `research_agent.py:238-248`; measured in `test_free_text_receives_one_metered_correction...` (3 replies → `provider_attempts` 3) | The 48 is in `run_plan`. **That every tool call consumes one of them is not stated anywhere.** |
| The 11 non-task operations (`get_challenge_info` … `forecast_resources`, `get_research_result`, `cancel_research_task`) | the model call only | no ledger reservation on their path (`research_tools.py:539-544`) | "discovery charges nothing" (`challenge_registry/battery.py:169,172`) |
| `inspect_prior_alignment` | the model call plus a demand note; always `UNAVAILABLE` | `research_tools.py:545-554` | in its description |
| `forecast_resources` | the model call; always `NO_RESOURCE_PREDICTION` | `resource_estimation.py:553-566` | yes: `workflow.estimate` says "static, uncalibrated" (`challenge_registry/battery.py:173`) |
| Workspace `public_material`, `inventory`, `read_file`, `write_file`, `notebook`, `capability_request`, **`check_design`**, `roadmap` | the model call plus notes and storage checks; **0 research trials, no compute** | **measured:** `test_workspace_actions_charge_no_research_trial` (all 8) | workspace: "no Carbon size or count limit" (`battery.py:163`). **Per-action cost is not stated.** |
| `kind=practice` | **1 of 8 research trials**, plus up to 600 s metered compute; one worker at a time; **no reference solve** | **measured:** `test_practice_and_run_python_each_charge_one_trial`; `battery/research.py:118,561-573` | `practice_charge`, `practice_worker_seconds` (`battery.py:157-158`); prompt: "each practice or run_python consumes a trial slot" |
| Workspace `run_python` | **1 trial**, plus metered compute | measured, same test | as above |
| **A malformed practice or `run_python` call** | **still 1 trial**, charged before validation; starts nothing | **measured:** `test_a_malformed_practice_call_is_rejected_and_still_charged` | **only afterwards**, in the rejection text |
| SELECT | the model call; writes the selected recipe; the controller then submits | `research_loop.py:331-344`; `research_campaign.py:983` | tool description |
| `submit`, `get_submission_result` | not callable by the agent (`NAMESPACE_MISMATCH`) | `research/service.py:687` | n/a |

**Findings from step zero.** These are recorded, not judged:

1. **`check_design` is trial-free.** It is a compile-only design oracle,
   bounded only by the 48-call cap. It is the agent's most valuable
   inexpensive resource, and it is tier 3's first object of scrutiny.
2. **Every tool call spends one of the 48 per-epoch model calls, and the
   agent is never told that.** Accepted by the owner as a finding in its own
   right. An agent that cannot see a cost cannot budget against it, which is
   the same class of defect as an undocumented cap. The 48 appears in
   `run_plan`, but nothing says that a free workspace action, SELECT, STOP or
   a reminder turn each consumes one.
3. **A malformed practice or `run_python` call still consumes a trial.** It is
   charged before validation, and the agent learns this only from the
   rejection text afterwards.
4. **`forecast_resources` is uncalibrated, and says so in advance**
   (`workflow.estimate`). An agent asking what something will cost gets no
   prediction. It is disclosed, but it leaves the undisclosed costs of
   findings 2 and 3 without a way to learn them.

## 3. Battery-specific corrections to the brief

The brief's §2 describes the Burgers objective. The battery objective differs
in ways that change two items.

- **Published.** The input box (`c1`, `c2`, `t_amb_c`, `soc0` with bounds and
  units), the output contract, the gates, the score definition, the full OD-2
  rule (including the 5.7 % margin and the important region), and the
  miner-visible feedback fields.
- **A sampling law exists, but the agent sees only a reference to it.**
  - The population contract declares its support (`four_input_box`) and a
    probability law with base measure **`uniform_over_input_box`**
    (`battery/research.py:challenge_parts`, `population.law_semantics`).
  - `get_challenge_info` serves the population as `population.to_ref()`, an
    object id and a content digest (`research_service.py:293-305`), not the
    law's content.
  - No `public_material` document states the law; the objective gives the
    bounds only.
  - **Correction:** the draft said no sampling law was published. What is
    true is that it is declared and referenced, but not readable by the agent
    as content. This is **not yet verified by a live `get_challenge_info`
    call**. The tier-0 harness makes that call first, at no provider cost,
    and records what the agent actually receives.
- **There is no reference solve:** "no reference solve is offered to miners in
  this version" (`battery/research.py:219-222`).
- **So a battery agent cannot generate labelled practice cases itself.** It
  can generate inputs only. Its labelled data is the published TRAIN v1 set
  (`training_data`), and practice scores against the stored public PRACTICE
  references.
- **Consequence for tier 1.** The brief's criterion "realizes it can generate
  its own practice data from the published laws" is replaced by "realizes
  TRAIN v1 and PRACTICE are its labelled data, and that no reference solve is
  available".
- **The disclosure boundary.** For battery it is the allow-list
  `evaluation_feedback_fields`, not Burgers' `final_feedback` text.
- **The incumbent.** Its score appears nowhere in the battery objective
  (checked: no "incumbent" field). H1's premise holds.

### 3.1 The recorded `generate` gap, named in every tier

OWNER-RESEARCH-ENVIRONMENT-01 (#397) requires every Challenge's environment to
give miners its public generator and reference solver under their own seeds.
Battery's `generate` is a **recorded open gap** (`challenge_kit/standard.py`;
`RESEARCH_ENVIRONMENT_STANDARD.md`): nothing miner-facing runs the pinned
PyBaMM reference, so miners have only TRAIN v1 and the 200 PRACTICE cases.

What it means for each tier:

- **Tier 0 stays runnable for battery.** It tests whether a design is
  admissible, using `check_design`, which compiles and never generates data.
  The gap does not touch admissibility. Every tier-0 result is still labelled
  "measured in an environment with the `generate` gap open".
- **Tier 1** scores plans. A plan to generate labelled data is **correct under
  the standard** and **impossible in this environment**. It is scored as
  item 4's "no reference solve assumed" failure only if the plan assumes it
  can run. It is also recorded separately as the plan reaching for a
  provision the standard requires and battery lacks. That count is evidence
  about the gap, not about the agent.
- **Tier 2.** Any finding about data scarcity, extrapolation or wasted
  practice is reported with the gap as a named cause, not attributed to the
  agent or to the interface. A struggling agent in an environment missing a
  required provision measures the environment.
- **Tier 3.** The leak ladder concerns realized exam cases. The gap narrows
  what a miner can generate, and it does not settle the reconstruction
  question (MQ-008).

No other Challenge is substituted for battery in any tier.

## 4. Tier 0: can the published material produce an admissible design?

**Design.**
- A model is given **only** the battery public material: the five
  `public_material` documents and the challenge discovery document. There is
  no Carbon-insider text and no hint.
- It is asked for one design in the `check_design` shape.
- The design is run through `check_design` as served at the approved commit.
- **Framings, texts fixed now:**
  - **F1:** "Here is a challenge's public material. Propose one design for it,
    as JSON in the design schema the material describes."
  - **F2:** "You are a miner entering this challenge. Using only this
    material, give the design you would submit first, as JSON in the
    material's design schema."
  - **F3:** "Design a construction for this challenge. Output only the JSON
    design."
- **Models:** `deepseek-v4-flash-0731`, `qwen3.8-27b` and `glm-5.3-flash`,
  read from the live model list. One absent from the list is skipped and
  recorded.
- **Samples:** 3 per framing × model cell, **n = 27** designs.

**Rubric, fixed now, scored mechanically from `check_design`'s verdicts:**

| Outcome | Definition |
|---|---|
| **PASS** | The output parses as a design, and `check_design` reports every choice rebuildable, returning a canonical design |
| **PARTIAL** | It parses, and at least one choice is rebuildable, but not all |
| **FAIL** | It does not parse as a design, or no choice is rebuildable |

- For every non-rebuildable choice, record `check_design`'s reason, and
  whether the public material states the constraint that rules it out
  (searched for the choice's name and value). That becomes the material-gap
  finding.
- Blind scoring is automatic, because the verdict comes from `check_design`,
  not from a reader.
- **Do not coach.** A hint the material does not contain is recorded as a
  missing piece of material, and never given.

## 5. Tier 1: does the environment teach its own best strategy?

**Design.**
- A model is given the public material, the twelve operations and the
  workspace actions with their tool descriptions. It is asked to **plan** its
  48 calls and 8 trials for an epoch. Nothing is executed.
- The same framing idea as tier 0 applies, with plan-specific texts fixed at
  approval. The same three models, 3 samples per cell, **n = 27** plans.

**Rubric, fixed now.** Each item is yes or no, scored by a reader **blind to
model and framing**: plans are shuffled and relabelled before scoring, and the
key is kept apart until all are scored.

1. **Queries before spending.** It reads material or discovery before its
   first trial.
2. **Finds `check_design`.**
3. **Finds `roadmap`.**
4. **Knows its labelled data.** It uses TRAIN v1 and PRACTICE as labelled data
   and does not assume a reference solve (the battery replacement, §3).
5. **Budgets against the real costs** in §2 (48 calls, 8 trials, 600 s
   practice), not invented ones.
6. **Reserves for later.** It keeps calls or trials in reserve for selection
   or for epoch 2.

**The decisive statistic, carried into every tier:** does the first
`kind=practice` come **after** a `check_design` call?

## 6. Tier 2: one instrumented campaign, testing named hypotheses

**Configuration and limits.**
- **One arm**, arm A's configuration: `FULL` feedback,
  `deepseek-v4-flash-0731` on `engy-anthropic`, caps unchanged (48 calls and 8
  trials per epoch, `FINAL_EPOCHS = (1, 2)`).
- **Hard ceiling of USD 3.00**, from `charged_micro`. The other USD 3 is
  reserved for tier 3, which needs its own go-ahead.
- **Escalation is suspended.** A struggling agent is the result. If the agent
  cannot complete one operation, the campaign stops and is reported.

**H1: the agent cannot tell whether it is winning.** The exam compares
against an incumbent it cannot see.
- *Predicted if true:*
  - calls spent on self-calibration rather than a stated target;
  - no stopping rule written in the notebook;
  - direction changes without a measured reason.
- *Measure:* the count of calls whose stated purpose is orientation rather
  than a physics hypothesis.
- *Refuted if:* orientation calls are a minority of the calls with a stated
  purpose, **and** the notebook states a stopping rule.

**H2: aggregate-only feedback prevents attribution.**
- *Predicted if true:* several variables changed between submissions or
  practices, and next steps that the previous measured result does not
  explain.
- *Measure:*
  - the variables changed per practice or submission;
  - per step, whether the prior result explains it (reader-scored, blind to
    the H2 prediction's direction).
- *Refuted if:* most steps change one variable **and** are explained by the
  prior result.

**H3: the free query surface is under-discovered.**
- *Predicted if true:*
  - practice spent on designs `check_design` would have rejected;
  - late or absent first use of `check_design` or `roadmap`.
- *Measure:*
  - the ordering statistic;
  - the count of practice trials that failed on a ground `check_design`
    catches.
- *Refuted if:* the first practice follows a `check_design`, **and** no
  practice fails on a ground it would have caught.

**Recorded from existing surfaces only.** These are `CampaignLedger.note`, the
`operations` table and the per-call provider journal. No second telemetry
system.
- **Utilisation:** every call, its count and its order. The never-called set
  is a primary result.
- **Friction:** every `TaskContractMismatch` with its correction, every
  rejection, refusal and retry, and the calls or trials each cost to
  recover.
- **Discovery:** the `public_material` names read, and those never read.
  `reference_method` unread is flagged, not judged.
- **Demand:** every `capability_request`, verbatim and unranked.
- **Prediction quality:** each `run_python` or practice's stated
  `hypothesis` and `expected_effect`, against the measured outcome.
- **Economics:**
  - `charged_micro` per call;
  - `reasoning_tokens`;
  - the cached-token fraction. Zero across iterations is reported as broken
    caching;
  - reservation against actual, from the `operations` table.

**What H1 and H2 do not authorize.** Invariant 4: disclosure is allow-listed.
Tier 2 measures **the cost of withholding**. It does not widen disclosure,
propose a widening as settled, or implement one. Any change is the owner's,
with whoever owns the allow-list.

## 7. Tier 3: the leak ladder (designed now, run later)

This runs only after tier 2, with the reserved USD 3 and its own go-ahead.

**Why v1's A/B was redesigned.** Both v1 arms see eligibility and failed gate
names. If realized-case information is recoverable from those alone, an A/B
contrast cannot see it, because both arms leak equally.

**The ladder**, one channel per rung:
1. eligibility alone;
2. plus failed gate names;
3. plus the aggregate pool score;
4. plus `pool_version`.

- **`check_design` is examined first.** Step zero shows it is trial-free.
- **Volume is a channel:** enough submissions map the admissible region
  whatever the score says.
- **The population law** (§3) is public by design. The question is realized
  cases.
- **No reconstruction verdict is written.** That is a scientific judgement,
  open and owned by the MQ-008 holder. Tier 3 produces evidence for them. A
  found channel is a success.

## 8. The firewall

**v2 telemetry is write-only from the agent's side.**
- The agent never sees, queries or receives it.
- A test asserts this, in the credential-absence style. It shows a telemetry
  marker present in the ledger (the specimen) and absent from every agent
  observation and tool reply.
- Behavioural telemetry fed back would be a score channel, and would
  contaminate any future feedback-blind control.

**Unchanged:**
- no official seeds, derived seeds, draw ids, reversible ids or protected
  material in anything recorded (invariant 1);
- mock isolation;
- practice deliberately incomplete (invariant 12).

## 9. Order and stopping

**Order:**
1. Step zero is done (§2).
2. **Owner approval of this document** before any provider call.
3. Tiers 0 and 1, reported **before** any tier-2 spend.
4. Tier 2, stopping at USD 3.00.
5. A proposal for the reserved USD 3, drawn from what was found.

**What stops the work:**
- any provider call before approval;
- spend beyond USD 3 in tier 2;
- widening disclosure;
- writing a reconstruction verdict;
- weakening any invariant, the firewall included;
- winner weights, mainnet, or a second dispatch authority.

OD4A-BATTERY-0002 is independent of v2 and is not sequenced behind it.
