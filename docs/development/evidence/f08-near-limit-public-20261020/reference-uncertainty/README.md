# F08 reference uncertainty (Validator review; $0, from RR-PACKS-07)

`f08-reference-uncertainty.json` (`carbon.f08.reference-uncertainty.v1`, its own sha256
`cb889778…`) is produced by `f08_reference_uncertainty.py` from the committed ladder
(`ladder-observed.json`, `26aef1d5…`): 8 cases × 3 rungs (h = 3, 2.25, 1.7 mm).

| Quantity | Limit | Lowest observed p | Largest fine-level estimate | **U** |
|---|---|---|---|---|
| worst_dynamic_mm_per_n | ≤ 0.15 | 2.235 (pilot-0004) | 3.85e-5 | **3.9e-5 mm/N** |
| static_tip_mm_per_n | ≤ 0.03 | 1.995 (pilot-0004) | 6.70e-7 | **6.7e-7 mm/N** |

- **Per-case p:** 2.2–3.2 for dynamic and 2.0–2.9 for static. No zero differences.
- **Stop triggers:** none fired. Every p is at least 0.5, every case is monotone and
  shrinking, and no case flips between the h3 and h1.7 labels.
- **Angular term:** not applicable.
- **The one adaptation (please confirm):** the Motor method is written for ratio 2.
  - F08's rungs have ratios 1.333 and 1.324, so p and the estimate use Roache's non-uniform
    form, with the estimate |φ2 − φ1| / (r21^p − 1).
  - It reduces exactly to the written rule at r = 2. That is checked: synthetic h² data gives
    p = 2.000 at both ratio 2 and F08's ratios.
- **For scale:** the ladder's smallest dynamic margin, 0.00286, is about 73 × U.
- **Mass:** analytic CAD, so it has no mesh U.
