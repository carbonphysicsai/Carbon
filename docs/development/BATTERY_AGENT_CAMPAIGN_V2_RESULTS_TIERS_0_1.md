# Battery agent campaign v2: results of tiers 0 and 1

**Status.** Results under the approved, frozen v2 pre-registration
(`BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md`).
- **Maturity.** Exploratory engineering evidence. It feeds exam qualification
  (AGENTS.md §7.1) and does not constitute it. There is no scientific
  qualification and no exam-adequacy claim. MQ-008 is untouched.
- **The recorded gap.** Every result was measured with battery's `generate`
  gap open (v2 §3.1). Tiers 0 and 1 do not depend on it.
- **Cost.** Every call was metered from the provider's own `charged_micro`.
  Figures are kept in private operator evidence, not here. Both tiers were
  negligible.
- **Transport.** Tiers 0 and 1 ran on Engy's Chat Completions endpoint
  (`engy-chat`), because the Anthropic-compatible Messages endpoint returns no
  `x_engy` charge or provenance report (finding 7).
- **Harnesses.** `scripts/dev/battery_campaign_v2/tier0.py` and `tier1.py`.

## Tier-0 prerequisite: what the agent is told about the population

**Measured** with a live call through the battery research service's own
adapter.
- `get_challenge_info` and `get_interaction_manifest` return the population
  and sampling plan only as **references**: object ids and content digests.
- The public `objective` gives the input bounds only.
- The declared law (support `four_input_box`, base measure
  `uniform_over_input_box`) appears in no agent-facing reply.

## Tier 0: can the public material produce an admissible design?

The design is: three framings, three models and three samples, **n = 27 per
run**, scored mechanically by the real `check_design` (v2 §4).

| | Run A (4,096 output tokens) | Run B (16,384 output tokens) |
|---|---|---|
| PASS | 4 (1 copied a discovery example) | **11** (1 copied) |
| PARTIAL | 4 | 10 |
| FAIL | 19 | 6 |

- **The output limit is the harness's, not v2's.** In run A, the reasoning
  models (glm-5.3-flash, qwen3.8-27b) spent all 4,096 tokens reasoning and
  never answered (11 FAILs). Those 11 measure the cap. Run B repeats all 27
  with more room, and both runs are reported. The rubric is unchanged.
- **Run B by model:**

  | Model | PASS | PARTIAL | FAIL |
  |---|---|---|---|
  | qwen3.8-27b | 6 | 3 | 0 |
  | glm-5.3-flash | 3 | 4 | 2 |
  | deepseek-v4-flash-0731 | 2 | 3 | 4 |

- **Run B by framing:** F2 has 7 PASS out of 9; F1 and F3 have 2 out of 9
  each.

**What limited the other designs, run B:**

| Count | Cause |
|---|---|
| 9 | Every choice was reported `supported`, but the rebuild refused with `strategy.identity_invalid` ("Strategy identity could not be established"). |
| 4 | No design could be parsed from the reply. |
| 2 | The wrapper had extra keys, one being `admission`, the discovery examples' own shape. |
| 1 | A parameter dependency was unsatisfied. |

**Why the rebuild refused them.** The strategy exceeded the capture limits in
`carbon/development_session/contracts.py:strategy_limits`. For example,
`max_object_members = 32`: one design was accepted with 32 parameters and
refused at 33. Those limits appear nowhere in the public material, and the
refusal does not name the limit.

## Tier 1: does the environment teach its own best strategy?

The design is: three plan framings, three models and three samples, n = 27.
Plans are scored mechanically, which is blind by construction (v2 §5).
- **Disclosed deviation.** v2 said the plan framing texts would be fixed at
  approval. They were fixed afterwards, before any tier-1 call, and are
  recorded in `tier1.py`.
- **Parsed:** 20 of 27 plans. Of the other 7, 4 hit the output limit while
  reasoning. The other 3 (deepseek, P1) stopped after a single tool-call-shaped
  step at 64-75 tokens; the cause is **undetermined**.

| Item (of 20 plans) | Yes |
|---|---|
| 1. Queries before spending a trial | 18 |
| 2. Finds `check_design` | **10** |
| 3. Finds `roadmap` | **1** |
| 4. Uses TRAIN v1 and PRACTICE as its labelled data (keyword proxy) | 12 |
| 5. Budgets within the real caps | 19 |
| 6. Reserves budget for selection or epoch 2 | 13 |

**Ordering statistic.** Of the 10 plans that use both `check_design` and a
practice, **8 check first and 2 practise first**. The other 10 plans never use
`check_design`.

## Findings

These are ranked by measured confound. None is implemented here, and none
widens disclosure of exam data.

1. **Undisclosed strategy size limits, refused opaquely.** This cost 9 of the
   27 run-B designs, where every choice was valid.
   - An agent cannot learn the limit from anything it is given, and cannot
     tell from the refusal what to change.
   - Supported by: publishing the limits, and having the rebuild name the
     limit exceeded.
   - An engineering change; it discloses no exam data.
2. **Half of the plans never find `check_design`, and almost none find
   `roadmap`** (10 of 20, and 1 of 20).
   - Step zero shows `check_design` is trial-free. That is the agent's
     cheapest way to learn admissibility, and the environment does not make
     it obvious.
   - Supported by: surfacing both actions where planning starts.
   - An engineering change.
3. **Every tool call spends one of the 48 per-epoch model calls, and the
   agent is never told** (step zero; accepted by the owner). A rejected
   practice also still costs a trial.
   - Supported by: stating both costs in the run plan.
   - An engineering change.
4. **The discovery examples teach a format `check_design` rejects.** They are
   written as `{strategy, admission}`, while `check_design` accepts only
   `{strategy, capabilities?}`.
   - Supported by: aligning the examples or the accepted shape.
   - An engineering change.
5. **The sampling law is declared but not readable by the agent.** This is
   evidence against `challenge_kit/standard.py` marking battery's `research`
   provision fully provided.
   - Supported by: publishing the law's description; it is public by design.
   - Placement is the owner's call.
6. **The framing sensitivity is large** (7 out of 9, against 2 out of 9). It is
   a sign of a fragile surface, and it is recorded, not acted on.
7. **Transport: Engy's Messages endpoint gives no charge or provenance
   report**, so a tier-2 campaign on `engy-anthropic` cannot be settled from
   the provider's charge.
   - v2 froze tier 2 on `engy-anthropic`; the same model on `engy-chat` does
     report.
   - An **owner decision** before tier 2.

## Next

Tier 2, one instrumented campaign at USD 3, **waits on the owner's
transport decision** (finding 7). v1's adaptation question remains deferred.
No v2 result bears on it.
