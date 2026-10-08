# LAUNCHPAD-ACCEPT-04: a testnet submit target through the tunnel, and verdict readback

**Authority:** LAUNCHPAD-ACCEPT-01 (the critical path, steps A3 and A4).
Depends on LAUNCHPAD-ACCEPT-03.

**Status:** SPECIFIED.

## The gap

- No published endpoint exists, so no real submission has had a verdict
  through the Launchpad.
- Rehearsal 3a's validator (valV2 on the AX42) binds loopback. The owner's
  PC reaches it as `http://127.0.0.1:18467` through the tunnel loop.
- A profile may already name a loopback intake (`runner._intake_url`). What
  is missing:
  - a clear, preflighted way to name this target with its pinned receiver;
  - a refusal that says "open your tunnel" when the tunnel is down;
  - real proof that readback reaches the verdict on both doors.

## Build

1. **Review names an own intake together with its receiver**
   (LAUNCHPAD-ACCEPT-03). Two cases:
   - **Over MCP:** `carbon_setup_review` with `intakes.<challenge>` and
     `receiver_hotkey`.
   - **In the browser:** the Evaluation step.
   For a loopback URL, the preflight reads the intake's public facts:
   - the network must be testnet, with netuid 567, and the facts' Challenge
     must be the named one, otherwise `intake_mismatch`;
   - the receiver must equal the pinned one;
   - if the facts can't be read, the refusal is `intake_unreachable`, whose
     `next_step` names a tunnel or validator that isn't running. Carbon
     cannot tell which.
2. **The tunnel target is not published.**
   - **Working decision:** `published_endpoints.json` stays empty.
     - A loopback-through-tunnel address works only for hosts that hold the
       tunnel key.
     - Publishing it would mislead every other miner.
   - Publishing a public AX42 endpoint waits for the owner's exposure
     decision (plan §8).
3. **Verdict readback.**
   - Verify that `observe` and `campaign_view` show these on both doors:
     - the submission id;
     - the intake outcome (`QUEUED`, `UNAVAILABLE` or `REFUSED`, from
       `campaign.intake_outcome`);
     - the sealed outcome's public fields.
   - Repair any field that one door shows and the other does not.
   - Hidden scores, cases and seeds never appear.
4. **A service test** extends `tests/service/test_launchpad_production_journey.py`.
   The loopback intake runs with `require_commitment: true` and a
   commitment-reader stand-in, and the test drives freeze → commit → submit →
   observe to a sealed outcome. That is engineering evidence only. The real
   acceptance is plan §5 (A5).

## Boundaries

- Nothing touches the AX42, the tunnel account or its key.
- No change to the validator or the intake.
