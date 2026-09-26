# Battery adaptive-agent campaign: pre-registration

**Status.** This is a **DRAFT for owner approval**, written before any run.
- No model call has been made and nothing is dispatched.
- Once the owner approves it, this document is frozen. Its digest goes into
  the campaign manifest before the first provider call.
- Changes after approval need a new version, and the approved version is kept.

**Authority.**
- Owner approval of 2026-09-26: USD 6 model-provider budget (OD-5).
- The owner's agent inference order of 2026-09-26: Engy (Bittensor SN53) through
  an Anthropic-Messages transport, a model ladder that starts at the bottom,
  and accounting from the provider's own charge.
- The owner's three conditions of the same day: pre-register, run a
  same-budget non-adaptive control, and count "no improvement" as a completed
  result.
- The battery launch Challenge (OWNER-LAUNCH-PORTFOLIO-01).

## 1. The question

Does an agent that **adapts to screening feedback** produce a battery
submission that the **frozen exam rule** promotes over what the **same agent,
at the same budget, without that feedback** produces?

This measures whether adaptation helps. It does not measure whether the agent
is good at battery modelling in general, and it measures no real-cell
property.

## 2. Arms

Both arms use the same Challenge and contract digest, the same provider and
model rung (§3), the same autonomous policy and twelve operations,
the same epochs (`FINAL_EPOCHS = (1, 2)`), the same per-epoch caps (48
provider calls, 8 research trials) and the same provider ceiling.

| Arm | Feedback the agent sees after each admitted submission |
|---|---|
| **A: adaptive** | What the exam returns: eligibility, the aggregate pool score, the `pool_version`, and the names of failed gates |
| **B: control** | Eligibility and failed gate names only. **No pool score**, so there is nothing to adapt to except admissibility |

**Owner decision needed (B's design).** B withholds the score but keeps
admissibility. The alternative is a scripted random search over the same
recipe space at the same number of submissions. The feedback-blind agent is
proposed because it holds everything constant except the one thing being
tested.

**Implementation gaps.** Both must be merged before either arm runs, so that
neither arm runs on unmerged code.
- **The transport.** Carbon's agent calls the OpenAI Responses API, which Engy
  does not serve. The Launchpad session is building the Anthropic-Messages
  transport and wiring it through `carbon/battery/campaign.py`. This campaign
  consumes it and builds no second one.
- **Arm B.** The campaign path has no feedback-blind mode. Arm B needs a small,
  tested change that withholds the score. It is built after the transport
  merges, so the two changes to the campaign path do not conflict.

## 3. Model ladder, budget and stopping

**The ladder.** The live model list (`GET /v1/models`) is read before
configuring. Both arms always run the same rung.
1. **Start:** `deepseek-v4-flash-0731`. It runs alone; there is no parallel
   A/B between models.
2. **Escalation** goes one rung only. It is triggered only by one of these
   observed failures in arm A, recorded with the evidence that shows it:
   - repeating an experiment already run;
   - ignoring a measured result when choosing the next step;
   - looping without converging;
   - choosing hypotheses unrelated to what the data showed.
3. **An outcome never triggers escalation.** No improvement, or a small one,
   is a completed result, not a failure. Escalation answers "the agent could
   not run the loop", never "the number was disappointing".
4. **If no listed failure occurs at a rung, the campaign ends at that rung.**
   The rung and the reason for stopping are reported.
5. **The order after the start** is the owner's ladder: `qwen3.8-27b`, then
   `glm-5.3-flash`, then `glm-5.2`, then `kimi-k3` last. A model missing from
   the live list is skipped and recorded, not substituted.


- **Provider ceiling:** USD 3.00 per arm across every rung
  (`provider_nanodollars` 3,000,000,000), for USD 6.00 in total. It is
  accounted from the provider's `charged_micro` per call, never from headline
  rates.
  - `provider_attempts` per arm = 48 calls × 2 epochs = 96.
  - The split is **proposed for owner approval**.
- **Stopping.** Each arm runs its two epochs or until a ceiling is reached,
  whichever comes first.
  - No extension, no rerun with new seeds, and no third arm after results
    are seen.
  - A ceiling reached before the second epoch is a completed run, reported
    as such.
- **Compute** (reconstruction and references) runs on this host at no provider
  cost, and is recorded per arm.

**Recorded per provider call:**
- `charged_micro` and `reasoning_tokens`;
- `cached_tokens` as a fraction of input. If it is zero across iterations, the
  prompt prefix is varying, and that is reported as a defect, not ignored;
- the provenance fields `request_id`, `miner` and `worker`;
- a rate limit, as its own typed failure, distinct from a provider error.

Cost per turn is visible while the campaign runs.

## 4. Outcomes, fixed now

The comparison is the exam's own frozen final comparison
(`carbon.battery.exam`, OD-2 provisional DEVELOPMENT rule):
- 5.7 % equivalence margin;
- `n_boot` 4000, `alpha` 0.05;
- important-region regressions block.

It runs between each arm's best admitted submission, on fresh private
finalist cases that neither arm saw. No new threshold is introduced. The
magnitude that counts as meaningful is the one the exam already uses to
promote.

| Result of "A best vs B best" | Pre-registered reading |
|---|---|
| `IMPROVEMENT` | **Adaptation helped** at this budget, for this agent |
| `NO_IMPROVEMENT` or `INSUFFICIENT_EVIDENCE` | **Adaptation did not help** detectably. A **completed** result, not a failure to be rescued |
| `TRADE_OFF` | **Adaptation did not help**: it changed the model without a promotable gain. The trade is reported component by component |
| `REGRESSION` | **Adaptation hurt**: the feedback led the agent somewhere worse |
| Either arm has no admitted submission | Reported as that. The missing arm is not replaced |

**Reported alongside, never as the primary result:**
- each arm's best against the current incumbent, under the same rule;
- nominated-but-not-promoted counts (memorization signal);
- gate failures by gate;
- provider spend and calls;
- any exploit or unexpected behaviour, recorded as a finding.

## 5. What this cannot show

- **One agent, one model ladder, one budget, one run per arm per rung.** A null result does
  not show that adaptation never helps. A positive result does not show that
  it always does.
- **Nothing about real miners.** Real miners may use other models and larger
  budgets.
- **Nothing about real cells.** Agreement is with the specified PyBaMM model.

## 6. Before the first provider call

1. The owner approves this document, including §2's control design and §3's
   budget split.
2. The Launchpad Anthropic-Messages transport is merged, then arm B's
   feedback-blind mode is implemented, tested and merged.
3. The provider credential is owner-held on this host. The campaign reads it
   only at the point of use, through the transport, and never into a
   variable, log or output. No one asks for its value.
4. The Engy account balance is known and reported. No campaign starts
   without it.
5. The approved document's digest is written into both campaign manifests.
