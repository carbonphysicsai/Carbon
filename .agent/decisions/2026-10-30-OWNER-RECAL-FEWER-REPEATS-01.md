# OWNER-RECAL-FEWER-REPEATS-01: trim the testnet launch recalibration repeats to open all four Challenges sooner

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "yes trim the repeats and bring that time in as much as we can."

He was answering the Lead's offer: "recalibrating with fewer repeat runs would bring Burst Thermal in by several hours. The trade-off is a less certain winning margin."

## Decided

- For the four testnet launch versions (Cooling 1.6, Ribbed Bracket 1.7, Motor 1.5, Burst Thermal 2.5), the one registered recalibration on the validator box runs with fewer repeat rebuilds than planned, as few as the registered measurement method still supports.
- The Validator sets the repeat count, using the method's own minimum. It records the count and the expected time saved before running.
- A Cooling recalibration already in progress is restarted with the trimmed count only if that finishes sooner.

## Bounds

- Fewer repeats means a less certain margin, so uncertainty must widen the margin, never narrow it. OWNER-KOTH-MARGIN-SEED-SPREAD-01 still holds: the margin is at least the measured seed spread and rebuild noise.
- Values are used as measured (OWNER-RECAL-VALUES-TESTNET-NOW-01). No agent picks or tunes a number.
- A measurement that fails its own checks is reported, not used.
- Testnet launch only. The full repeat count returns at the week-1 full-bank re-pack, and mainnet uses its own recalibration with the owner's approval.

## Update (same session, later)

The Validator set: 3 same-seed repeats per panel member (each already holds a bit-identical official GPU receipt); any member whose repeats differ goes to a fallback count; control seeds stay at 10, since fewer seeds would narrow the seed spread.

Owner's words: "5 is the back up. not 10. press with that"

- Decided: the fallback for a member whose 3 repeats differ is 5 repeats, not 10.
- Unchanged: 3 repeats per member; control seeds at 10; uncertainty widens the margin, never narrows it.
