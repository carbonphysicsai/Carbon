# OWNER-CATALOG-INFO-BUDGET-EXEMPT-01: the v6 information budget applies to miner-written graph recipes, not to Carbon-built catalog models

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "Yes to catalog fix"

## Context

With the v6 accounting fix live at freeze, Carbon's own Cooling 1.6 prior_krr catalog model measured 63,026 bytes, about 97% of it graph wiring. It was refused even at the 32 KiB budget (OWNER-FITTED-INFO-32KIB-AT-LAUNCH-01). The Validator ruled that the information budget guards against answer tables in graphs miners write, and that Carbon-built catalog models carry no table channel: miners choose only bounded settings.

## Decided

- The v6 fitted-information budget (32 KiB for the testnet launch versions) applies to miner-written graph recipes, at submission (validate.py) and at freeze in the graph lane.
- Carbon-built catalog models skip that information budget at freeze. They keep every structural, allowlist and state-size check.
- It ships in the next validator image move, with its tests.

## Bounds

- The miner graph-recipe budget is not loosened.
- Sets no score, threshold or economics.
- Testnet launch versions. Mainnet follows its own versions.

## Update (same day, later)

In the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0), the Validator proposed taking this exemption out of the final testnet launch image, so that every pack is rebuilt only once, at the post-launch image-tie removal (OWNER-IMAGE-TIE-QUICK-FIX-NOW-FULL-LATER-01). The owner replied directly: "Agreed. Just change the starting model…". The Validator relayed this to the Lead.

- The exemption is deferred to the post-launch release. It is not in Move B.
- For launch, Cooling 1.6's recommended starting model becomes MeshGraphNet, a served catalog entry that freezes under the 32 KiB budget. This applies in the Control Center and in the MCP door (`_baseline_start`), in Move B.
- The decision itself stands; only its timing changes.
