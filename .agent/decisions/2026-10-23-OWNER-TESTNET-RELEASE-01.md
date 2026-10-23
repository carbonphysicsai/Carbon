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
