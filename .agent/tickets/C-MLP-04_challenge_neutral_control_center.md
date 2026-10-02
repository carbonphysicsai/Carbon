# C-MLP-04: miners reach the Control Center and choose what to mine

Owner authority: the owner, in chat on 2026-10-02:

> Yeah lets close this gap. we need miners to be able to get to the control
> center and then decide what challenge to mine. Nothing should be battery
> only or batter specific. Lets finish this buildout today

Recorded as `OWNER-CONTROL-CENTER-NEUTRAL-01` in `.agent/DECISIONS.md`.

**Primary Development Hub map_ref:** `SYSTEM/AGENT-EXECUTION`,
`HUB_UPDATE_REQUIRED`.

**Status:** implemented (engineering evidence only). A fresh-machine run of
the installer and a Challenge launch from it is the acceptance, and is a
person's (`docs/development/FRESH_MINER_JOURNEY.md`).

## The gap this closes

The survey of 2026-10-02 found:
1. no path from the website to the Control Center;
2. an operator-only file required in setup;
3. battery assumed throughout the Launchpad: imports, profile fields, feedback
   modes, the validator outcome's schema, GPU scopes, copy;
4. a stale Burgers identity in the pre-launch review.

## Slices

1. **A miner needs no operator file.**
   - `carbon/development_session/miner_network.py` gives a campaign its
     network without one:
     - Carbon's testnet context (the settled constants the onboarding doors
       already read);
     - the publisher, which is the hotkey at UID 0 of a finalized snapshot.
   - Setup's Agent step reads it when no `operator_config` is named, and
     writes `miner-network.json` (owner-only).
   - Profiles name exactly one of `operator_config` or `miner_network`. Every
     campaign entry point (`battery/campaign.py`, `research_campaign.py`,
     `miner_mcp/standard_cli.py`, the runner's registration read) binds
     through `miner_network.binding`.
2. **The Control Center names no Challenge.**
   - What differs by Challenge is read from that Challenge's campaign
     (`carbon/challenge_registry/campaigns.py`):
     - feedback modes and their schema;
     - the validator intake check;
     - GPU and rented-GPU scopes and their shape checks.
   - The Launchpad and MCP doors import no Challenge module
     (`tests/cpu/test_control_center_challenge_neutral.py`).
   - Profiles carry per-Challenge `intakes` and `validators` maps.
   - GPU practice is set up for a Challenge the miner names, and never
     launches another (`gpu_scope_is_for_another_challenge`).
   - The catalog shows every Challenge the same way: profiles, research
     provisions (`challenge_kit/standard.py`) and what setup offers.
   - The launch wizard offers the chosen Challenge's own feedback modes.
3. **One command to the Control Center.**
   - `scripts/install_miner.sh` takes a clean Linux machine through:
     - a machine check;
     - the locked environment;
     - building the pinned images locally;
     - recording them for setup;
     - starting the Control Center.
   - The Control Center reopens the profile setup wrote, without a flag.
   - `website/get-started/index.html` is the website's page for it; its
     deployment is a separate decision.
4. **Docs, programme state and Hub.**

## Recorded engineering decisions (2026-10-02)

- *The publisher is UID 0.*
  - UID 0 is the subnet owner's hotkey: the testnet runbook's "publisher
    UID 0", and OD-4a's burn UID.
  - It is read from a finalized metagraph snapshot.
  - A snapshot without UID 0 is refused (`publisher_not_on_chain`), never
    guessed.
- *Legacy profile fields keep their meaning.*
  - A C-MLP-03 profile's `battery_intake` and `paths.battery_validator` are
    read as the intake and validator of the one Challenge they were written
    for, through `runner.intakes`/`runner.validators`.
  - No profile is rewritten, so `review_pin` and run identities do not move.
  - The schema stays runner-profile v2: `intakes` and `validators` are
    optional additions, and every older profile validates unchanged.
- *A public refusal code changed.*
  - `feedback_mode_is_battery_only` is now
    `feedback_mode_not_offered_by_challenge`.
  - It means "this Challenge's campaign does not offer that mode", and FULL is
    every Challenge's.
- *The pre-launch review names no Challenge.*
  - It says `CHOSEN_AT_LAUNCH_FROM_THE_CATALOG`.
  - The chosen Challenge's description carries its exam environment and rule.
  - The retired Burgers identity is gone from the review and the preflight.
- *Only implemented Challenges can be launched.*
  - Reserved, deferred and retired Challenges are shown with their status and
    refused with the registry's code.
  - Making one launchable is that Challenge's own ticket (cold plate #342,
    motor #344, photonic #345).

## Boundaries

- Testnet 567 only; DEVELOPMENT; nothing here qualifies, pays or writes to
  the chain.
- No key reaches Carbon. The installer reads none and asks for none.
- The battery intake's exposure record is not made here
  (`OWNER-…INTAKE-EXPOSURE-NN`).
- The website page is a candidate. Deploying it, like the Ask Carbon
  component, is the owner's decision.
