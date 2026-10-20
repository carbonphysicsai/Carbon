# F02 reference uncertainty: the single-refinement bound (Validator review; $0, from RR-PACKS-04)

`f02-reference-uncertainty.json` (`carbon.f02.reference-uncertainty.v1`, its own sha256
`29c3d7e6…`) is produced by `f02_reference_uncertainty.py` from the RR-04 judgement
(`f7cc8c87…`), by your rule. The rule takes, over the eight cold actions, the largest of
|mesh2 − primary| and |dt0.5 − primary|, rounded up to 2 significant digits. It is labelled
"single-refinement bound".

- **Largest shift:** 0.01141 °C (cool-rect-long-high, mesh2).
- **The near-limit four:** 0.0055–0.0057 °C.
- **U(peak_top_c) = 0.012 °C.**
- **Label flips across rungs:** none.
- **For scale:** the closest decision margin, 86 W at 95.206 °C (0.21 °C), is about 17 × U.
