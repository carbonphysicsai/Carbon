# OWNER-MODULAR-CHALLENGES-01: Challenges are easy to add, remove and modify

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session: "make it easy to add and remove challenges from this design. It should be highly modular. We want this system to be able to add, remove, and modify it's challenges easily."
Scope: all Challenges and the whole exam/validator path. Built in Phase A, before the one image build.

## Decided

- **One folder per Challenge:** each Challenge is a single plugin folder, `carbon/challenges/<id>/`, holding a manifest plus one implementation of a shared Challenge interface. A registry discovers the folders, and every central per-Challenge list in the codebase becomes a registry lookup.
- **The three operations:**
  - **add:** the folder and manifest, plus passing the shared end-to-end conformance test;
  - **remove:** mark it `retired` (it stops serving, grading and weights; history is kept);
  - **modify:** a new immutable version.
- **Weights:** each Challenge's weight share stays owner-set. If the registry's active Challenges and the weights policy disagree, weights fail closed until the owner sets the shares.
- **Design:** codex-queue VALIDATOR_MODULAR_CHALLENGES_20261022 (the Validator's). Contract rule C16.
