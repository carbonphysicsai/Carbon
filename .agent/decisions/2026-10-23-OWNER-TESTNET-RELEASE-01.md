# OWNER-TESTNET-RELEASE-01: a testnet release to miners, separate from the one mainnet image

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). The owner was asked two questions: "(1) treat this as a testnet image, separate from the one final mainnet image?" and "(2) when the checklist passes, may PR Head push to the public repo and publish the testnet images?" The owner replied: "1 yes 2 yes".
Amends: the publish-once rule (owner 10-20, image-publish-after-worker-freeze). "Once" now means the **mainnet** image. Testnet images may be published and updated as the work lands.

## Decided

1. **A testnet image is allowed now.** It is tagged as testnet and is not the mainnet image. Later testnet updates are allowed. The one registered recalibration still runs on the final image, on the registered 4090 class.
2. **Public push and testnet image publish are authorized** once **every blocking item** in codex-queue/reports/TESTNET_RELEASE_CHECKLIST_20261023.md passes on the release head (integration/testnet-rc1 or its successor), verified by the Validator.
   - PR Head performs the push.
   - The Lead confirms with the owner one last time immediately before the push, because the push cannot be undone.
   - `claude/launchpad-backbone-catalog` / 68bfee956 is never pushed.
   - No sealed or private material, keys, balances or account figures may be in the pushed tree or the images.
3. **Scope:** testnet 567 only. Mainnet launch, the mainnet image and the chain actions stay with the owner's go/no-go.

## Ship conditions added by the owner (same day, directly to the Lead)

The owner's words: "this doesn't ship unless all 4 challenges are working, launchpad is operationally sound, they have full backbone access, limits only set by them, and all avenues work, and being scored correctly".

So the push and publish in item 2 above also require **all** of the following, verified on the release head:
1. **All 4 launch Challenges work end to end:** Motor, Cooling, Ribbed Bracket, Burst Thermal.
2. **Launchpad is operationally sound:** install, update, setup, practice, freeze and submit, with no open blocker.
3. **Full backbone access:** the whole Carbon-tested catalog is available on every launch Challenge (catalog v2).
4. **Only miners set limits:** the no-Carbon-limits versions have landed. Only exam protection and cited external facts remain.
5. **Every avenue works:** the Launchpad page with Graphite; the headless CLI/MCP route; the miner's own agent; local GPU and remote GPU (PyTorch and JAX).
6. **Scored correctly:** the final scoring is live (D = min(V, C) with decision fidelity, the physics half, and the KOTH margin rules) and has been checked on each Challenge.

## Further owner condition (same day, directly to the Lead)
"don't ship anything that could benefit from a pending update". The release head must already contain every in-flight update that would improve what ships. Examples are catalog v2 entries, priors, the GPU fixes, Graphite fixes, and the no-Carbon-limits v2 versions. No push or publish while such an update is still pending. Updates parked as POST-TESTNET under the scope freeze are not "pending" for this rule.
