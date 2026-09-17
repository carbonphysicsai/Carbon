# TPU worker preparation and missing host adapter

The versioned TPU reconstruction mapping and request are prepared for the fixed
`carbon_jax_tpu_v5e_8_development_v1` profile. The controller rejects TPU before
host admission; the service also rejects a fabricated TPU worker profile before
staging or numerical imports. The NVIDIA Docker adapter rejects this profile.
Image installation/import evidence is independent of numerical execution and
does not satisfy those gates. Existing CPU and GPU identities remain unchanged.

From a clean Linux checkout, build and inspect without any accelerator device:

```sh
bash scripts/dev/tpu_worker_image.sh .carbon-artifacts/tpu-worker-image.json
python -m scripts.dev.inspect_tpu_worker_image "$PWD"
python -m scripts.dev.accelerator_acceptance \
  --profile carbon_jax_tpu_v5e_8_development_v1 --role VALIDATOR_RECONSTRUCTION
```

The first command calls the normal C03 source/wheel/image builder, adds only the
existing hash-locked `tpu-py311.txt` environment and checks nonroot provenance.
The second runs a 30-second, 512-MiB, 64-PID, network-disabled, read-only package
instrument with no devices or host mounts. It imports Carbon's service/protocol,
reads distribution metadata, and verifies exact cleanup. It never imports JAX,
libtpu or Torch. The third prints the prepared acceptance plan; dispatch is off.
Build downloads are local packaging activity, not a cloud TPU rental.

## Concrete adapter seam and recovery plan

Future authorized implementation must extend `IsolatedReconstructionController`
at the existing profile dispatch branch and `worker/docker_runtime.py` at the
guarded device-arguments/control-verification seam. Use the same launch journal,
resource-policy/class admission, exact image, watchdog, bounded export and
post-cleanup validation. Do not add remote SSH commands or cloud credentials to
the scientific request. Allocation provisioning remains an operator action.

Before filling that seam, record these exact host facts in the existing resource
request and an operator-owned approved grant:

| Required fact | Current state / implementation consequence |
| --- | --- |
| Account, project, zone, resource identity and selected allocation SKU | REQUESTED_NOT_GRANTED; no allocation commands executed |
| VM image, kernel, libtpu-compatible host runtime and device major/minor identities | Unknown; cannot bind exact device ACLs or claim compatibility |
| Eight local/global chips, one process, observed topology | Profile expectation only; must observe on the allocated host |
| Nonroot device access, cgroup/seccomp, memory and process controls | Untested; do not substitute privileged mode |
| Network and metadata isolation with explicit local topology setup | Untested; do not substitute host networking or expose metadata credentials |
| Exclusive allocation ownership and HBM/process/release observations | Unknown; do not reuse NVIDIA UUID/nvidia-smi checks |
| Principal/role/campaign, grant expiry, productive/reconstruction/cleanup budgets | Must match existing admission/accounting; no allowance reset on reconnect |
| External allocation expiry/deletion authority, provider status and cost reconciliation | Missing; successful container cleanup alone cannot establish billing release |

After a host adapter is implemented and admitted, persist its exact allocation
identity before create; use the existing lease and launch record across retries
and output directories. Cancellation/expiry stops admission, reconciles the exact
launched container, verifies device release and then verifies provider allocation
release within the recorded authority. Controller loss must preserve an active
intent and quarantine uncertain capacity. Recovery must inspect that exact
intent; never prune unrelated resources, clear uncertain markers automatically,
reset devices or extend grants. A provider deletion command requires the approved
project/zone/resource identifiers and cleanup authority, which are currently
absent. No runnable allocation/deletion script with guessed identifiers is shipped.

## Upstream constraints

[JAX 0.10.2 source](https://github.com/jax-ml/jax/blob/jax-v0.10.2/setup.py)
requires JAXlib 0.10.2 and libtpu 0.0.42.* for its TPU extra; the lock selects
0.0.42 exactly. [JAX installation](https://docs.jax.dev/en/latest/installation.html)
supports Cloud TPU on Linux x86_64. Python 3.11.16 is separate from the controller.

[Google's v5e configuration guide](https://docs.cloud.google.com/tpu/docs/v5e)
distinguishes eight-chip single-host slices from training-optimized slices of
sixteen or more chips. The smaller proposed v5litepod-8 may run training with
lower availability; account/SKU selection remains unconfirmed. The
[JAX TPU guide](https://docs.cloud.google.com/tpu/docs/run-calculation-jax)
explains that default matrix precision uses BF16; Carbon requires explicit
`highest` precision and must measure the resulting numerical behavior. Google's
[container examples](https://docs.cloud.google.com/tpu/docs/run-in-container)
do not establish Carbon's nonroot, metadata-isolated worker containment. Checked
2026-09-17; preserve these limits when qualifying a concrete runtime.
