# KOTH-TAKEOVER-RULE-01: better score wins beyond measured rebuild noise; a self-improving king keeps his clock

Date: 2026-10-19
Status: ADOPTED for development; confirmed by the owner 2026-10-19 (see the scope note). Payable use still needs an adopted score pack and a registered four-Challenge weight policy, both the owner's.
Authority: the owner delegated this decision to the Test Lead on 2026-10-19:

> keep it simple. better score wins and takes the emission, halves every 24 hours, existing winner beating himself is the one I need you to decide on.

The Test Lead decided it and relayed it to the Carbon Validator, who records and implements it.

**Scope note.** The owner's words delegate one question: the king beating himself (§2). Under the same delegation, as the Test Lead stated, three more decisions were made:
- the rebuild-noise reading of "better score" (§1);
- dethroning a king that fails a gate, with its share burning (§3a);
- the four-Challenge policy (§4).

Each is development-only and fails closed. The owner has been told this pattern, not only the individual decisions.

**Owner confirmation (2026-10-19, in the Test Lead's session, relayed to the Carbon Validator).** The Test Lead asked: "KOTH: my four decisions and Battery dropping off the paid list... Say if any is wrong". The owner answered **"Yes and yes"**. That confirms §1, §2, §3a and §4, including battery's removal from the paid list. Unchanged by this record: `CARBON_BUILD_TARGET.md` §4 (1/N, full for 24 h, then halving every 24 h; no fresh-case tournament).

## 1. Who takes the crown

A challenger takes the crown when its score **exceeds the king's score on the same bank key by more than that Challenge's measured rebuild noise**.
- **Within the noise:** a tie, and **the king keeps it**.
- **There is no fixed margin.**
- **Rebuild noise is defined as:** the largest absolute difference in total score between independent fresh rebuilds of one recipe, evaluated on the same bank key. That means at least three rebuilds, on the Challenge's pinned build and judge images. It is registered per Challenge, with the digest of its measurement record.
- **It is measured, never set.** The packs lane measures it, and the Validator reviews it.
- **It's not the same as inference repeat noise** (`paired_repeat`), which reruns one frozen model. Rebuild noise retrains from the recipe, so it also covers build jitter. That's the jitter an exact copy would otherwise win on.
- **Until a Challenge has registered rebuild noise, promotion there is UNAVAILABLE.**

## 2. The king beating himself

If the incumbent's own miner takes the crown with a better model:
- the better model becomes the incumbent, which raises the bar for everyone;
- **the reward clock does not reset**, and halving continues from the original promotion.

"Same miner" is exactly the existing same-miner clock safeguard (`winner_eligibility.decide`: same hotkey, or the same coldkey frozen in the ledger). No new identity rule.

## 3. What stays unchanged

- The 1/N shares, the burn of unpaid allocation and integer remainders, and the eligibility ledger.
- An infrastructure or indeterminate result never wins and never dethrones.
- A contender that isn't scored never wins.

## 3a. A king that fails a mandatory gate (decided under the same delegation)

**A king whose model measurably fails a mandatory gate on a new evaluation version is dethroned.** That covers `MANDATORY_GATE_FAILED` and an invalid output (`CANDIDATE_INVALID`).
- A scored contender on the same key takes the crown.
- Without one, the Challenge has no winner, and its share burns until a valid winner exists.
- **A gate that is only unmeasured on our side does not dethrone; the king keeps the crown.** That covers infrastructure failure and indeterminate evidence.
- Other ineligible statuses (decision-outcome or leg-minimum) aren't gate failures and change nothing.

## 3b. Staleness (Validator, gate design)

- **BANK promotions skip `nomination_overdue` because they have no nomination pool,** so the field doesn't exist for them. That's why `decide` applies the overdue check only to `FINAL` promotions.
- **The same rule carries over to banks.** Once a Challenge's bank refresh cadence (its anti-leak control) is registered, a promotion decided on a bank version that is overdue for refresh pays nobody, mirroring overdue pools.
- **No cadence is registered yet,** so nothing is gated today. This is true by decision, not by omission.

## 4. The four-Challenge policy (decided under the same delegation)

`testnet-winner-v2-four-challenge-dev` lists Motor, Cooling, F08 and F02 (N = 4) as a **registered development version**.
- **Battery is not one of the four.** v1 lists battery, Cooling and Motor (N = 3). v2 drops battery and adds F08 and F02, following the owner's 19 October goal of four launch Challenges. Under 1/N, that changes who would be paid.
- `testnet-winner-v1` stays the registry's current policy, unchanged, as history.
- **The registry pin** (`sha256:4a95d313…`) is over the policy's **compact, sorted canonical JSON** (`winner_decay._canonical`), not the file's raw bytes, so a plain `sha256sum` of the file won't match.
- Adopting the score pack and any mainnet use stay the owner's at launch.

## 4a. Owner reversal: Battery is included (2026-10-19)

Asked by the Test Lead, "Add Battery as a fifth Challenge?", the owner answered **"Include it."** in the Test Lead's session. That reverses §4's removal of Battery from the paid list.
- `testnet-winner-v3-five-challenge-dev` lists Motor, Cooling, F08, F02 and Battery (`battery-fastcharge-ageing-development-v1`), so N = 5.
- `testnet-winner-v2-four-challenge-dev` stays registered as history. `testnet-winner-v1` stays current and unchanged.
- **N at launch is whatever policy is registered then.**
- Battery's pack labels use the sealed `battery-plating-ref-v2` (`VALIDATOR-PLATING-REF-V2-02`, on main).

## 5. Implementation (written on `codex/p3-paired-key`; brought to the base on `codex/koth-on-base`)

- `compare_private_pair` takes the comparator's `rebuild_noise` (`value`, `measurement_digest`). A challenger wins only if `total > king_total + value`. If no noise is registered, the result is UNAVAILABLE.
- `winner_eligibility.decide` accepts a bank-comparison promotion kind. It uses the existing predecessor check and the same-miner `no_reset`.
- A dethroning with no successor calls `PoolStore.vacate_incumbent`, which leaves no promotion, so the reward layer pays nobody and the share burns.
- The registry pin for v3 (`sha256:4b488bce0a43bc9b1f3914bb11b72d026ba2a1154fae5a83bc6649774c5add71`) is, like v2's, over the compact sorted canonical JSON.
- **The baseline run that sets a pack's leg minimums never contends.** The comparator requires `minimum_source_entry_ids` (the pack's `leg_minimum_source.entry_id`). Such an entry can neither take an empty throne nor beat a king (`leg_minimum_source_not_a_contender`).
- `rebuild_noise.measurement_digest` is checked for **shape only**. Whether it records three real rebuilds on pinned images is the packs-lane measurement and the Validator's review, not the code.

## §2a Hardware scope of the rebuild-noise margin (Carbon Validator, 2026-10-19)

- **Same host and same image:** the paired repeat is a same-host comparison under an identical procedure. Motor and Cooling allow ≤ 32 ulp, F08 requires exact equality, and F02 uses its measured across-runs margin. No cross-host claim is made (`exam_environment.py`).
- **King versus challenger may be on different hosts.** The `rebuild_noise` margin must therefore be measured over rebuilds that span every CPU or host class a validator may grade on, with at least one Targon host and one other host. A margin measured on one host class is registered for that class only. A comparison across classes it doesn't cover is `UNAVAILABLE`.
- **Today no Challenge has a registered `rebuild_noise`,** so every takeover is `UNAVAILABLE` and the crown can't move. This fails closed.
- **§2a is not enforced in code** (owner, 2026-10-20: "simple king of the hill best score wins for every challenge. Do not drift into over complication."). The KOTH design is frozen as is. The registered margin applies to the validator fleet as one host class; today that's Targon EPYC-v4 only. If validators of another class are admitted, the margin must be re-measured to cover them before they grade, which is an operational rule rather than a code check. G6 (a second rebuild on takeover) is not adopted.
