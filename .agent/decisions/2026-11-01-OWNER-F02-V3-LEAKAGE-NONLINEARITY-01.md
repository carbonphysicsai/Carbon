# OWNER-F02-V3-LEAKAGE-NONLINEARITY-01: add temperature-dependent chip power (leakage) to Burst Thermal 3.0

Date: 2026-11-01 (CST)
Status: DECIDED by the owner, directly in the Lead session. Owner's words: "A. Good catch. Keep checking for this stuff. It's what makes our system intelligent!"

Question (Validator, relayed by the Lead): cut sizing (21 solves, signed tables) showed that inside any box keeping the chip at or below 420 K, the temperature-dependent materials give less than the owner-signed 0.5 °C nonlinearity (best 0.44 °C at 432 K; 0.51 °C needs 471 K). (A, recommended) add a second realistic nonlinearity, chip power rising with temperature (leakage feedback), with sourced coefficients the owner signs, ~+2–3 days, $0–20; (B) allow up to 500 K; (C) ship without the nonlinearity bar.

## Decided
1. F02 3.0 adds temperature-dependent chip power (leakage feedback) as a second nonlinearity. This needs a deck change and sourced, two-pass-transcribed coefficients that the owner SIGNS by digest (remotely is fine).
2. The 0.5 °C nonlinearity threshold and the ≤420 K realistic-box rule stay as signed. Step 1 re-runs with leakage on.
3. F02 3.0 target ~9–10 Nov. Nothing graded is affected. Spend $0–20 within the USD 250 budget.
