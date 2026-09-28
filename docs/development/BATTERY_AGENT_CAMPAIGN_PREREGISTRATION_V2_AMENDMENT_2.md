# Battery agent campaign v2: amendment 2 (tier 2 rerun)

**Status.** This is an **owner-directed amendment** to the frozen v2
pre-registration (`BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md`), following
amendment 1. v2 and amendment 1 are not edited.
- It was recorded on **2026-09-28, before any provider call of the tier-2
  rerun**, so nothing below is post hoc.
- **Authority:** the owner's decision of 2026-09-28 on the research loop's
  handling of parallel tool calls. That decision answers the question left
  open in `BATTERY_AGENT_CAMPAIGN_V2_RESULTS_TIER_2.md` §4.
- **Maturity is unchanged:** this is exploratory engineering evidence. It
  feeds exam qualification and does not constitute it.

## B1. What happened, and what stays recorded

- The first tier-2 campaign stopped at turn 1. The model made parallel tool
  calls although `parallel_tool_calls: false` was set, in 4 of 4 samples, and
  the research loop ended the campaign.
- **That campaign stays recorded as a result.** It is not rescored,
  replaced or deleted (invariant 10).

## B2. The instrument change: the research loop's parallel-call rule

- **One tool call per turn remains the rule.**
- **What changes:** when a reply contains several calls,
  - the loop runs the **first** one;
  - it returns an **explicit refusal** for each extra call;
  - the refusals are **journaled** and **use no trial slot**.
- **When the run stops:** only after **three turns in a row** contain parallel
  calls. The old behaviour stopped it on the first.
- **Record format:** it is versioned from this change onward, so retained
  turns recorded before the change keep their meaning.
- **Owner and build:** Launchpad owns the research loop and builds the change.
  The tier-2 rerun starts only from a main commit that contains the merged
  change.
- **What this change does not do:** it widens nothing the agent is told
  (invariant 4). The one-call rule is enforced as it was; only the penalty
  for breaking it changes.

## B3. The rerun

It is **one new arm-A campaign**, configured exactly as v2 §6 and amendment 1
specify:

| Setting | Value |
|---|---|
| Feedback | `FULL` |
| Model and transport | `deepseek-v4-flash-0731` on `engy-chat` |
| Output allowance | 16,384 tokens, set at launch and recorded |
| Caps | 48 calls and 8 trials per epoch, `FINAL_EPOCHS = (1, 2)` |

- **Budget:** the ceiling is the USD 3.00 tier-2 budget **less what the first
  campaign and its three diagnostic replays already spent**, read from
  `charged_micro`. The two runs together stay within USD 3.
- **Measures:** H1–H4, their predictions and their refutation criteria are
  unchanged.
- **One measure is added to the friction family:** the number of turns with
  parallel calls, the extra calls refused, and whether the three-in-a-row stop
  was reached. The rerun shows whether the refusal teaches the agent the rule.
  It is recorded, not scored.
- **The stop rule (v2 §6) still applies.** If the loop's three-in-a-row stop
  ends the run, that is the result, and it is reported. There is no model
  escalation.
- **The `generate` gap** stays open and is named in the result.
