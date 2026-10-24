# OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01: the larger worker resources are switched on, testnet only

Date: 2026-10-23 (US Central; 2026-10-24 UTC)
Status: **APPROVED by the owner, directly.** The owner typed, in lp-u45's session (local_fc5334bb, the U45 session; Claude Code transcript `bbc8bae7-037e-4994-8f8d-50f30791cc42`): "approve LARGE_MODEL_PROFILE_APPLIED for testnet only". The owner then confirmed it to the Lead directly in chat ("already did both").
Confirmed directly to the Validator, 2026-10-24.
Signed: lp-u45 (received the owner's words first-hand); the Lead (co-signs; the owner confirmed to the Lead directly).
Applies: OWNER-WORKER-RESOURCES-LARGE-MODELS-01, whose condition is met (below).

## Decided (testnet 567 and rehearsals only)

- `carbon/reconstruction/worker/model.py` `LARGE_MODEL_PROFILE_APPLIED = True`.
- Every Challenge version serving Level 4 allowlist v7 launches its worker under the larger profile: 4 CPU, 16 GiB lane memory, 4 GiB scratch, 2 GiB output, 2 GiB shared memory.
- That is the 13 versions in `served_versions.V7`: Battery 2.1; Cooling 1.2, 1.3, 1.4; Motor 1.3, 1.4; Burst Thermal (F02) 2.2, 2.3, 2.4; Ribbed Bracket (F08) 1.3, 1.4, 1.5.
- Versions on allowlists v1, v5 and v6 keep today's C-03 envelope, and the C-03 CPU profile digest is unchanged.
- Unchanged: pids, nofile, network none, read-only root, capabilities, and the rebuild wall (OWNER-SANDBOX-REBUILD-WALL-01 is separate).

## Testnet-only scoping (the Lead's option (a))

- The flag is a module constant with no network condition in code: any image built from a tree where it is True serves the larger resources.
- **Release rule (LANDING_QUEUE, item 13): no mainnet image from a tree where `LARGE_MODEL_PROFILE_APPLIED` is True.** The mainnet image is built from a later commit with the flag False (owner-held).
- The invariant test `tests/invariants/test_large_model_profile_testnet_only.py` fails if a mainnet profile is built in a tree with the flag on: the registered validator host class scoped MAINNET, or a validator GPU device class accepted for a network other than testnet.

## The condition it rests on

OWNER-WORKER-RESOURCES-LARGE-MODELS-01 required a real-lane containment run at the new profile before any version serves it. Containment Run F at `c21e69062f1afd54f5405d661c0a8ea498808bff` (`codex-queue/reports/CONTAINMENT_RUN_F_c21e69062_20261022.md`) passed: every part rc 0, no skips, C-03 8/8, and `tests/service/test_c03_worker_resources_service.py` 2/2 on real Docker, the first C-03 v7 launch on the real daemon.

## Not covered

- **Mainnet.** It needs its own acceptance of this profile on the mainnet validator class (TBD until launch), or the gate set back to False, before mainnet serves.
- The rows OWNER-CONTAINMENT-ACCEPT-TESTNET-01 left open, and any later change to the sandbox, images or these values.
