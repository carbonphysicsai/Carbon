# Core platform accelerator access request

Programme: #209; supporting execution plan: `CARBON_CORE_PLATFORM_EXECUTION.md`.
Status: **REQUESTED_NOT_GRANTED**. Prepared 2026-09-17. This document is not an
allocation, grant, IAM change, installation or authority to spend.

## Existing self-hosted option

Read-only discovery found one NVIDIA GeForce RTX 3060 Laptop GPU (6 GiB) exposed
to the existing Ubuntu-24.04 WSL host, driver 581.95. Docker runs, but the NVIDIA
Container Toolkit/runtime is absent. No running Docker containers were observed
at discovery; that observation must be repeated immediately before maintenance.
Existing campaigns, their files and grants remain untouched. CPU Julia runs use
the existing Docker service and do not establish accelerator containment.

Requested local maintenance: install NVIDIA Container Toolkit **1.20.0-1** from
its signed upstream apt repository, add the NVIDIA runtime to Docker's existing
configuration, and restart Docker once after confirming no active workloads.
Preserve a byte-for-byte backup of any existing daemon configuration, package
inventory and ownership/mode. Do not replace unrelated runtime settings. Use
`nvidia-ctk runtime configure --runtime=docker` to prepare the additive change;
inspect its diff before restarting. Recovery restores only that exact backup
and restarts the service after confirming no new workloads. Never uninstall or
delete an existing campaign's dependencies as recovery.

The installation commands and exact packages are published in the
[NVIDIA installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
The proposed packages are `nvidia-container-toolkit`,
`nvidia-container-toolkit-base`, `libnvidia-container-tools`, and
`libnvidia-container1`, all at `1.20.0-1`. Installation is a separate host
maintenance action, not a scientific or security acceptance decision.

Initial requested GPU use: exclusive single-device DEVELOPMENT validation for
at most four hours plus one hour reserved for failed-work reconciliation and
cleanup, on the owner's existing local account. Cloud rental: USD 0. Electricity
is not metered by Carbon and is not represented as a measured zero cost. No
concurrent device partition is accepted. Device-memory/OOM, process loss,
cancellation and CPU-fallback rejection must pass before untrusted use.

## Proposed TPU allocation

- Project and account: **HUMAN_INPUT**; no configured gcloud account was found.
- Host name: `carbon-core-v5e-acceptance`; proposed zone `us-east5-a`.
- Device: eight v5e chips, `v5litepod-8`, single VM, dedicated allocation.
- Availability/quota/runtime resolution: **UNVERIFIED**. Google's current JAX
  walkthrough names this shape; small serving shapes can have different training
  availability from larger training slices. Do not silently substitute a larger
  or differently priced shape. Resolve the exact supported runtime image and
  immutable worker environment before creation.
- Work: miner forward/gradient/update/Fourier/physics/export, separately owned
  fresh validator reconstruction, fixed-state comparison, cancellation and
  allocation cleanup. Reserve the final reconstruction and cleanup before trials.
- Budget: four productive VM-hours plus one hour for compilation, failed work,
  idle time and cleanup; maximum five hours from allocation becoming billable.
- Rate checked 2026-09-17: USD 1.20/chip-hour, eight chips = USD 9.60/VM-hour;
  allocation including idle ceiling USD 48.00. READY idle time is billable.
- Storage/egress/operations allowance: USD 10.00 total; this is a requested cap,
  **not a quoted tariff**. No extra disk/bucket creation is authorized. Resolve
  applicable account/region rates and included boot storage before granting.
- Contingency: USD 12.00. **Aggregate requested cloud cap: USD 70.00** including
  all allocation, idle, storage, egress, operations and contingency. Do not rely
  on a billing alert as enforcement or reuse a provider-call grant for rental.
- Expiry: request expires 2026-09-24T00:00:00Z unless granted earlier with a new
  explicit expiry; the run lease ends five hours after allocation begins.
- Cleanup authority requested: delete only the named allocation created under
  this grant, terminate admission at lease expiry, reconcile in-flight work,
  export bounded public DEVELOPMENT results and verify provider deletion.
  Controller loss requires an independently installed expiry cleanup mechanism
  before admitting work. No cleanup authority over pre-existing machines.

Rate source: [Cloud TPU pricing](https://cloud.google.com/tpu/pricing).
Shape/runtime command source:
[JAX TPU walkthrough](https://docs.cloud.google.com/tpu/docs/run-calculation-jax).

## Prepared operator commands (not executed)

After account selection, the read-only prerequisite checks are:

```sh
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud config get-value project
gcloud compute tpus accelerator-types describe v5litepod-8 --zone=us-east5-a --project=PROJECT_ID
gcloud compute tpus tpu-vm versions list --zone=us-east5-a --project=PROJECT_ID
```

After a grant binds project, account, exact image, budget and cleanup mechanism,
the provider operations are the following templates. `PROJECT_ID` and
`REVIEWED_RUNTIME_VERSION` deliberately remain unresolved; do not run these
templates without their exact grant binding.

```sh
gcloud compute tpus tpu-vm create carbon-core-v5e-acceptance --project=PROJECT_ID --zone=us-east5-a --accelerator-type=v5litepod-8 --version=REVIEWED_RUNTIME_VERSION
gcloud compute tpus tpu-vm describe carbon-core-v5e-acceptance --project=PROJECT_ID --zone=us-east5-a
gcloud compute tpus tpu-vm delete carbon-core-v5e-acceptance --project=PROJECT_ID --zone=us-east5-a
```

The Python controller must retain credentials; the numerical worker receives
only its registered inputs and device access. Block metadata credential access
before untrusted work. Bind the returned provider resource identity, not just
its reusable name, into the existing operation record. Failed creation, failed
cleanup and uncertain billing remain explicit infrastructure/accounting states.

## Other programme lines

Local pinned Julia diagnostics and fixture MCP interoperability use existing
local CPU resources: no new cloud or model spend requested. Real agent-host
model calls require a separately identified valid existing grant or a prospective
bounded grant; none is inferred here. Workbench remains private and request-only.
AWS is deferred; Hippius is outside the critical path. Protected evaluation,
production deployment, scientific promotion and chain operations are excluded.

Next external input: name the project/account and approve or revise the local
maintenance window and capped resource request. Meanwhile CPU Julia, MCP,
Workbench, packaging and admission-disabled accelerator code can continue.
