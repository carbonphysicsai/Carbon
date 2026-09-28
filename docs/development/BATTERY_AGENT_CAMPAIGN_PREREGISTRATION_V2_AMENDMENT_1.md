# Battery agent campaign v2: amendment 1 (tier 2)

**Status.** An **owner-directed amendment** to the frozen v2 pre-registration
(`BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md`). v2 itself is not edited.
- Recorded on **2026-09-28, before tier 2's first provider call**, so nothing
  below is post hoc.
- Authority: the owner's decisions of 2026-09-28, in the brief "Tier-2
  Transport, OD-4a lapses, and the adapter is your next ticket".
- Maturity is unchanged: exploratory engineering evidence, feeding exam
  qualification and not constituting it.

## A1. Transport: tier 2 runs on `engy-chat`

- **Replaces:** v2 §6, which named `engy-anthropic`.
- **Reason** (not to be re-opened): Engy's Messages endpoint returns no charge
  or provenance report (tiers 0-1 results, finding 7). v2 meters from the
  provider's own `charged_micro` and fails closed when it is missing, so
  Messages cannot carry a metered experiment.
- **Comparability:** `engy-chat` keeps tier 2 comparable to tiers 0 and 1.
- **#369 is not deprecated by this.** The Anthropic-Messages transport stays
  available to miners; it is not the instrument for this measurement.
- **A fix this finding caused:** Launchpad's correction to the Messages
  translation, which had read a missing cache count as 0, is on branch
  `agent/messages-cache-unknown`.

Everything else in v2 §6 is unchanged:
- one arm, `FULL` feedback, `deepseek-v4-flash-0731`;
- caps of 48 calls and 8 trials per epoch, `FINAL_EPOCHS = (1, 2)`;
- a **USD 3.00 hard ceiling**, with the other USD 3 reserved for tier 3 under
  its own go-ahead;
- escalation suspended.

## A2. H4, stated before the run

**H4: the agent loses practice operations to undisclosed structural limits.**
- **Basis:** tier 0 run B. 9 of 27 designs had every choice reported
  `supported`, yet were refused with `strategy.identity_invalid` ("Strategy
  identity could not be established"). They exceeded the undisclosed
  `max_object_members = 32` (`development_session/contracts.py`).
- **Predicted if true:** at least one practice or submission is refused with
  `strategy.identity_invalid`, or an equivalent structural rejection, on a
  design whose every choice was reported `supported`.
- **Measure:**
  - the count of such refusals;
  - for each, the design's size against the limit it exceeded (object
    members, total value nodes, identity bytes).
- **Refuted if:** no practice or submission in the run is refused on a
  structural limit while every choice was reported `supported`.
- **Caveat on refutation:** if the agent never builds a design large enough to
  reach the limit, H4 is **not exercised**. That is reported as such, not as
  refuted.

## A3. H3's status

Tier 1 has already measured H3's discoverability question:
- 10 of 20 plans find `check_design`, and 1 of 20 finds `roadmap`;
- 8 of 10 plans that use both check before practising.

So discoverability is the defect, and strategy is not. Tier 2 **confirms** this
in a real run; it does not discover it. Its report says so.

## A4. The output cap

Run A at 4,096 output tokens gave 4 admissible designs; run B at 16,384 gave
11. The cap was itself a confound.
- **Tier 2's agent runs with a 16,384-token output allowance**, recorded in
  the campaign manifest's provider plan.
- **If the launch path cannot set it, tier 2 does not start** until it can. No
  run proceeds under a cap that could silently stop a reasoning model from
  answering.
- The cap in force is reported with the results.

## A5. The `generate` gap, named in every result

Battery's `generate` gap (#397) remains open. The battery kit is assigned to
Launchpad and is not built.
- **Every tier-2 result names the gap**, in each result, not once at the top.
- **Planned future work, not built now:** re-run tier 0 on the same harness and
  rubric once the kit lands. The before-and-after on the same question (does
  having a generator change what designs an agent produces?) is the
  measurement.

## A6. Unchanged

Everything else in v2 stands unchanged:
- the firewall, with telemetry write-only from the agent's side;
- invariants 1, 4 and 12;
- no disclosure widening;
- no reconstruction verdict (MQ-008);
- v1's adaptation question deferred;
- OD-4a is independent of this.
