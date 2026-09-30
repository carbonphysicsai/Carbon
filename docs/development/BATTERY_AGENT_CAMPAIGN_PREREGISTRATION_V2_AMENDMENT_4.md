# Battery agent campaign v2: amendment 4 (tier 3B, the leak ladder)

**Status.** This is a **pre-registration drafted for the owner's approval**.
It amends the frozen v2 pre-registration. v2 and amendments 1 to 3 are not
edited.
- **No 3B provider call is made until the owner's approval of this document
  is recorded in `.agent/DECISIONS.md`.** Merging it records the design. It
  approves nothing, and it spends nothing.
- **Authority for the spend:** OWNER-BATTERY-V2-DISCLOSURE-01 item 9 approved
  USD 3 for tier 3, under its own pre-registration. 3A ran well inside its
  USD 0.50 ceiling (`BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`), and **USD 2.50 is
  held for 3B**.
- **The gate from 3A is met** (tier 3 results, §3): P5 held, and epoch 1's
  submission was evaluated.
- **Maturity is unchanged.** This is exploratory engineering evidence. It
  feeds exam qualification and does not constitute it. MQ-008 is untouched.

## D1. The question and what may be concluded

**The question** is v2 §7's: where do leak vectors start? It asks what a
sequence of submissions can learn about the exam's **realized screening
cases**, rung by rung, as each feedback channel is added.

**What is not a leak.** The population law is public by design: battery's
objective carries its `sampling_law` (support `four_input_box`, base measure
`uniform_over_input_box`, OWNER-BATTERY-V2-DISCLOSURE-01 item 7). The
disclosure boundary is drawn at realized cases: "no final realized cases,
labels or identities". Reading the published law is not reported as a leak.

**No reconstruction verdict is written.** Whether what the sandbox and its
feedback let a miner produce is enough to reconstruct the exam population is
"a scientific judgement, open and owned by the MQ-008 holder"
(OWNER-CHALLENGE-KIT-01 item 4).
- 3B produces **evidence for that holder**.
- **A found channel is a success.** It is something to learn before miners
  do.
- A passing structural test is not an answer to the holder's question.

## D2. The channels, measured from code before any spend

These bounds are **structural**. They come from the frozen exam rule and the
allow-lists, not from a run, and they hold whatever the agent does. Each row
names its basis.

### Fields every rung shows

These come from the outcome's identity allow-list (`campaign.py`,
`_WITHHELD_OUTCOME_FIELDS`):
- `state`: this shows whether a submission was scored or is waiting, so it
  says whether the pool is scoring;
- `failure`: a typed refusal or failure code;
- `reconstruction`: only `backend` and `validator_path`
  (`daemon.py`, `outcome`). **No seed is in it.**

### What each rung adds

| Rung | Mode | Adds | Upper bound per submission | Basis |
|---|---|---|---|---|
| 1 | `ELIGIBILITY_ONLY` | `eligible` | 1 bit | `campaign.py` `_SCREENING_FIELDS`; `exam.aggregate`: eligible means no case failed a gate and at least one case scored |
| 2 | `SCORE_WITHHELD` | `gates_failed` | at most 7 bits: which of the 7 gates failed on at least one case, as a sorted set of names, with no counts | `exam.GATES`; `daemon._public_score` |
| 3 | `AGGREGATE_SCORE` | `score`, `important_score` | two means over the scored cases, **rounded to 4 decimal places** | `daemon._public_score` |
| 4 | `FULL` | `pool_version`; case counts (`scored`, `reference_invalid`, `failed_infra`); `nominated`; `finals`; `waiting` | several fields at once | `daemon.outcome` |

**Every rung's new field is a function of the realized screening cases.**
Even rung 1's single bit depends on which cases were drawn. Structurally,
leak vectors therefore start at rung 1. Their magnitude, and whether it
matters, is the MQ-008 holder's question.

**A known deviation from one channel per rung.** Rung 4 adds five things
over rung 3, not one (#427). They are reported together.

**What no rung shows** (`research.py`, `SCREENING_FEEDBACK_FIELDS`):
- per-case errors;
- the score components;
- the per-gate failure counts;
- case identities or inputs;
- the rebuild seed.

## D3. `check_design`, examined first

**Why it is examined first.** `check_design` returns a verdict per choice
and, when every choice is rebuildable, **the canonical design Carbon would
rebuild**: resolved defaults, the implementation identity, and the recipe
and plan digests. Step zero established that it costs a model call and no
research trial. So it is a nearly free design oracle, and it is richer than
any scalar score.

**The structural finding: it is a complete channel into the grader's
construction, and it has no input from the exam.**
- **What it answers from:** `check_design(design)` takes only the design. It
  answers from the public construction contract and the validator's own
  compiler (`design_check.py`; `battery/compile.py`).
- **What it loads:** the battery compile path loads only `domain`,
  `challenge`, `contracts`, `recipes` and `compile`. It loads no module that
  holds the exam's pool, seeds, truth or evaluation state.
- **The test that holds it:**
  `tests/cpu/test_battery_check_design_channel.py`, added with this
  amendment.
  - It checks the property above.
  - Its specimen: the same probe, run on the daemon, finds the pool store,
    the seeds and the exam rule.
  - It was shown to fail when the pool store is imported into the probed
    path.

**What this does and does not say.**
- It says `check_design` answers the same way whatever cases the exam
  realized.
- It does **not** say `check_design` is harmless. It fully discloses:
  - which designs are submittable;
  - what the validator will train.

  That is by design: Carbon "can widen what participants are allowed to
  discover without changing who controls the grade" (AGENTS.md §7.9).
- In the ladder, its behavioural use is measured at every rung (D6, M4).

## D4. Volume as a channel

Every scored submission returns at least rung 1's bit. So how many
submissions can reach one set of realized cases is a property of the caps.
These bounds come from the frozen exam rule (OD-2).

| Bound | Value | Basis |
|---|---|---|
| Scored submissions per pool version, all miners together | at most 3 | `exam.py` `rotate_after_admitted: 3`. Scoring requires the pool to be `OPEN`, and it increments `admitted` and attempts rotation in the same transaction (`pool_store.record_score`), so queued submissions cannot exceed it |
| Cases per pool version | 300: 3 active screening batches of 100 | `exam.py` |
| Versions one batch stays active | 3: each rotation retires the oldest of the 3 active batches | `pool_store._try_rotate` |
| Scored submissions that ever see one batch | at most 9, all miners together | the two rows above |
| Submissions per miner | **no per-hotkey cap at admission.** One miner can take every slot. | `daemon.py` admission checks the Challenge, contract, recipe and commitment only. NET-2's per-hotkey rate of 32 requests a second is a transport limit. |
| Practice's channel into realized exam cases | none by provenance: practice scores against the public PRACTICE set (200 solves), which shares no case with TRAIN v1 and supplies none of the exam's cases | `practice.py` |

**The finding.** Whether practice is intentionally incomplete in fact is
settled by these caps.
- The exam bounds volume **per realized case set** (at most 9 submissions
  see any batch).
- It does not bound volume **per miner**.
- A single miner can therefore concentrate every one of those submissions.

This is reported for the MQ-008 holder, and it is not judged here.

## D5. The run

**Four campaigns, one per rung, run one after another in ascending order**
(rung 1 first).
- Each campaign is a fresh agent with no memory of the others.
- The order sets only which pool version each rung meets.

Each campaign is configured **exactly as 3A** (amendment 3, C3), except for
its feedback mode:

| Setting | Value |
|---|---|
| Feedback | the rung's mode: `ELIGIBILITY_ONLY`, `SCORE_WITHHELD`, `AGGREGATE_SCORE`, `FULL` |
| Model and transport | `deepseek-v4-flash-0731` on `engy-chat`, 16,384 output tokens, `low` reasoning effort |
| Parallel-call rule | `FIRST_RUN_REST_REFUSED`, three in a row stops |
| Caps | 48 calls and 8 trials per epoch |
| Epochs | 2 (`FINAL_EPOCHS = (1, 2)`, unchanged). So each rung submits twice, and its agent sees one outcome under its rung's mode, epoch 1's, during epoch 2. |
| Budget ceiling | **USD 0.50 per campaign**, enforced by the ledger's `provider_nanodollars` ceiling and metered from `charged_micro`. That is USD 2.00 in all. The remaining USD 0.50 of the tier-3 approval stays unspent. |

**Escalation is suspended,** as in 3A. A stop is the rung's result. There is
no retry and no model change.

**Pool versions.** The ladder makes 8 submissions. At 3 per version, rung 1
meets one version, rung 2 straddles a rotation, and rungs 3 and 4 share
versions. Each submission's pool version is recorded in private evidence, and
the analysis reports it beside every rung. Only rung 4's agent sees it.

**Another miner's submission during 3B** (Launchpad, for example) is
recorded with its effect on rotation. It is not a stop.

**The environment** is main at or after this amendment's merge. It includes
3A's two supported fixes, #425 (N1: a `*_json` field must be a string, and
the refusal names it) and #426 (N2: a wrong workspace field is refused before
dispatch, not recorded as `FAILED_INFRA`), and #428 (Launchpad's runner
takes the four modes from `carbon.battery.campaign.FEEDBACK_MODES`). The
launch records the exact commit.

## D6. What is measured, and what counts as a found channel

These are fixed now. Each is read from the retained campaign records, the
daemon's outcome for each submission, and the agent's observations.

| # | Measure | How |
|---|---|---|
| M1 | **Disclosed:** the screening fields that actually reached the agent | Read from the agent's epoch-2 observations, and compared with the rung's allow-list. A field outside the list is an allow-list failure and stops the run (D8). |
| M2 | **Dependence:** whether each disclosed field is a function of the realized screening cases | Structural, from D2 |
| M3 | **Use:** whether the agent acted on the disclosed outcome | (a) Whether epoch 2's selection reason or notebook names a disclosed field or states its value, by mechanical match on the field names, gate ids and values. (b) How many recipe variables changed between the two selected recipes, counted as H2 counts them. |
| M4 | **`check_design` use** | Calls per epoch; whether any `limits_exceeded` appears; whether a selected recipe is exactly a canonical design that `check_design` returned. |
| M5 | **Volume used** | Submissions per pool version and per batch, beside the D4 bounds |

**Definitions.**
- **FOUND.** A rung's channel is **FOUND** when a field that depends on the
  realized cases (M2) reached an agent observation (M1).
- **USED.** It is **USED** when M3(a) holds.
- **NOT MEASURED.** A rung whose agent received no screening outcome, for
  example because the pool was `ROTATION_PENDING` when epoch 2 began, is
  **NOT MEASURED**. It is not NOT FOUND.
- **Not a verdict.** Neither FOUND nor USED is a reconstruction verdict.

**The prediction, fixed now:**
- **Every measured rung is FOUND,** because every rung discloses `eligible`
  (D2).
- **Refuted if** a rung's agent receives a screening outcome and none of that
  rung's case-dependent fields.

**USED has no prediction.** It is what the ladder is for.

## D7. The control

v2 and the owner's standing direction call for a same-budget, non-adaptive
control. **It cannot be run yet.**
- A scripted caller would reach the validator daemon as a submission whose
  records say a model produced it.
- Launchpad declined that use in 3A, and the reason holds (tier 3 results,
  §1).
- The missing seam is a declared control door. **Whether a scripted
  submission may reach the daemon is an owner decision** (D9).

**What stands in for it:**
- **The structural bounds (D2 to D4).** They are what a non-adaptive caller
  would be limited by, and they hold without a run.

**What stays unmeasured without it:** the score's spread for the same recipe
under different rebuild seeds and pool versions. So M3's recipe changes
cannot be separated from noise in the outcome the agent saw, and the result
says so.

## D8. Stop rules

These are amendment 3's (C5), plus:
- **An allow-list failure.** A screening field outside the rung's list in an
  agent observation stops the ladder. It is reported as a disclosure
  incident.
- **Exam material in an observation.** Any official seed, derived seed, draw
  id, hidden case or reference stops the run. It is reported as an
  invariant-1 incident.
- **Spend at a campaign's ceiling** ends that campaign. It is reported, and
  the next rung still runs.
- **The pool cannot score** (`ROTATION_PENDING` with no prepared batch).
  - The next campaign does not launch until a batch is prepared.
  - A rung already running completes, and is recorded NOT MEASURED if its
    outcome never arrived.

**Unchanged:**
- no change to feedback modes, allow-lists or the environment during 3B;
- the v2 §8 telemetry firewall: write-only from the agent's side, asserted by
  its test.

## D9. What the owner decides before 3B runs

1. **Approve this amendment.** That is the pre-registration gate for the
   USD 2.00 in D5.
2. **Prepare the screening batches** (the precondition).
   - **The latest recorded pool state** is from the H record
     (`BATTERY_H_VALIDATOR_OBSERVATION.md`, after 12:14Z on 2026-09-29):
     - version 0;
     - `ROTATION_PENDING`, with admitted 3;
     - no screening batch `PREPARED`;
     - the only finalist set consumed.
   - **How many batches the ladder needs.** Scoring 8 submissions from that
     state needs **3 prepared screening batches** with complete references:
     1. one to clear the pending rotation;
     2. one after submissions 1 to 3;
     3. one after submissions 4 to 6.
   - **Preparing batches is the owner's call.** They are then ingested by the
     operator steps.
   - **At launch,** a read-only `operate status` is taken first and must show
     the pool able to score.
   - **A finalist set** is not needed for any rung's screening outcome.
     Without one, a nominated submission's final waits as
     `WAITING_FOR_FINALIST_SET`, which only rung 4 can see.
3. **Optional: the control door** (D7). If it is authorized, the control is
   pre-registered in a further amendment before it runs.

## D10. Where the result goes

- **The report:** `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`, section 3B.
  It has one row per rung (M1 to M5, FOUND or USED or NOT MEASURED) and the
  D3 finding.
- **Kept in private operator evidence:** scores, pool versions against
  submissions, and cost figures, as in tiers 0 to 3A.
- **The evidence** is addressed to the MQ-008 holder. No verdict is written.
