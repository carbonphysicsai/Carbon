# OWNER-SEALED-EXAM-DELIVERY-01: sealed exams reach validators as signed, permit-gated packages, and validators hold them (an accepted risk)

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session ("I accept that validator exam decision"), after the Validator's recommendation in the same session.
Releases the hold of 2026-10-22 on the validator exam-access question.
Scope: all five Challenges. Testnet now; mainnet uses the same design. Mainnet containment and the other mainnet acceptances stay separate owner decisions.

## Decided

1. **Delivery:** the answer-key route (Workstream I2):
   - Carbon's producer signs each sealed batch package, together with the version's pack-set manifest (OWNER-FULL-EXAM-BANK-01).
   - The distribution host serves it **only to hotkeys holding a validator permit** on the network (btauth), and logs every fetch.
   - The validator checks the signature and every file digest, stores the package owner-only, and re-checks it at use.
   - There is no manual copy.
2. **The accepted risk:** **validators hold the sealed cases and their reference answers.** The owner accepts this as an unavoidable Bittensor risk. Grading stays with the validators (OWNER-VALIDATOR-IMAGE-ALL-CHALLENGES-01), not with a central Carbon service.
3. **Leak controls (required before mainnet; they don't block testnet):**
   - **per-validator traceable copies:** each validator's package carries its own embedded marker, so a leaked copy identifies its source;
   - **signed withdrawal:** a batch can be withdrawn from every validator at once, for rotation or a leak;
   - **already decided:** the full bank with one graded submission per hotkey per epoch, rounded-total-only feedback, the weekly overfit check, and rotation at most every 90 days with targeted cases.
4. **Not decided here:** the minimum stake for the permit (the network's own validator-permit rule applies).
