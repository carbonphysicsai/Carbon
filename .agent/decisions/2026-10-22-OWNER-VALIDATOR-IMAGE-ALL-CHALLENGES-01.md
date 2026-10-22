# OWNER-VALIDATOR-IMAGE-ALL-CHALLENGES-01: the one validator image can grade any Challenge submission

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session: "We just need to ENSURE that every validator that downloads the carbon validation image can execute that for any challenge submission they receive."
Scope: a requirement on the published validator image and its install. It doesn't decide exam delivery to validators; that question is on hold (2026-10-22).

## Required

**Any validator** that downloads the one published Carbon validator image and installs it on a registered-class host must be able to **rebuild and grade a submission for every Challenge**, through **every served construction route**, with no extra build and no manual step:
- **the Challenges:** Motor, Cooling, Battery, F08 and F02;
- **the routes:** catalog backbones, graph recipes and bundles;
- **the runtimes:** the PyTorch and JAX runtimes, including Battery's JAX path. The PyTorch and JAX backends must behave identically, with parity tests.

## Proven before the image is published, once

- **E9 is added to the internal-test exit criteria:** on the class host, one install from the **candidate** image rebuilds and grades ≥ 1 submission per Challenge, for each served route, from a clean machine.
- The candidate image's digest is the one that is later published. If any Challenge or route fails, the image is fixed **before** the publish, never after.
