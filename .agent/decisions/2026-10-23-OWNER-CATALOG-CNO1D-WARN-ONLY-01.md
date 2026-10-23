# OWNER-CATALOG-CNO1D-WARN-ONLY-01: CNO1d's GPU twin may relax determinism to warn-only, for practice only

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Graphite Test session (session `local_56982aa9-c1b6-4050-b9e0-9f77f006ca06`, "Graphite Test: UI, wallet"). Recorded by Graphite Test at the Validator's request (the owner told that session directly).

## The question and the answer

- **Question put to the owner (option 2):** CNO1d's own code calls `torch.use_deterministic_algorithms(True)` and its upsample backward has no deterministic CUDA kernel, so its GPU build raises while training. Allow a GPU twin of `cno.CNO1d` only, with that call relaxed to `warn_only=True`, for GPU practice only, with the official route refusing it?
- **Owner's answer:** "2" (choosing option 2 over CPU-only), and later, when asked to confirm it directly to the Validator: "yes".

## Decided

- `cno.CNO1d` gets a `torch-cu130-py311` GPU twin whose `common.py` relaxes the determinism call to `warn_only=True`. This is the second registered change of `gpu_build` and applies to an explicit one-entry list (`WARN_ONLY_DETERMINISM`), never a general rule.
- The twin is **practice only**: its receipt is `smoke only: not bit-reproducible on GPU`, and the official route refuses it (`catalog_runtime_not_reproducible`).
- Practice serves it once its smoke receipt is valid (the practice-receipt rule, Validator 2026-10-22).

## Not decided

- Nothing about CNO1d's score quality: on CPU and GPU alike only 2 of 5 seeds pass the `motoring_mean_nonnegative` gate (measured 2026-10-22); the page marks gate failures honestly.
- `thuml.LSM` has no GPU twin (Validator ruling): not changed by this record.
