# OWNER-FITTED-INFO-32KIB-AT-LAUNCH-01: raise the v6 fitted-information budget to 32 KiB at launch if served catalog models exceed 16 KiB

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "1"

The Lead's two numbered options were for the case that some served catalog models exceed the 16 KiB v6 cap: "1. Raise the limit to 32 KB now, instead of after launch… 2. Stop offering those models until later." The owner chose option 1.

## Decided

- If Launchpad's measurement shows any served catalog entry on the four launch versions over 16384 bytes (v6 accounting), the v6 budget for those launch versions becomes 32 KiB (32768 bytes) at launch, in the same install as the v6 graph fix.
- If every served entry fits under 16 KiB, the budget stays 16 KiB at launch, and the post-launch 32 KiB raise in OWNER-TESTNET-ALL-FOUR-CROWNS-MAINNET-NEW-VERSIONS-01 is unchanged.
- An entry over 32 KiB stays refused (typed `fitted_info_over_budget`); this record does not raise the budget further.

## Bounds

- Testnet launch versions only. Mainnet is not covered.
- The Ribbed Bracket and Burst Thermal testnet lookup watch stays as decided.
- Sets no other threshold, score or economics.

## Update (same session, later)

Owner's words: "Add it now". He was answering the Lead's offer to include the 32 KiB limit without waiting for the measurement ("Reply '32 KB now' to do that, or approve the Launchpad step and we'll measure first").

- Decided: the v6 budget for the four testnet launch versions is 32 KiB (32768 bytes) at launch, unconditionally. It goes in this install via c781a13d3, with its tests re-run.
- The catalog-size measurement is no longer on the launch critical path. It still runs after the install, to list any served entry over 32 KiB, which stays refused.
