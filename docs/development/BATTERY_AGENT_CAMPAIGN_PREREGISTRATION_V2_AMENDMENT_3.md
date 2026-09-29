# Battery agent campaign v2: amendment 3 (tier 3)

**Status.** This is an **owner-directed amendment** to the frozen v2
pre-registration. v2 and amendments 1 and 2 are not edited.
- It is recorded on **2026-09-29, before any tier-3 provider call**, so
  nothing below is post hoc.
- **Authority:** OWNER-BATTERY-V2-DISCLOSURE-01 item 9 (`.agent/DECISIONS.md`).
  The owner approved the reserved USD 3 for tier 3, to run after items 1-7
  were delivered and under its own pre-registration. This document is that
  pre-registration.
- **Maturity is unchanged:** exploratory engineering evidence. It feeds exam
  qualification and does not constitute it. There is no scientific
  qualification, and MQ-008 is untouched.

## C1. Why tier 3 has two stages

**The problem.** v2 §7 designed tier 3 as the leak ladder: what a sequence of
submissions can learn about realized exam cases through each feedback
channel. A leak ladder needs **evaluated submissions**, and no v2 campaign
has produced one:
- tier 2's first run stopped at turn 1;
- its second stopped after 19 calls, with no practice, no `run_python` and no
  submission.

The findings (`BATTERY_AGENT_CAMPAIGN_V2_FINDINGS.md`) traced both stops to
limits the agent was never told, and the owner had them fixed.

**So tier 3 runs in order:**
- **3A: does the fixed environment let the agent do research?** One
  campaign, plus a zero-spend control. This is also the before-and-after
  measurement for every change the findings supported.
- **3B: the leak ladder**, run only if 3A passes its gate (C4).
  - It needs two feedback modes that do not exist yet:
    - `ELIGIBILITY_ONLY`, rung 1;
    - `SCORE_WITHOUT_POOL_VERSION`, rung 3.

    Today the campaign has `SCORE_WITHHELD` (rung 2: eligibility plus failed
    gate names) and `FULL` (rung 4).
  - Its exact configuration is pre-registered in **amendment 4, after 3A and
    before any 3B provider call**. That covers the rung order, the epochs,
    the submissions per rung, and what counts as a found channel.

## C2. The environment under test

The environment is main at **`e25e23b4`** or a later main commit, which
contains:

| PR | Change |
|---|---|
| #415 | The context ceiling is measured in tokens at both admission checks |
| #417 | Refusals are filed under their own `refusal` note kind, not `capability_request` |
| #419 | A trial slot is charged only when a task starts; a correction names its field |
| #420 | `check_design` names each exceeded strategy limit (`limits_exceeded`) |
| #422 | The agent's instructions state every operating rule (OWNER-BATTERY-V2-DISCLOSURE-01 items 3-7), and battery's objective carries its `sampling_law` |
| #421 | The findings' correction of R4: `get_prior` takes no selector |

The launch records the exact commit. The worker and analysis images are
built from it, as in tier 2.

**What did not change:**
- invariant 4: the agent is told operating rules, and no exam material;
- the v2 §8 telemetry firewall;
- battery's recorded `generate` gap, which is named in the result.

## C3. Stage 3A

### The campaign

This is **one arm-A campaign, configured exactly as tier 2's rerun**
(amendment 2, B3) except for the environment commit:

| Setting | Value |
|---|---|
| Feedback | `FULL` |
| Model and transport | `deepseek-v4-flash-0731` on `engy-chat` |
| Output allowance | 16,384 tokens, set at launch and recorded |
| Reasoning effort | `low`, the pinned default |
| Parallel-call rule | `FIRST_RUN_REST_REFUSED`, three in a row stops |
| Caps | 48 calls and 8 trials per epoch, `FINAL_EPOCHS = (1, 2)` |
| Budget ceiling | **USD 0.50**, enforced by the ledger's `provider_nanodollars` ceiling and metered from `charged_micro` |

The remaining USD 2.50 is held for 3B.

**Escalation is suspended.** If the campaign stops, the stop is the result,
and there is no retry and no model change (v2 §6).

### The control: same caps, no model, zero spend

The control is a **scripted, non-adaptive caller** driven through the same
`run_epoch` loop, with the same caps and tool surface. It uses the loop's
injected `transport` in place of a model, which is how the loop's own tests
script turns.

Its call sequence is fixed now:
1. `get_challenge_info`
2. workspace `public_material` `objective`
3. workspace `check_design` on the published scaffold recipe
4. practice of the published scaffold recipe
5. `get_research_result` for that practice
6. select the practiced recipe

**What it measures.** It shows what the environment returns to a correct
caller that does not adapt. That separates "the environment blocks research"
from "this model does not find the path".
- If the control cannot complete its six calls, 3A's campaign result is read
  as an environment failure, whatever the model did.
- The control makes **no provider call** and spends nothing.
- If the loop cannot be driven this way without changing Launchpad-owned
  code, the control is **not run**. The result says so, and the missing seam
  is reported to Launchpad.

### Predictions, each tied to a finding

These are fixed before the run. Each is scored from the retained ledger,
provider journal and operations table.

| # | Prediction if the fixes worked | Finding it tests | Refuted if |
|---|---|---|---|
| P1 | The campaign is not stopped by the parallel-call rule | Instance 2, the one-call rule | The three-in-a-row stop ends an epoch |
| P2 | The campaign is not stopped by the context ceiling before 48 calls unless the recorded input really exceeds the token bound | Instance 3, bytes versus tokens | The ceiling stops an epoch while the last recorded input is under `max_input_tokens − CONTEXT_RESERVE_TOKENS` (4,096) tokens |
| P3 | After any argument-contract refusal, the agent's next attempt at the same operation corrects the named field | R1, the string `"null"` | The same field is refused 3 times in a row |
| P4 | Trial slots used equals tasks started | Change 9 | Any slot is charged to a request refused before dispatch |
| P5 (**primary**) | **At least one practice or `run_python` executes in epoch 1** | All of the above: whether research is possible at all | No practice or `run_python` executes in epoch 1 |

### Also reported, not scored

- **The v2 §1 headline metric:** the fraction of calls that return
  information about the physics rather than about Carbon, beside run 2's 0
  of 19.
- **H1-H4** with their unchanged predictions and refutation criteria (v2 §6).
- **The six families** (v2 §6), with **Demand now split:**
  - genuine `capability_request` actions by the agent;
  - `refusal` notes, reported separately.

  Run 2's corrected count was 0 genuine requests and 14 refusals.
- **`check_design` use.** Whether it is called, and whether its
  `limits_exceeded` field ever appears.

## C4. The gate from 3A to 3B

**3B may be pre-registered and run only if both hold:**
- **P5 holds**;
- **epoch 1 produced at least one evaluated submission,** meaning the
  controller submitted a selected recipe and the battery daemon returned an
  evaluation outcome.

**If the gate fails:**
- 3A is the tier-3 result. The environment still blocks research, or does
  not reach evaluation, and the result names where it stops.
- The USD 2.50 held for 3B stays unspent.
- A further run waits until that cause is fixed, as the owner directed for
  tier 2.

## C5. Stop rules

These are v2 §9's rules, plus the following:
- **Spend reaches the 3A ceiling:** the ledger's ceiling stops the campaign,
  and the stop is reported.
- **An observation contains exam material:** any official seed, derived
  seed, draw id, hidden case or reference in an agent observation stops the
  run. It is reported as an invariant-1 incident.
- **No reconstruction verdict is written in 3A or 3B.** Whether the sandbox
  lets a miner reconstruct the exam population is the MQ-008 holder's
  judgement. Tier 3 produces evidence for them.
- **No change to feedback modes, the allow-list or the environment during
  3A.**

## C6. Where the result goes

- **The report:** `docs/development/BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`,
  with 3A first. 3B follows under amendment 4, if the gate passes.
- **Figures:** cost figures stay in private operator evidence, as in tiers 0
  to 2 (the repository is public).
