# OWNER-SANDBOX-REBUILD-WALL-01: a 30-minute sandbox build/run limit for the new versions (testnet)

Date: 2026-10-23
Status: **ACCEPTED by the owner, directly in the Carbon Validator's session.** It was asked as a security acceptance: applying the registered 30-minute rebuild limit (OWNER-REBUILD-TIME-LIMIT-01) to the four new versions lets the sandbox run each build for up to 30 minutes instead of 10, with memory, disk, network-off and the other sandbox limits unchanged. Answer: "Accept, testnet only (Recommended)".
Amends: the testnet containment acceptance (v7 bounds), for this one dimension only.

## Accepted (testnet 567 only)

- **Versions:** Motor 1.4, Cooling 1.4, Ribbed Bracket (F08) 1.5 and Burst Thermal (F02) 2.4. Their `build_wall_seconds_max` and `inference_wall_seconds_max` are **1800 s**, and the launch deadline for those versions matches.
- **Existing versions keep 600 s** and their digests (Option C).
- **Every other sandbox bound is unchanged:** memory, CPU, disk, process count, network none, filesystem, capabilities.
- **It doesn't depend on the large-model profile flip** (`LARGE_MODEL_PROFILE_APPLIED` stays as the owner holds it).

## Not covered

Mainnet; any other version; any other sandbox dimension.
