# OWNER-PRACTICE-BANK-PICKS-DELEGATED-01: harder public practice bank values (owner delegated the picks to the Lead)

Date: 2026-10-31 night (CST)
Status: DECIDED by the Lead under explicit owner delegation in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "you answer these optimally", quoting the three questions (N per Challenge, distance from hidden exam cases, how far out practice goes).
Plan: codex-queue/reports/HARDER_PUBLIC_PRACTICE_BANK_PLAN_20261031.md (rev 2 sha fe3ba7a04e135da709dafa4af6a6de54f28355a3d98cf63f9cf0fabe48ea635c, plus the Validator's §8 leakage ruling).

## Decided

1. N = 40 new public practice cases per Challenge (Motor, Cooling, Ribbed Bracket, Burst Thermal): about twice the per-target A_gen count, enough to separate good from default models on practice.
2. Minimum distance from every sealed cell, sealed probe and pool design (live and next exam versions) = 0.10, max-norm over inputs normalised by the signed extended region's range. Same as the proof grid's control radius (the Validator's recommendation).
3. Public draws come from the inner band only, with the band's outer edge at 0.5 of each extension (the inner half). The outer half stays sealed-only, so the exam keeps testing extrapolation (Validator ruling (d)). Registered with the bank version; never moved after seeing results.

## Conditions

- The Validator's Q1a holds: the draw seed stays private; overdraw in custody, publish exactly N; publish no candidate list, refusal count, labels or per-case pass/fail; only one boolean ("all N satisfy the rule") plus the bank digest leave custody.
- Owned hosts only, $0 rented compute. The 6-case probe on the inner band comes first, with stop rules: fewer than 5 of 6 OK, or the good model still scores at the ceiling (the Validator's probe pass band: the good model's practice A at least 0.05 below in-TRAIN, and good vs default separating by at least 0.05).
- The bank never enters scoring. Testnet; a new practice bank version.

## Why these values

40 gives a stable practice signal at a few hours of owned-host time per Challenge. 0.10 is the existing control radius, so a public case is never "near the optimum" of a sealed target. 0.5 matches the Validator's "outer half sealed-only" ruling exactly, the most conservative band that still widens practice beyond the TRAIN interior.
