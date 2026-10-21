# OWNER-A40-POD-ENV-PROVIDER-BOUND-01: the A40 pod check tests only the provider bound

Date: 2026-10-21
Status: APPROVED by the owner. In the Test Lead's session the owner said, of the A40 file-count guard: "more unnecessary limits we are setting." The Validator ruled on it under that direction and OWNER-MINER-LIMITS-EXAM-ONLY-01.
Scope: `tests/cpu/test_a40_acceptance.py::test_the_real_pod_environment_fits_well_under_the_provider_limit`, implemented in `fe391470422abe6cbff39c2b44cc421b82bf5618` and landing via A2 `b75a697ab`.
Maturity: engineering control. No scientific or security acceptance is created.

## 1. What changed

- **Removed:** `assert len(manifest) < 600`. It was a file count with no provider basis.
- **Removed:** `assert check_env_size(env) < 60_000`. It was a self-chosen margin.
- **Kept, now the only check:** `check_env_size(env) <= ENV_LIMIT_CHARS`, the code's own runtime refusal.

## 2. The bound and its basis (an external fact, cited)

- **`scripts/dev/exam_design/runpod/pod_env.py` `ENV_LIMIT_CHARS` = 108,000 characters** (names plus values of the pod-create environment).
  - Set by OWNER-POD-ENV-LIMIT-RAISE-01, and unchanged here.
- **The provider basis:** RunPod's pod-create request was **observed** to fail as an opaque HTTP 500 at about **118,000 characters** (2026-10-13). RunPod doesn't document this; it's an observed fact.
  - The 108,000 bound keeps about 10,000 under that point.
- **The landing head:** 606 files, `env_chars` 34,751 (measured by Launchpad).

## 3. Rule

- **No file-count or self-chosen margin** may be added back to this test.
- **If the provider's real limit changes,** a new observation or documentation is cited and `ENV_LIMIT_CHARS` moves with a record.
