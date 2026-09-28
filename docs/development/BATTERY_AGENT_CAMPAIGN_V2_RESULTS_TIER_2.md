# Battery agent campaign v2: tier 2 result: stopped at turn 1

**Status.** This is a result under the approved, frozen v2 pre-registration
and its amendment 1. **Tier 2 did not run its research.** It stopped on the
agent's first turn, and it stays stopped pending an owner decision
(section 4).

- **Maturity.** Exploratory engineering evidence. There is no scientific
  qualification and no claim that the exam is adequate. MQ-008 is untouched.
- **Recorded gap.** Battery's `generate` gap was open. The run never got far
  enough to depend on it.
- **Cost.** Every call was metered from the provider's own `charged_micro`.
  The figures are kept in private operator evidence and are negligible.

## 1. What ran

The run was the one registered arm-A campaign, configured as follows:

| Setting | Value |
|---|---|
| Feedback | `FULL` |
| Model | `deepseek-v4-flash-0731` |
| Transport | `engy-chat` (amendment A1) |
| Output allowance | **16,384 tokens** (A4). Launch-settable since #401 and recorded in the campaign manifest. |
| Budget ceiling | USD 3, enforced by the ledger's `provider_nanodollars` ceiling |
| Source | a clean checkout of a main commit containing #401 |
| Images | worker and analysis images built from that commit |
| Admission | subnet registration (the miner hotkey is registered on 567) |

## 2. What happened

1. On turn 1 the agent replied with **two tool calls**,
   `get_challenge_info` and `get_interaction_manifest`, although the request
   carried `parallel_tool_calls: false`.
2. The research loop refuses any reply with more than one tool call
   (`research_loop.py`: "parallel tool output prohibited; retained and
   stopped"). The campaign ended `INTERRUPTED`, having made one provider
   attempt, no research trial and no submission.
3. **Resuming does not help.** A resume replays the retained turn-1 response,
   which is keyed on the request digest, and stops again. It makes no new
   provider call.
4. **The behaviour is systematic, not a one-off.** The same turn-1 request
   was replayed three times directly through `engy-chat`, outside the
   campaign. Every reply contained parallel calls: 4, 2 and 2. Counting the
   campaign's own reply (2), that is **4 of 4**.
5. **The agent is never told the rule.** Its instructions (2,946 characters)
   contain no statement that a turn may make only one tool call.

## 3. Hypotheses

| | Pre-stated prediction | Result |
|---|---|---|
| H1 | the agent cannot tell whether it is winning: orientation calls dominate, and no stopping rule is written | **Not exercised.** No research turn completed. |
| H2 | aggregate-only feedback prevents attribution: several variables change per step, and steps go unexplained | **Not exercised.** There was no practice and no submission. |
| H3 | discoverability of `check_design` and `roadmap` | **Not exercised in a live run.** Tier 1 already measured it: 10/20 plans find `check_design`, 1/20 find `roadmap`, and 8 of the 10 using both check first. Tier 2 was to confirm that, not discover it. |
| H4 | at least one practice or submission refused as `strategy.identity_invalid` or equivalent, on an all-`supported` design | **Not exercised as stated,** because no design was reached. |

**The same class of defect struck harder than H4 predicted.** H4 predicted
losing single operations to an undisclosed limit. Here an undisclosed
structural rule, one tool call per turn, **lost the whole campaign on turn
1**. This is reported as an observation beside H4. It is not a confirmation
of H4, whose stated measure was not reached.

## 4. Why it stays stopped

The stop is the registered behaviour. v2 §6 says: "Escalation is suspended. A
struggling agent is the result. If the agent cannot complete one operation,
the campaign stops and is reported."


Every way to continue changes something the pre-registration fixes, or is on
the owner's list of reserved changes:

- **Tell the agent the one-call rule.** This widens disclosure to the agent,
  which is the owner's decision (invariant 4, brief §6).
- **Change the loop to accept parallel calls.** For example, run the first
  call and return a typed refusal for the others. This changes the instrument
  after registration, so it needs an amendment recorded before the run.
- **Change the model.** This deviates from v2's fixed tier-2 model, so it
  also needs an amendment.

## The six recorded families (v2 §6), as far as the run reached

| Family | Recorded |
|---|---|
| Utilisation | 1 provider call. Called: `get_challenge_info` and `get_interaction_manifest`, both requested in the same refused turn and neither executed. Everything else was never called. |
| Friction | 1 refusal: parallel tool output, which ended the campaign. Recovery cost: not recoverable, and a resume replays the same refusal. |
| Discovery | No `public_material` name was read. `reference_method` was unread (flagged, not judged). |
| Demand | No `capability_request`. |
| Prediction quality | No `run_python` or practice, so nothing to compare. |
| Economics | All `charged_micro`, 0 reasoning tokens. Cached fraction 0/7,118 on the campaign's single call, so the zero-across-iterations rule was never exercised. On the three direct replays it was 6,912/7,118 (97%), so caching works on this transport. The per-call reservation sized for 16,384 output tokens was settled at the provider's much smaller charge. |

## 5. Supported environment changes, each with a proposed owner

| # | Finding (evidence) | Change | Proposed owner |
|---|---|---|---|
| 1 | Undisclosed `max_object_members = 32` (tier 0: 9/27 all-`supported` designs refused) | disclose the limit | the owner decides the disclosure; Launchpad implements |
| 2 | The opaque `strategy.identity_invalid` message says nothing about what was wrong (tier 0) | name the limit that was exceeded | Launchpad (research surface) |
| 3 | Every tool call spends 1 of 48 model calls, and the agent is never told (step zero) | disclose the per-call cost | the owner decides the disclosure; Launchpad implements |
| 4 | The one-call-per-turn rule is undisclosed and ends the campaign (this tier) | handle extra calls without ending the campaign, and/or disclose the rule | Launchpad (research loop); the owner decides the disclosure and the amendment |
| 5 | Battery `generate` gap (v2 §3.1) | the battery challenge kit | Launchpad (assigned) |
| 6 | Launch could not set the output cap (A4) | done: #401 | Testnet (merged) |
| 7 | The Engy Messages translation turned a missing cache count into 0 (tier-0 finding) | done by Launchpad: #404 | Launchpad |

**Planned future work, not built:** re-run tier 0 on the same harness once
the battery kit lands, for a before-and-after on `generate`.

---

## Rerun under amendment 2 (2026-09-28)

This is the one new arm-A campaign that amendment 2 specifies. It was
launched from main at `8ee4038d`, which contains #408. Its manifest records:

| Setting | Value |
|---|---|
| Parallel-call rule | `FIRST_RUN_REST_REFUSED`, three in a row |
| Output allowance | `max_output_tokens` 16,384 |
| Reasoning effort | `low`, the pinned default |
| Feedback | `FULL` |
| Budget | the USD 3 ceiling less the first run's spend |

Every call was metered from `charged_micro`. **Battery's `generate` gap
remained open.** The run never reached a point where it would have mattered.

### What happened

The epoch **stopped after 19 of 48 calls**, with the reason "context admission
ceiling". The run made **no practice, no `run_python`, no submission and no
final**, and **no workspace action executed**.

| | Count |
|---|---|
| Provider calls | 19 |
| Turns with parallel calls | 1: turn 1, one extra call refused, the run continued |
| Tool calls refused or erroring | **15 of 19** |
| `start_research_task` refused | **13 of 13** |
| Research-trial slots consumed | **4 of 8**, with **no task started** |

**Finding R1: `"null"` as a string, not JSON `null`.** On every
`start_research_task` call, the agent sent `strategy_json`, `action` and
`arguments_json` as the string `"null"` where the contract wants JSON `null`.
- The tool schema allows JSON `null` for all three: each is typed
  `["string", "null"]`.
- `arguments_json` is itself JSON encoded as a string, so `"null"` is a
  natural reading.
- The correction text says `strategy_json=null`. It was returned verbatim 13
  times, and never says which field was wrong or that the string differs from
  the value.
- The agent never recovered.
- **Cost:** 3 practices and 1 `run_python` were each charged a trial slot and
  none started (the step-zero finding that a malformed practice is still
  charged). Every recipe it tried was reported `valid` by `dry_validate`.

**Finding R2: the context ceiling compares bytes with tokens.**
- The loop refuses the next call when `len(canonical(request))`, in **bytes**,
  exceeds `max_input_tokens − 4096 = 61,440`, a number of **tokens**.
- Measured at 4.0 bytes per token, the run stopped at **about 15,140 tokens of
  context, against 65,536 configured**.
- This is conservative by construction, because bytes are always at least
  tokens. But it stopped the campaign after 19 of 48 calls, and the agent is
  never shown this limit.

**Finding R3: refusals are filed as capability requests.** Each refused call
was journaled as a `capability_request` note ("disposition: investigate").
There are 14, and none is a request the agent made. So the Demand family is
contaminated by construction.

**Finding R4: `get_prior` was called with `{}`** and returned
`REQUEST_TYPE_INVALID`. It needs a selector the agent did not supply.

**The parallel-call rule worked.** One turn had a parallel call, the extra
call was refused, and the run continued. The agent made no parallel call
after that refusal (1 of 19 turns).

### Hypotheses, against their pre-stated predictions

| | Prediction | Result |
|---|---|---|
| H1 | Orientation calls dominate the calls with a stated purpose, and no stopping rule is written. | **Prediction met, not attributable.** All 13 calls with a stated purpose were orientation or baseline, none a physics hypothesis, and no notebook or stopping rule was written. But no practice ran, so the agent never received the feedback H1 is about. R1 explains the pattern. Refutation criterion: not met. |
| H2 | Several variables change per step, and steps go unexplained. | **Not exercised.** There was no practice and no submission. |
| H3 | Late or absent use of `check_design` and `roadmap`; practice spent on designs `check_design` would reject. | **Ordering part met.** The first practice attempt (call 11) came before the first `check_design` (call 14) and `roadmap` (calls 15–16). All three were refused under R1, so none executed. Practice failures on a ground `check_design` would catch: **0**. They failed on the argument encoding. Tier 1 had put the number at 8/10 check-first in plans; the live ordering went the other way. |
| H4 | A practice or submission refused as `strategy.identity_invalid` or equivalent on an all-`supported` design. | **Not exercised as stated.** No design was assessed. The designs had 3 parameters (MLP) and 1 (KNN), far under the 32-member cap. **A sibling mechanism, the envelope encoding in R1, cost 4 of 8 trial slots with no task started.** It is an observation beside H4, not a confirmation of it. |

### The six recorded families

| Family | Recorded |
|---|---|
| Utilisation | 19 calls: `start_research_task` 13, `dry_validate` 2, `get_challenge_info` 1, `get_mock_scaffold` 1, `get_prior` 1, `get_research_result` 1. **Never called:** `get_interaction_manifest` (refused as the parallel extra), `compile_strategy`, `inspect_prior_alignment`, `inspect_resources`, `forecast_resources`, `cancel_research_task`, SELECT and STOP. |
| Friction | 15 failures in 19 calls: 10 `workspace_recipe_forbidden`, 3 `practice_recipe_required`, 1 `contract_incompatibility` and 1 `REQUEST_TYPE_INVALID`. Recovery: none. Cost: 4 trial slots and about 75% of the calls. |
| Discovery | No `public_material` name was read. The agent tried `objective` 4 times and `capabilities` once, and all were refused. `reference_method` was unread (flagged, not judged). |
| Demand | 14 `capability_request` notes, **all artefacts of R3**. There was no genuine request. |
| Prediction quality | No practice or `run_python` executed. The stated hypotheses are recorded, for example "KNN should be valid", with nothing to compare against. |
| Economics | 19 calls, all `charged_micro`. Reasoning tokens 0 on every turn. **Cached-input fraction 0.86** (`CACHING_OBSERVED` from turn 3). Every reservation settled at the provider's much smaller charge. |

### Supported environment changes this run adds (proposed owners)

| # | Change | Proposed owner |
|---|---|---|
| 8 | Name the offending field in the argument-contract correction, and state plainly that `null` means JSON `null`, not the string `"null"`. Or accept the string `"null"` as null for the three nullable fields. | Launchpad (research surface). Accepting the string is an interface change and needs the owner's decision. |
| 9 | Do not charge a trial slot for a request refused before dispatch. The step-zero finding again, now measured costing half an epoch's trials. | Launchpad. The owner decides, because it is a budget rule. |
| 10 | Measure the context ceiling in tokens, or scale the byte bound, so a 65,536-token setting is not a 15,000-token limit. | Launchpad (research loop) |
| 11 | Do not file refusals as capability requests. | Launchpad |
| 12 | Say what selector `get_prior` needs. | Launchpad |

**Maturity:** exploratory engineering evidence. There is no scientific
qualification, and MQ-008 is untouched.
