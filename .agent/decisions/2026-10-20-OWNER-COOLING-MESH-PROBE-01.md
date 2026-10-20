# OWNER-COOLING-MESH-PROBE-01: Cooling mesh-family probe approved, cap USD 4

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Yes").

## Decided

- **The change:** Cooling's reference mesh family is changed, with z graded under the hot spot plus local refinement near it.
- **The probe:** one probe cell is solved at three levels (r 2, 2√2 and 4). That's about 5.3 CPU-h, as in `PACKS_COOLING_RR11B_RESULT_20261020.md` option A.
- **The cap is USD 4.**
- **Stop trigger:** the step ratio stays above 0.7. Then stop and report.
- **Pass criterion:** an observed order of at least 1.5 on the last pair.
- **Not decided here:** the finer round (option B, about USD 15 on the usual VM). It needs its own figure, and only if the probe passes.


## Related

The Motor RR-13 rerun on the AX42, approved in the same session, is recorded in OWNER-MOTOR-RR13-AX42-01.
