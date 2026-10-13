# LP-05: explicit NVIDIA device-request driver

Authority: the owner-selected Platform2 queue item
`GPU-PRACTICE-DEVICE-REQUEST-DRIVER-01`, diagnosed by Launchpad on 2026-10-13.
Starting main: `bd01fb9237a5886594f8845ef834873187abc719`.
Reviewer: Launchpad. Primary historical map_ref: `SYSTEM/AGENT-EXECUTION`;
Hub maintenance is retired by OWNER-WORKFLOW-SPEED-01.

Repair the worker, miner research container and remote practice creation paths
to request `--gpus driver=nvidia,device=<uuid>`. Keep the worker's exact
DeviceRequests inspection and add the same driver requirement to miner
inspection. CPU requests continue to contain no accelerator request.

Reuse existing argument, Docker-inspect and remote-script fixtures. Test both
inspection boundaries with an empty driver (POLICY refusal) and the NVIDIA
driver (accepted with the other controls satisfied). Cover wrong/missing drivers
and verify the emitted GPU option names the driver and the chosen device.

Baseline: 16 affected contract/inspection/script cases passed diagnostically.
A broader diagnostic run passed 45 cases before an existing MCP-door test failed
because the local environment lacks pinned `mcp` metadata. The canonical wrapper
refuses this Windows-managed worktree; canonical CI remains the acceptance source.
Run GPU/accelerator regressions, invariants, pinned Black/Ruff, diff/encoding
checks and pre-push delivery hygiene. No hostile probe sources are executed.

Completion is conditional on passing required CI at the handed-off PR head.
This repairs a DEVELOPMENT launch contract; it qualifies no device or backend.
Launchpad owns the real JAX GPU-practice acceptance after merge and lane move.
No remote host operation, Docker launch, paid compute, deployment, merge,
approval, protected material, tolerance or LIVE change is authorized here.
