## 2026-10-08 — OWNER-WORKER-IMAGES-V2-01: install Carbon's released worker images, and cut worker-images-v2

**Authority.** The owner, 2026-10-08, verbatim: "approve worker-images-v2".
The Test Lead session relayed it to the Launchpad Acceptance session, which
answers finding LA-F10: the miner Launchpad cannot practise on Carbon's
released worker images.

**The finding (LA-F10).**
- Setup and campaigns accept a worker only if it was built from the install's
  exact source revision. `verify_current_worker` in
  `carbon/development_session/research_campaign.py` compares the image's
  `source_tree_digest` with the accepted implementation.
- `scripts/install_miner.sh` always built the images locally from the
  checkout.
- `scripts/dev/worker_image_release.py pull` (IMAGE-RELEASE-01) verifies a
  released image by digest and labels and writes its exact manifest. No miner
  path used it.
- So a current-main install refused the released images
  (`ghcr.io/carbonphysicsai/...`, release `worker-images-v1`), because they
  were built at another revision.

**The plan, as approved.**
1. Build `install_miner.sh --release <tag>`. It checks out the release tag
   and pulls every image by digest. Remote setup names the released
   reference, and local builds remain the fallback.
2. After that merges, PR Head cuts `worker-images-v2` from main with the
   existing release workflow (`.github/workflows/release-worker-images.yml`).
3. F01 is re-run with `--release worker-images-v2`. C4, a RunPod
   `ssh-container` pod, runs on the released accelerator image.

**Working decisions for step 1 (the executor's, within the ticket).**
- **What a release is.** A tag named `worker-images-vN` (the workflow's own
  pattern), fetched from origin's tags, whose commit is in main. Its records
  must be published as the release's assets. Each record must name its kind,
  the tag, and the tag's commit. Anything else is refused before the checkout
  moves.
- **Pull, never build.** The installer pulls the worker and the analysis
  image, and the GPU worker with `--gpu` or when one was installed before.
  `worker_image_release.py pull` checks every record field and the pulled
  image. The installer records the pulled manifests with `installed write`,
  as it records built ones.
- **Failure.** A failed pull stops the install before anything is recorded.
  Nothing is built. The message names the build command: the same tag with
  `--ref`, without `--release`.
- **Older releases.** A release whose own installer has no `--release` cannot
  be pulled this way, because that installer carries on after the move. This
  includes `worker-images-v1`. The install stops before the move and names
  the build command.
- **`--update` with `--release`.** It moves to the named release only when
  the release is at this install's revision or newer. It never moves back,
  and it does not look up a "latest" release. Going back is a plain
  `--release` install, named on purpose.
- **Remote setup.** The installer always keeps the GPU worker's release
  record. The `ssh-container` card names that release's
  `repository@sha256:...` reference first, but only when the GPU worker setup
  found is byte-for-byte that release's manifest. `push_worker_image.sh` is
  then the fallback. The container's build identity is still checked. For
  `ssh-docker`, sending the worker is unchanged.
- **Credentials.** No registry credential or key is handled. The public
  images need no login, and any other access is the host's own.

**Maturity.**
- Released images remain UNQUALIFIED_PUBLIC_DEVELOPMENT. Their security
  acceptance before mainnet remains the owner's (HUMAN_INPUT).
- The release verifies the CPU rows of its capability matrix.
- The GPU rows stay UNVERIFIED until the A40 run.
- Nothing here is qualified, paid, or on chain.
