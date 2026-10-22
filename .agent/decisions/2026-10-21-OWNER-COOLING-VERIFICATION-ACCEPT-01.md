# OWNER-COOLING-VERIFICATION-ACCEPT-01: Cooling code verification accepted

Date: 2026-10-21
**Status: ACCEPTED by the owner.** The owner accepted the record directly in the Carbon Validator's session. The Validator relayed it to Data Collection, who records it here. Code verification is a science acceptance reserved to the owner. This record takes effect when the PR Head merges it, confirming it with the owner as for OWNER-CODE-VERIFICATION-ACCEPT-01.

## Accepted

The finalised verdict is in `docs/development/evidence/cooling-code-verification-20261020/cooling-verdict.json`. It was introduced at commit `370e8c569656445af31cf8edd260cddb030f8b7e` and is updated here to state the acceptance. It covers Cooling's OpenFOAM image `opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319` under OWNER-COOLING-VERIFICATION-01's criteria: the finest-pair order must lie in [1.7, 2.3] for every reported norm, and conservation and interface terms must be at round-off.

| Rung | Test | Finest-pair order / result |
|---|---|---|
| 1 | Poiseuille (closed form) | 2.0 |
| 2 | Nusselt (closed form) | 2.0 |
| 3 | Conjugate coupling | Round-off accepted as a demonstrated floor. RR-12d's FAIL came from a miscast rule (Validator, RR-14 decision §3). |
| 4 | Manufactured energy (RR-12c, `mms_energy.py`) | L2 2.000 / 2.000, L∞ 1.995 / 1.999 |

Coverage, as the verdict states:
- the manufactured rung verifies the shared finite-volume operators;
- the production enthalpy-form energy path is verified by the closed-form rungs 2 and 3 at the levels tested;
- a manufactured case through chtMultiRegionSimpleFoam remains an open option, not required.

## Scope

This record accepts code verification of the discretisation only. It is not reference adequacy, physical validity or qualification. The reference uncertainty is a separate, Validator-reviewed record (`cooling-reference-uncertainty-20261020`).

A rebuild or re-pin of the image needs a new run and a new acceptance.
