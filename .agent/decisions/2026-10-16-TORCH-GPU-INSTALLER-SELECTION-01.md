# TORCH-GPU-INSTALLER-SELECTION-01 — working decision

Ticket: `.agent/tickets/TORCH-GPU-INSTALLER-SELECTION-01.md`.
Status: IMPLEMENTED_WORKING_DECISION in the branch's installer selection and focused fixture tests; canonical validation and review remain pending.
Primary map_ref: `SYSTEM/LAUNCHPAD`.

Problem: `install_miner.sh --pytorch --gpu` selects a Torch CPU/analysis pair yet installs JAX's accelerator GPU worker. The existing Battery local GPU campaign and setup code accept the separately published Torch GPU image; a miner-facing installer selection should bind to that image without weakening its checks.

Recommendation: explicitly select the `torch-gpu` release kind and `torch_gpu_worker_image.sh` only for the combined flags. Preserve `--gpu` default JAX, the CPU Torch pair, early release-record checks, pinned pull and manifest recording. Keep remote Torch scope unchanged; `installed.released_gpu` may continue to withhold a remote released reference for Torch.

Alternatives rejected: leave misleading combined flags and require manual manifest selection for every Torch miner (available for current v5 testing, but usability defect persists); make `--pytorch` implicitly select GPU without `--gpu` (unexpected build/pull); accept arbitrary GPU backend declarations or relabel a JAX image (violates exact identity); widen remote Torch practice (separate authority).

Interfaces/dependencies: installer flags, its release-record list and output manifest path, CPU fixture tests, PyTorch practice adoption guide. Existing image schemas, release bytes, local setup checks and historical evidence remain unchanged. Reversible by reverting this branch's installer selection and guide; no migration of stored evidence.

Implementation location: `scripts/install_miner.sh`, `tests/cpu/test_graphite_pytorch_practice_adoption.py`, `docs/development/images/PYTORCH_PRACTICE_ADOPTION.md` on `codex/torch-gpu-installer-01` from c8979fe6. A lead change supersedes this record plus the ticket contract and those exact files.

Human-reserved input: none for this engineering selection. Security acceptance, scientific tolerance, production deployment and qualification remain reserved and untouched. Notify Root as coordinating lead; continue implementation unless a blocking direction arrives.
