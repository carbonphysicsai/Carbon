# VALIDATOR-TESTNET-GPU-CLASS-01: testnet grades on the same GPU class as mainnet. One recalibration

Date: 2026-10-22
Status: a Validator record applying a standing owner rule. There is no new owner decision.

Authority:
- the owner's standing rule that testnet must operate exactly like mainnet (2026-10-04: "testnet operating exactly like mainnet … I do not want to have to build a new validator at all when we switch from testnet to mainnet");
- OWNER-VALIDATOR-GPU-CLASS-01 (2026-10-22), which picks the RTX 4090 class after a two-host identity check.

## Recorded

1. **The testnet grading host moves to the mainnet class:** the RTX 4090, or the L40S / RTX 6000 Ada if the identity check fails. The CPU-only ccx33 class (VALIDATOR-HOST-CLASS-CCX33-01) stays recorded, but it is not used for the registered recalibration.
2. **There is one registered recalibration, on that GPU class,** with the published image. The rebuild noise and rebuild wall are measured on the same class. The ccx33 registration does not carry over, and no second recalibration is planned.
3. **The ccx33 host may keep running non-grading roles,** such as the weights timer and the receiver front end, if useful. Grading that counts toward KOTH or weights runs only on the registered GPU class.
