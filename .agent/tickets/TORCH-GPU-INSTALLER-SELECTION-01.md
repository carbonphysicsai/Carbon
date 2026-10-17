# TORCH-GPU-INSTALLER-SELECTION-01

Status: working contract; Root-assigned bounded usability repair, 2026-10-16.
Start: `origin/main` c8979fe62357df1c24affd1869d9805731f37b03, clean branch `codex/torch-gpu-installer-01`.
Primary hub map_ref: `SYSTEM/LAUNCHPAD` (mapped detail; selection meaning changes in the installer and adoption guide, not Hub placement, maturity or dependency).

## Problem and working decision

The current `--pytorch --gpu` installer selects the Torch CPU/analysis pair but the JAX accelerator GPU worker. The normal local GPU setup accepts a Torch GPU manifest and the v5 release publishes one. Make the two flags select the Torch GPU worker for local practice; keep `--gpu` alone on JAX. This prospectively supersedes the prior CPU-only `--pytorch` installer selection statement. No old release, tag, manifest or historical result changes.

## Expected change and tests

1. Keep the existing exact source, release-record, image digest, primary/analysis parent and setup/doctor checks. Select the GPU kind and builder from the explicit flag combination; never infer a backend from a caller Boolean or relabel another image.
2. The release installer must fetch the Torch GPU record before moving checkout, pull and record that exact image when GPU is selected, and keep the JAX default and its remote record behavior. A CPU-only Torch install must remain usable without a GPU pull.
3. A local-build `--pytorch --gpu` uses the existing `torch_gpu_worker_image.sh`; that script independently verifies its exact C03 parent. No image build is performed by this ticket's author.
4. Add focused fixture tests for default JAX, explicit Torch GPU build and release selection, missing Torch GPU release refusal before checkout, and recorded path. Update the adoption guide and installer help.

Expected paths: this ticket, dated working decision, `scripts/install_miner.sh`, `tests/cpu/test_graphite_pytorch_practice_adoption.py`, `docs/development/images/PYTORCH_PRACTICE_ADOPTION.md`. `installed.py` and remote Torch scope stay unchanged unless a test proves this contract needs them.

## Starting evidence and bounds

Open PR overlap check: #1413, #1385, #1255, #1246, #1222 touch none of the expected paths. Existing `GRAPHITE-PYTORCH-PRACTICE-ADOPTION-01` explicitly made the older CPU-only choice; this ticket makes the prospective local-GPU follow-up. Existing v5/c897 normal JAX install is being tested by Product independently. Windows author's bundled Python lacks pytest; canonical acceptance must run through `scripts/dev/canonical.sh` on a host when the scoped runtime is available, or protected CI after public PR authorization. No Product host state, image release/publication, GPU execution, remote-scope widening, provider spend, scientific tolerance, qualification or LIVE authority is in scope.

Completion predicate: focused fixture tests and appropriate canonical checks succeed on the final tree; complete-diff review closes findings; normal delivery gate and merge are owned by the authorized delivery lane. CUDA fit/predict remains separate actual host evidence.
