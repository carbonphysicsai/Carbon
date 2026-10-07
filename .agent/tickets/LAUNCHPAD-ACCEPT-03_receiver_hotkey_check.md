# LAUNCHPAD-ACCEPT-03: the receiver-hotkey check at submit

**Authority:** LAUNCHPAD-ACCEPT-01 (the critical path, step A2).

**Status:** SPECIFIED.

## The gap

- `published_endpoints.json` lists a `receiver_hotkey` beside each intake,
  but it is "for reference only" (`environment_setup.py`, `RECEIVER_NOTE`).
- The intake client signs for whatever receiver the intake itself reports
  (`carbon/battery/intake_client.py`).
- So a wrong or substituted intake URL is signed for and sent to. The only
  guard is the signer's optional `--receiver` flag, which a miner may not
  set.
- FRESH_MINER_JOURNEY.md says so: "nothing checks it yet".

## Build

1. **A profile pins each Challenge's receiver.**
   - Add an optional `receivers` map, `{challenge_id: ss58}`, to
     runner-profile v2, beside `intakes`. It is an optional addition, so
     every older profile validates unchanged and `review_pin` does not move.
   - Review writes it:
     - for a published endpoint, from its `receiver_hotkey`;
     - for the miner's own intake, from a `receiver_hotkey` field Review now
       takes. That field is required with an own intake URL on a new Review.
   - Review first reads the intake's public facts, and refuses
     `intake_receiver_mismatch` (field `receiver_hotkey`) when they differ.
2. **Check before every signing.**
   - Before signing a submit, a resend or a status poll, the intake's
     reported `receiver` must equal the profile's pinned receiver.
   - Otherwise the result is REFUSED `intake_receiver_mismatch`, with nothing
     signed or sent, and `next_step` set to review the evaluation endpoint.
3. **A legacy profile with an intake but no receiver** keeps working, with a
   warning in the prelaunch review and setup's Evaluation step.
   - **Working decision:** do not refuse a profile written before this
     change, because refusing would strand running campaigns.
   - A new Review always pins a receiver.
4. **Docs:** update FRESH_MINER_JOURNEY.md, and `RECEIVER_NOTE` /
   `published_endpoints` copy, so the receiver is binding, no longer
   reference only.

## Tests

- A mismatch refuses before any signer call, on submit, resend and status.
- A match proceeds.
- Review pins from a published endpoint, and from an own intake.
- A legacy profile warns but is not refused.
- Door parity.

## Boundaries

- No change to the intake, the validator or the signer.
- This is authentication-adjacent. Surface it for security review.
