# OWNER-CATALOG-LICENCES-03: five named dependency wheels cleared

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Yes, all five"). The Validator named each library and its licence in the question.

Amends: OWNER-CATALOG-LICENCES-02.

## Decided

These wheels ship in the six DeepXDE/THUML catalog entries, and **they may keep shipping**:

| Wheel | Licence |
|---|---|
| joblib 1.5.2 | BSD-3-Clause |
| scikit-learn 1.7.2 | BSD-3-Clause |
| scikit-optimize 0.10.2 | BSD-3-Clause |
| threadpoolctl 3.6.0 | BSD-3-Clause |
| pyaml 25.7.0 | WTFPL |

- **Conditions:** each wheel's licence text and notice ship with it.
- **The tracked list:** the catalog licence manifest, `carbon/backbone_catalog/LICENCES.md`.

**Unchanged:**
- GPL code (KNO) is not published.
- Nothing reaching `68bfee956` is ever pushed.
- The versions of the image-supplied libraries (neuralop, physicsnemo) are re-read from the published image when it is built.
