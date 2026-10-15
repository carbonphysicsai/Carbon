# GRAPHITE-PYTORCH-PRACTICE-ADOPTION-01

Status: working contract; Root-assigned bounded engineering repair, 2026-10-15.
Start: main `3ee7144aa0bd35b0f693d9a154e07bea553eff29`.
Primary map_ref: SYSTEM/LAUNCHPAD. Hub maintenance waived by current OWNER-DX-03.

## Problem and scope

The released CPU Torch worker can serve JAX and PyTorch practice through the
existing exact-lock `BatteryPractice` selection. The v4 installer selects C03,
and v4 publishes only C03-parented analysis. Substituting the Torch primary
alone correctly fails the analysis-parent equality check.

Keep the existing primary/analysis interface and backend checks. Add an explicit
`install_miner.sh --pytorch` route selecting a CPU Torch primary and analysis
child built on that exact primary. Publish an additional `torch-analysis` kind
through the existing release pipeline. Keep default C03/JAX behavior and all
source, image, lock, runtime, parent-label and parent-layer verification.
Existing v4 artifacts/history remain immutable; v4 has no Torch analysis pair.

## Plan and expected manifest

1. Record contract and delegated decision before implementation.
2. Extend release analysis-kind handling and the closed parent-reference helper
   for the CPU Torch parent; build/push the parent before its analysis child.
3. Carry the additional companion through build, pull, verification and release
   assets. Add explicit installer selection for local and released images.
4. Add focused fixture tests for real installer arguments, primary/analysis
   pairing, record identity/refusals, parent reference and default regression.
5. Run static checks here and canonical remote CI; request independent review
   and send exact PR/head/results to Root, the merge and host actuator.

Expected paths: this ticket and its dated decision; scripts/install_miner.sh;
scripts/dev/{release_worker_images.sh,worker_image_release.py,worker_parent_ref.sh};
scripts/dev/release_parent_rehearsal.sh;
carbon/development_session/research_image.py;
.github/workflows/release-worker-images.yml; exclusive focused CPU test;
existing release-workflow test expectation; dedicated adoption instructions and
their link in docs/development/images/RELEASED_WORKER_IMAGES.md.

## Validation and completion predicate

Local application execution is unavailable by Root's current operator ruling.
Static syntax/diff/UTF-8/delivery checks are author evidence only. Canonical CI
must run focused adoption, installer, release and analysis tests plus all
scope-required regression checks and exact-head Merge gate. Negative controls
must refuse missing companions, wrong kinds/parents and changed identities.
Completion is conditional on green exact-head CI, independent closed review and
Root's guarded normal merge. Runtime GPU validation and publication are separate
Root-owned evidence; they are not earned by fixture tests.

## Boundaries and adoption dependency

No new backend permission, scientific threshold, score, official data access,
qualification, security acceptance, deployment or provider spend is authorized.
No local host/container/model/solver execution or image build in this lane.
Root must adopt matching accepted source and freshly published matching images
after final merged source is selected. Do not mix new source with v4 by relabeling.
GPU coverage uses both existing independent JAX and Torch CUDA worker paths:
owner offers RTX 3060 first or RunPod 4090. Root verifies driver/device/actual CUDA fit and
cleanup; do not retry the six rejected R8 probes. No new GPU routing in this PR.

## Reuse and ownership

KEEP BatteryPractice, setup/profile image fields, parent equality, source digest,
worker doctor and analysis builder. REPAIR installer/release selection only.
Packets3 owns research_loop/construction_selection and their focused tests;
Platform2 confirms no current edits to these installer/release paths. Full live
open-PR file check: #1385 (243 paths), #1255, #1246, #1222; no overlap.

Maturity ceiling: implemented/tested engineering only; actual adoption, hardware
success and all qualification claims require their own observed evidence.
