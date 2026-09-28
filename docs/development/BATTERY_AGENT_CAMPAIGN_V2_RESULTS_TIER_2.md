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
