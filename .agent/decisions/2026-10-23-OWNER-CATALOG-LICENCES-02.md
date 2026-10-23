# OWNER-CATALOG-LICENCES-02: base-image components found on the pinned images

Date: 2026-10-23
Status: **DECIDED by the owner, directly in the Carbon Validator's session.** Answer: "Accept all five (Recommended)".
Extends: OWNER-CATALOG-LICENCES-01 (its "not covered: components added after this list").
Source: baselic.py on the pinned images. `codex-queue/claude-ops/results/pair-v2/baselic-torch.json` sha256 0dec05d8b439e435e1e00042db4fc017f7de4241ac09e6f37cbb1441696f6a09 (the Torch worker image) and `baselic-jax.json` sha256 5b2ce8f33eab06ca09d38fc15f95811bb275e1621a0c4925cad6059874a92315 (the C-03 worker image), per the catalog worker.

## Accepted (base image only, unmodified, with their licence texts kept)

- **sentry-sdk** (MIT), Torch image.
- **google-crc32c** (Apache-2.0 upstream; its metadata declares none).
- **chex** (Apache-2.0) and **toolz** (BSD), JAX image.
- **orjson 3.12.0** (MPL-2.0 AND Apache-2.0/MIT): file-level weak copyleft, treated as certifi and tqdm are.

There is no GPL or LGPL in either image. `carbon 0.9.0` in the JAX image is Carbon's own code.

## Note (not a licence matter)

sentry-sdk is a telemetry client. The worker sandbox runs with `--network none`, so it cannot send anything. Keep it that way: any change that gives a worker network access must re-examine it.

## Not covered

Components added after this list; any modified MPL file.
