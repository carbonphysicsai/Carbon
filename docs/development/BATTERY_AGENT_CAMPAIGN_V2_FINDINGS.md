# Battery agent campaign v2: findings across tiers 0 to 2, and the changes they support

**Status.** This is a synthesis of results already recorded under the frozen
v2 pre-registration:
- `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIERS_0_1.md`
- `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_2.md`, covering both runs

It runs nothing new. **Tier 2 is not re-run.** It stopped twice, for reasons
that can be named, and those reasons are the finding. A third run before the
environment changes would measure the same defects again.

- **Maturity.** Exploratory engineering evidence. It feeds exam qualification
  (AGENTS.md §7.1) and does not constitute it. There is no scientific
  qualification and no exam-adequacy claim.
- **MQ-008 is untouched.** Whether the sandbox lets a miner reconstruct the
  exam population is a scientific judgement, open and owned by the MQ-008
  holder.
- **Nothing here is implemented.** Every change below is proposed. The
  owner decided changes 8 and 9 and every disclosure question on 2026-09-29
  (`.agent/DECISIONS.md`, OWNER-BATTERY-V2-DISCLOSURE-01): the agent is told
  every operating rule below.
- **Recorded gap.** Battery's `generate` gap was open throughout (v2 §3.1).

## Headline result: the environment was the constraint

The v2 hypothesis was that Carbon's research environment, not the agent,
limited what an agent could do. It was tested with **a measured before, one
named change, and a measured after**, on the same model, transport, caps and
feedback mode.

| | Before: tier 2, run 2 | After: tier 3A |
|---|---|---|
| Practices executed | 0 | 16 |
| Evaluated submissions | 0 | 2, both `SCORED` and eligible |
| Tool calls refused | 15 of 19 | 11 of 59 |
| How the run ended | stopped at the context ceiling after 19 of 48 calls | both epochs ended in the agent's own selection |

**The named change** was OWNER-BATTERY-V2-DISCLOSURE-01: the agent is told
every operating rule it can hit, delivered in #415, #417, #419, #420 and #422.
- **The model did not change:** `deepseek-v4-flash-0731` on `engy-chat`,
  16,384 output tokens, 48 calls and 8 trials per epoch, `FULL` feedback.
- **The budget was never binding.** Tier 2 used under one per cent of its
  ceiling.

**An agent that could not complete one practice now runs the loop and
produces scored submissions.** That is the headline result of v2.

**Basis:**
- run 2 is recorded in `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_2.md`;
- tier 3A is recorded in `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_3.md`, and
  was pre-registered as amendment 3 before any call.

**Limits of the claim:**
- It is one run on each side. It shows that the environment no longer stops
  research. It is not a measured effect size.
- **Maturity:** exploratory engineering evidence, feeding exam qualification
  (AGENTS.md §7.1) and not constituting it.
- **MQ-008 is untouched.**

## 1. The finding: an agent cannot plan against a limit it is not told about

This is **one finding with three instances**. Each instance is a hard limit
that the environment enforces and never states to the agent. The agent meets
each one only by hitting it, and each one cost real operations.

| # | Limit | Where it is enforced (main) | What the agent is told | Measured cost |
|---|---|---|---|---|
| 1 | Strategy capture limits, e.g. `max_object_members = 32` | Values: `carbon/development_session/contracts.py:221` (`strategy_limits`). Type: `carbon/fees/model.py:330` (`SubmissionResourceLimits`). Refusal: `carbon/construction/compiler.py:1084`, `:1088`, `:1096`. | Nothing. The refusal is the generic `strategy.identity_invalid` ("Strategy identity could not be established"). At `:1088` it comes from a catch-all `except`, so the exceeded limit is not even available to name. | Tier 0, run B: **9 of 27** designs refused where every choice was reported `supported`. One design was accepted at 32 parameters and refused at 33. |
| 2 | One tool call per turn | `carbon/development_session/research_loop.py:291-294`. The request also carries `parallel_tool_calls: false` (`:233`), and the provider ignored it. | Nothing up front. `CHALLENGE_PROMPT` (`research_agent_policy.py`) does not state it. Since #408 the rule is stated **after** a violation, in `PARALLEL_REFUSAL`. | Tier 2, run 1: **the whole campaign**, stopped at turn 1. 4 of 4 samples of the turn-1 request made parallel calls. Run 2, after #408: 1 extra call refused on turn 1, and the run continued. |
| 3 | Context admission ceiling | `research_loop.py:238`: `len(canonical(request))`, in **bytes**, is compared with `max_input_tokens − 4096`, in **tokens**. | Nothing. The agent reasons in tokens and is told neither the limit nor its unit. | Tier 2, run 2: stopped after **19 of 48** calls. The last admitted turn carried **15,140 input tokens**, against **65,536** configured. |

**Basis.** The code sites were read on main at `368c713e`. The costs come from
the two results documents. Instance 3's token counts were re-read from run
2's retained epoch outcome (`provider_turns[].input_tokens`, 19 turns; the
last three were 13,769, 14,632 and 15,140). The prompt check is a read of
`CHALLENGE_PROMPT` on main: it contains no statement of any of the three
limits.

**Two more members of the class** are already recorded:
- **The per-call cost.** Every tool call spends one of the 48 per-epoch model
  calls, which is not stated anywhere (v2 §2, step zero).
- **The stop condition #408 added.** Three consecutive parallel turns stop the
  epoch (`consecutive_limit: 3`). This is also never stated, including in the
  refusal the agent does see.

They are listed so the class stays complete. Neither has a separate measured
cost.

**Why this matters as a class.** Each instance could be fixed alone and the
next one would still be found by the next campaign, at the owner's expense.
The class-level change is the same in every case:
- every hard limit the environment enforces on the agent is stated to the
  agent before it can be hit;
- every refusal names the limit that was hit.

Whether a given limit may be stated is a disclosure decision (invariant 4).
None of these three limits is exam data. They are Carbon's operating rules.

### What #408 settled about the one-call rule, and what remains

The owner had three open options after run 1: disclose the rule, amend the
loop, or change the model.
- **Amending the loop is done by delivery.** #408 runs the first call and
  refuses the rest. Run 2 shows it worked: one parallel turn in 19, no stop,
  and no parallel call after the refusal.
- **Changing the model is no longer needed for this defect.** Run 2
  completed its turns on the same model.
- **Disclosure remains, and it is the owner's.** The rule is still not in the
  agent's instructions; the agent learns it only by breaking it once. The
  three-in-a-row stop is disclosed nowhere. What remains is whether both go
  into `CHALLENGE_PROMPT`.

## 2. The capability-request stream is contaminated

The `capability_request` stream was meant to record **what an agent asks for
that does not exist**. That makes it the most valuable output of the
experiment. As built, **every pre-dispatch refusal is also filed there**:
- `research_tools.py:476`: `rejected()` journals each refused request as a
  `capability_request` with `disposition: investigate`;
- `research_tools.py:576`: every non-OK `start_research_task` reply is
  journaled the same way;
- `research_loop.py:412`: the trial-ceiling refusal is filed there too (not
  reached in either run).

**Counts, separated.** Read from run 2's retained campaign ledger (`notes`
table):

| Run | Notes filed as `capability_request` | Of which refusals | Genuine requests by the agent |
|---|---|---|---|
| Tier 2, run 1 | 0 | 0 | 0 |
| Tier 2, run 2 | **14** | **14** (all from `rejected()`: 13 `start_research_task`, 1 `get_research_result`) | **0** |

Every one of the 14 carries the default `expected_benefit` "Requester has not
yet justified an extension". None is a workspace `capability_request` action
by the agent.

With refusals separated, **the Demand family records zero requests across
tier 2**. As filed, it records 14 requests that were never made.
- Any roadmap count ("how many miners asked") built on this stream is
  inflated by refusal volume. Refusal volume is a friction measure, and the
  opposite of a demand measure.
- The fix is to journal refusals under their own kind, and to keep
  `capability_request` for the agent's own action (`research_workspace.py:164`).
  This is an engineering change and discloses nothing.

## 3. Changes supported, ranked by measured confound

**The confound.** The headline question of v2 §1 is what fraction of the
agent's tool calls produce information about the physics rather than about
Carbon. Ranking is by the fraction of the agent's budget each defect was
**measured** to consume. A change whose cost was not measured is ranked below
every measured one, however plausible it is.

**The columns.**
- **Cost** is the engineering size, not money.
- **Disclosure** says whether the change widens what the agent is told, and
  so needs a decision under invariant 4.
- **Owner** is the proposed owner; the owner assigns.

| Rank | Change | Measured confound (basis) | Cost | Disclosure decision? | Proposed owner |
|---|---|---|---|---|---|
| 1 | **Measure the context ceiling in tokens** (or scale the byte bound) so a 65,536-token setting is not a ~15,000-token limit, and state the ceiling. Tier-2 change 10. | **29 of 48 calls (60%)** of the epoch never happened (run 2, outcome `STOPPED`, "context admission ceiling") | Small: one comparison in `research_loop.py:238`, plus a test pairing a request that is under the token bound but over the byte bound | Stating the ceiling: yes. Fixing the unit: no. | Launchpad (research loop); the owner decides stating it |
| 2 | *Held for the owner:* name the offending field in the argument correction and say that `null` is JSON `null` (tier-2 change 8); stop charging a trial slot for a request refused before dispatch (change 9) | **15 of 19 calls (79%)** failed, and **4 of 8 trial slots** were consumed with no task started (run 2, R1) | Not proposed here | Change 8's string acceptance is an interface change; change 9 is a budget rule | **Decided 2026-09-29 (OWNER-BATTERY-V2-DISCLOSURE-01): change 8 option (a), naming the field with no interface change; change 9, no slot charged until a task starts. Launchpad implements.** |
| 3 | **Disclose the one-call rule and its three-in-a-row stop** in the agent's instructions. The loop half is done (#408). | Run 1: **100%**. The campaign ended on its only call. Run 2, after #408: 1 extra call refused, 0 calls lost. | Small: prompt text | **Yes** | The owner decides; Launchpad implements |
| 4 | **Publish the strategy capture limits, and name the exceeded limit in the refusal**, replacing the catch-all at `compiler.py:1088` with a specific refusal | **9 of 27 designs (33%)** refused although every choice was valid (tier 0, run B) | Medium: the refusal must carry the limit from `identify_strategy` through `CompileRejected`; publishing is a text change | Publishing: yes. Naming it in the refusal: no. | Launchpad (research surface); the owner decides publishing |
| 5 | **Separate refusals from capability requests** (section 2) | **14 of 14 Demand records (100%)** are refusals. This is an instrument confound, not an agent one. | Small: a new note kind at three sites | No | Launchpad |
| 6 | **Surface `check_design` and `roadmap` where planning starts** | Tier 1: **10 of 20** plans find `check_design`, **1 of 20** find `roadmap`. Tier 2 live: the first practice (call 11) came before the first `check_design` (call 14). | Small: text | No: both are already disclosed tools | Launchpad |
| 7 | **Align the discovery examples with the shape `check_design` accepts** | Tier 0, run B: **2 of 27** designs carried the examples' extra `admission` key | Small | No | Launchpad |
| 8 | **Say that `get_prior` cannot succeed while no prior pack is registered** (corrected 2026-09-29: it takes no selector; the schema is `{}` and every call returns `REQUEST_TYPE_INVALID`). Tier-2 change 12. | Run 2: **1 of 19** calls | Small: text | No | Launchpad |
| 9 | **State that every tool call spends one of the 48 model calls** | Not measured separately. It is the denominator of every figure above. | Small: text | **Yes** | The owner decides; Launchpad implements |
| 10 | **Publish a description of the sampling law**, which is public by design | Not measured. Evidence against `challenge_kit/standard.py` marking battery's `research` provision as fully provided. | Small | **Yes**; placement is the owner's call | The owner |

**Already done, not ranked:**
- #401: launch-settable output cap (Testnet);
- #404: cache-count translation (Launchpad);
- #408: loop half of the one-call rule.

**Battery's `generate` gap** (the battery challenge kit, assigned to
Launchpad) is not ranked here, because neither tier-2 run got far enough to
depend on it. Its confound is unmeasured, not zero.

**What the ranking says.** Ranks 1, 3 and 4 are the three instances of
section 1. Together they account for the largest measured losses in every
tier: a lost campaign, 60% of an epoch, and a third of tier 0's designs. The
second-largest (rank 2) is held for the owner.

## 4. Boundaries

- **Nothing here widens disclosure.** It names the changes that would, and
  leaves each to the owner under invariant 4.
- **The v2 telemetry firewall holds.** The families remain write-only from
  the agent's side (v2 §8). Nothing in this document is fed back to an agent.
- **No threshold, tolerance, gate, population or qualification criterion** is
  set or implied.
- **No spend.** The USD 3 reserved for tier 3 needs its own go-ahead.
