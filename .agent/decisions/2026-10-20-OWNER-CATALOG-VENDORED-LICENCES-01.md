# OWNER-CATALOG-VENDORED-LICENCES-01: the backbone catalog may publish vendored third-party source with its licence

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Yes, publish").

## Decided

- **The backbone catalog may vendor third-party model source into the public repository,** with each project's own LICENSE file kept beside it.
- **Licences in scope:** MIT (neuraloperator, THUML and others), Apache-2.0 (PhysicsNeMo), LGPL-2.1 (DeepXDE) and EPL-2.0 (jNO).

## Not covered

- **GPL code:** KoopmanLab (KNO) stays excluded, by the earlier owner instruction.
- **Code with no licence:** WNO stays excluded.
- **Any commit containing those bytes is never pushed.** The superseded catalog `68bfee956` and its r1–r3 bundles embedded KNO and WNO. The landing catalog was squashed (r4 `65b8903fb` onward) so that no landed history reaches them. The pre-push check is `git merge-base --is-ancestor 68bfee956 <ref>`, run per ref.
