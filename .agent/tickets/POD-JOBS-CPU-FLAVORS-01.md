# POD-JOBS-CPU-FLAVORS-01 — the shared pod launcher may offer more than one CPU flavor

**Status:** open. **Owner:** Data Collection. **Reviewer:** Graphite Testing Manager (spend-bearing: PR Head security-sensitive flag).
**Authority:** Test Lead, 2026-10-13 (D3); OWNER-POD-LAUNCH-DELEGATION-01; CLOUD-FIRST-COMPUTE-01.

## Why

On 2026-10-13 every 8-vCPU `cpu5m` pod job created (4/4), while every 16- and 32-vCPU `cpu5m` create failed as ambiguous (0/3 jobs, both attempts each), and the D3 re-reference stopped for capacity. The public-dev launcher's 32-vCPU pod on 2026-10-12 asked RunPod for `cpuFlavorIds: [cpu5m, cpu3m]` with `cpuFlavorPriority: custom` and was placed. The shared launcher (`carbon/agent_campaign/pod_jobs.py` over `operator_compute`) sends exactly one flavor, because `CPUPlacement` holds one `flavor_id`.

## Scope

- A pod job spec may name an ordered list of CPU flavors (same memory class); the create body sends them in that order with `cpuFlavorPriority: custom`.
- The receipt records the flavor the provider actually placed, read back from the pod, so a result can be tied to its CPU generation.
- `operator_compute` changes only additively: a single-flavor request behaves exactly as today (Graphite's live path is unchanged).
- Tests with the in-memory provider only; no real RunPod call in CI.

## Not in scope

Choosing which flavors are numerically interchangeable for a given study: that is a per-study control (see the D3 cpu3m overlap control, 2026-10-13). Mixed-flavor runs of one study need that control first.
