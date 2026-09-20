# Accelerator worker image rebuilt against the lane-split revision

Recorded 2026-09-20 under programme #209, ticket C-CORE-19, work package item W1.
Build evidence. It qualifies no hardware, authorizes no attempt and grants no
execution authority. No device was attached and no attempt of the authorized
batch was spent.

## Why a rebuild was owed

The portable workload profile's digest moved when the host-pinned fields left it
and the portable shape became `carbon.accelerator-profile.v2`. The previously
retained image was labelled with the old digest, so it no longer matched the
profile a launch would be admitted under. `verify_image_and_toolkit()` compares
those labels and would have refused it - correctly.

## Identity

| | |
| --- | --- |
| Image ID | `sha256:e4a2014daa9abc4e3df0bb890bc031a6a859ae21f42d4bec0a0494e25d949794` |
| Retention tag | `carbon-accelerator-worker:de7fa60b` |
| Source tree | `sha256:16709159fbabd48accff0fe1e34c9737de41af293d561e6217a86a9cde478dde` |
| Base image | `sha256:1cf27134c044fd8ec4928954321277eb8359c4667f6afbf9643b7a4950ff152b` |
| Build recipe | `sha256:9303bb497d53de7af2737a97c5c358c2ab3de0b1db0ff6a580a0eaaa2f5433ad` |
| Entrypoint | `sha256:ae36d483b7c7c3b045a62d583ec5f8d5304c181ead2b4add3fe17a214e039119` |
| Wheel | `sha256:7700770b8f2c92d3ba5e84a3c8ea2c44a383d2e5e10c88f4a97a04f10bed76f2` |
| Environment lock | `sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434` |
| **Accelerator profile label** | `sha256:e1d8aefd79a540de086a293e430f4b6b255c749b60dc7bd8d3c51235534671cf` |
| Scope label | `UNQUALIFIED_PUBLIC_DEVELOPMENT` |

The profile label matches `GPU_PROFILE.digest` at this revision, which is what
the rebuild was for.

## Provenance is exact, and was enforced rather than assumed

`source_tree_digest` is computed as `git archive --format=tar HEAD | sha256`, and
it matches this revision's tree byte for byte. The build ran from a **clean
checkout**: a first attempt with uncommitted documentation present was refused by
the builder itself -

> `Carbon C-03 worker image build failed: the source checkout must be clean
> before image identity is assigned.`

- which is the guard working. The documentation was committed and the build
re-run, so the recorded identity describes a real revision rather than a working
tree that happened to exist once.

## What this is not

Not an acceptance, not a qualification, and not authority to attach a device. The
image existing means a launch's image check can now pass; it establishes nothing
about whether the launch would succeed, and nothing about hardware.

The earlier image built against the previous profile digest is untouched and
unrelabelled; it remains what it was, for the revision it was built from.
