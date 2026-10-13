## 2026-10-13 — GRAPHITE-OUTPUT-CAP-KIMI-01: kimi-k3's whole-context roles reply with up to 32,768 output tokens

**Authority.**
- The owner, 2026-10-13, relayed by the Test Lead: "Max out the available tokens like the rest of them that is an
  insane limitation." The Test Lead read "like the rest of them" as 32,768, the cap the level planner and the Score Lab
  research session already use, and chose it per model. The owner can raise it further with one line.
- This is a dated decision, not a correction of an earlier one. It changes no grant figure, ceiling, construction
  contract, score, gate or miner-facing surface, and it involves no spend.

**Why.** The Level 4 Constructor run under GRAPHITE-GRANT-L4-G-CONSTRUCTOR-4 (lane G, kimi-k3) staged and ran the
starter, then two turns in a row ended `status: incomplete, reason: max_output_tokens` with 2,048 of 2,048 output tokens
spent entirely on reasoning and no tool call. The cap covers reasoning and reply together, and the provider bills
reasoning as output. The loop stopped the run (code `replies_truncated`, `incomplete{reason, cap, tokens}`, the turns
recorded `FAILED_INFRA`) and Carbon closed the session `NO_IMPROVEMENT`. The run cost about USD 0.11 of the grant.

**History of the figures.**
- 2,048 is `model_provider.DEFAULT_SETTINGS.max_output_tokens`, set in commit b8b82bcf5 (2026-09-26, "The miner chooses
  the research agent's model provider"). It is the historical pinned default that every plan frozen before
  `OUTPUT_DEFAULT_V2` recorded; it stays as it is.
- 4,096 for the phase-4 Attacker is GRAPHITE-ATTACKER-STOP-RULE-01 (2026-10-05): "the largest cap that keeps D35's whole
  input window unchanged". A larger cap on a model that opens on its whole context would let a request overflow the
  context, which the provider refuses as an invalid request and which stops a campaign. A truncated turn is
  recoverable and now reports its cause.

**Decision.**
1. `roles.MODEL_OUTPUT_CAPS = {"kimi-k3": 32768}`: the Constructor and the Attacker on kimi-k3 reply with up to 32,768
   tokens. It is a per-model table, not a per-role constant. Every other model keeps its role's cap (the Constructor's
   2,048, the Attacker's 4,096), and GRAPHITE-ATTACKER-STOP-RULE-01 stands for them.
2. The fit rule (`roles.output_cap_fits`): the loop admits input under `max_input_tokens` less
   `CONTEXT_RESERVE_TOKENS` (4,096); that plus the cap must stay inside the model's recorded context. A table row that
   does not fit is refused (`output_cap_does_not_fit_context:<model>`), never applied or dropped silently.

   | model | context | window | worst request at 32,768 | fits |
   |---|---|---|---|---|
   | kimi-k3 | 1,113,088 | 1,048,576 | 1,077,248 | yes, 35,840 to spare |
   | deepseek-v4-flash-0731 | 1,048,576 | 1,048,576 | 1,077,248 | no, over by 28,672 |
   | qwen3.8-27b | 1,001,536 | 1,001,536 | 1,030,208 | no, over by 28,672 |
   | glm-5.3-flash | 262,144 | 262,144 | 290,816 | no, over by 28,672 |
   | glm-5.2 | 262,144 | 262,144 | 290,816 | no, over by 28,672 |

   32,768 is within the recorded output maximum (131,072, Engy's published list). The input window is unchanged, so
   GRAPHITE-D34 and D35 ("max out context") stand, and the Level 4 readiness R4 formula is unchanged.
3. A run of replies that all hit the output cap stops with a named cause: `cause: turn_hit_output_cap`,
   `agent_decision: false`, `output_cap{cap, turns[{turn, output_tokens}]}`, beside the unchanged
   `code: replies_truncated`. A cut turn never touches the reminder counters or any stall rule.

**Money.** The grant's worst case, ceiling and token share are unchanged (14.91, 14.94, 10.99; the Attacker's share
11.45): a call's charge cannot exceed its reservation, so spend stays inside the share. The per-call hold on kimi-k3 is
window x input price + cap x output price: 1,048,576 x 1,950 + 32,768 x 9,750 = USD 2.3642112 (was 2.0646912 at 2,048).
Full holds in the 10.99 share: 5 to 4; in the 11.45 share: 5 to 4. The controller refuses the next call when the
remaining share is below one hold, so the usable share before a stop falls by about USD 0.30.

**Not carried.** (a) 32,768 on every model, unchanged windows: refused above (the four non-kimi models overflow).
(c) 32,768 everywhere with an 11 percent cut to the glm windows: available if the Test Lead wants it, not pending work.
The Level 4 readiness R4 review for lane G attests the output; it is re-attested for 32,768 in this change's own commit
(draft until the Test Engineer confirms in the PR).
