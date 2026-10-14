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

## Prospective amendment — stock preflight (2026-10-14)

The Test Lead redirected the fix from a blind ordered fallback to a RunPod CPU stock preflight. The owner's correction on 2026-10-14 confirms that the public Data Collection handoff and previously executed pod jobs are the source to reuse; a new raw stock response is not required for implementation or no-spend tests.

- Keep `RunPodAdapter` and the shared `carbon.agent_campaign.pod_jobs` lifecycle. A CPU compute spec may opt in to `fallback_flavors`; an omitted list preserves the existing single-flavor request contract.
- Before a CPU create, query each explicitly accepted flavor/vCPU pair through the recorded `cpuFlavors { id specifics(input:{instanceId:"..."}) { stockStatus } }` GraphQL shape. Build `instanceId` as `<flavor>-<vcpus>-<ramGB>`, using the documented memory multipliers c=2, g=4, m=8.
- Use only the historical operator interpretation: `High` means available; `null` means unavailable; the requested `instanceId`, not returned `id`, identifies the observation. GraphQL errors (including partial data with errors), missing, malformed, contradictory, or unrecognized results are UNKNOWN and refuse before the create. Keep the caller's original preference order among known-stock choices. No provider request occurs in tests.
- Do not query or interpret `securePrice` in this change: its current quote and currency/unit are not bound. The existing caller-supplied rate ceiling and deadline remain the spending bound and must be set for the slowest explicitly accepted flavor. Do not add rates, speed multipliers, caps, or scientific equivalence claims.
- After create, read the pod's reported `cpuFlavorId` before starting the job. The CPU bootstrap waits behind the authenticated `/go` start gate whether or not uploads are declared; release it only after that read matches a stock-accepted choice. Record the flavor and gate state in the private job receipt. If the flavor is missing or outside the accepted choices, leave the gate closed and use the existing owned-resource teardown/reconcile lifecycle.

This amendment supersedes the ordered-create fallback in the original scope. It does not change the owner switch, ledger, per-run cap, provider mutation allow-list beyond one read-only CPU stock operation, GPU behavior, Graphite's live path, or any actual compute authorization.
