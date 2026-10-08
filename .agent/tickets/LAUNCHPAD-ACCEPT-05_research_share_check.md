# LAUNCHPAD-ACCEPT-05: the research share check at the launch door

**Authority:**
- LAUNCHPAD-ACCEPT-01 (stage D);
- GRAPHITE-MINER-S3 and S4;
- OWNER-LAUNCHPAD-PROD-02 decision 1: no Carbon output cap.

**Status:** SPECIFIED.

## The gap

- `carbon/agent_campaign/graphite/miner/driver.py` publishes
  `research_share_shortfall`. For a FULL launch, it returns
  `{stage, dimension, share_cap, per_call}` when the research share, or the
  hunt's part of it, cannot pay one model call's reservation under the
  miner's ceilings.
- `check_research_share` refuses `research_share_too_small`, but only inside
  the driver, before its manifest freezes.
- GRAPHITE-MINER-S4 recorded that the doors do not call it. It needed the
  selection a new plan freezes, which now exists on main.
- So the launch form and the cost calculator accept a FULL launch that will
  then be refused.

## Build

1. **`launch` calls `research_share_shortfall`** for FULL Graphite launches.
   - It uses the same selection the campaign would freeze: the model's full
     output by default, or the miner's own cap.
   - When the share falls short, `launch` refuses `research_share_too_small`
     with the shortfall's fields and a `next_step`: raise the money ceiling,
     raise the research share, or choose BUILD.
2. **`options`** returns the smallest money ceiling that clears the check at
   the chosen model and share.
3. **The browser's estimate** shows that minimum before launch
   (`app.js`, the hunt estimate).

## Tests

- **Parity:** for the same inputs, the door's verdict equals
  `check_research_share`'s.
- **Boundary values:** the refusal holds at one nano below the minimum, and
  launch passes at the minimum.
- Door parity between browser and MCP.

## Boundaries

- No change to the reservation rule, the default share or any ceiling. The
  miner's economics stay the miner's.
