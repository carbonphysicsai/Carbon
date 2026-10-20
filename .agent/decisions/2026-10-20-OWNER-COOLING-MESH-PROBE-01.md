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

## Related, same session: the Motor RR-13 rerun on the AX42

The owner approved re-running RR-13's 14 infrastructure-failed cases on the AX42, at no marginal cost. Owner, verbatim: "yes start motor ... in AX42".
- **Probe first:** one L2 case alone, recording peak RSS and peak disk.
- **Then:** parallelism set from whichever limit binds.
- **Stop trigger:** the alone-run fails the same way.
- **Pass criterion:** all 14 OK, with mesh identity and `executed_image_verified`.
- **What it changes:** whether RR-09's Motor rows bind or go UNRESOLVED.
