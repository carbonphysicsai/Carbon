# Prospective accelerator worker environments

These are separate **unexecuted, admission-disabled** worker environments for
Python 3.11.16, Linux x86_64, and JAX 0.10.2. The `.txt` files lock all resolved
dependencies and archive hashes; `.in` files are their declared inputs. Build
installation must use `--require-hashes --only-binary=:all:` and freeze the
resulting image. No request-time resolver or package installation is permitted.
Neither an environment lock nor successful package installation authorizes a
device allocation or changes the accepted CPU reconstruction profile.

The exact [JAX 0.10.2 source](https://github.com/jax-ml/jax/blob/jax-v0.10.2/setup.py)
requires Python >=3.11, CUDA13 plugin 0.10.2 for its CUDA13 extra, or libtpu
0.0.42.* for its TPU extra. These manifests choose libtpu 0.0.42 explicitly.
Metadata and wheel hashes were checked against the public release distributions
on 2026-09-17. GPU dependencies include the plugin's CUDA runtime libraries;
the host driver and NVIDIA container integration remain separate requirements.
CUDA libraries are pinned to the documented CUDA13.0 generation, including
cuDNN 9.12.0.46, rather than letting the resolver select a newer CUDA/PTX
generation against the recorded 581.95 host driver. This resolves package
compatibility; an actual immutable image build and device execution are still
required to establish runtime compatibility.

The [JAX installation documentation](https://docs.jax.dev/en/latest/installation.html)
requires driver >=580 and SM >=7.5 for CUDA13; WSL2 GPU support is experimental.
The named laptop GPU/driver is a candidate, not an accepted isolated allocation.
The proposed v5e eight-chip shape is one host with a 2x4 physical topology. Consult
the exact [v5e configuration](https://docs.cloud.google.com/tpu/docs/v5e) and
[JAX calculation guide](https://docs.cloud.google.com/tpu/docs/run-calculation-jax)
when preparing access: small slices and throughput-oriented training slices have
different availability characteristics. No account or provisioning is assumed.

The planned precision is Float32/Complex64, x64 disabled, highest matmul
precision. Actual lowering and numerical behavior must be measured; a config
setting is not a proof of arithmetic precision. The GPU instrument disables
preallocation and uses the platform allocator for observable release; this can
be slow and is not a hard device-memory cap. See the official
[memory guidance](https://docs.jax.dev/en/latest/gpu_memory_allocation.html).
Persistent compilation caches are disabled and scratch remains role/principal
isolated; [cached executables require trusted storage](https://docs.jax.dev/en/latest/persistent_compilation_cache.html).

Print a non-executing acceptance plan from the repository root:

```sh
python -m scripts.dev.accelerator_acceptance \
  --profile carbon_jax_cuda13_nvidia_development_v1 \
  --role MINER_RESEARCH
python -m scripts.dev.accelerator_acceptance \
  --profile carbon_jax_tpu_v5e_8_development_v1 \
  --role VALIDATOR_RECONSTRUCTION
```

The numerical helper uses the existing FNO Trainer and checkpoint code. Its
CPU fixture test is implemented numerical-harness evidence only. Hardware
execution, independent recipe reconstruction, OOM and allocation-cleanup
acceptance remain open. Missing external inputs are recorded in the existing
programme resource request, not supplied through this directory.

The prospective NVIDIA controller path now extends C03 rather than creating a
second executor. CPU requests retain v1; GPU requests bind a separate v2 worker
profile and grant digest and emit v4 reconstruction artifacts. A private fixed
host grant must match the exact image, profile, principal, existing resource
policy/class, controller root, role and expiry. The same controller, launch
journal, deadline watchdog, immutable output validation and accounting apply.
No approved host grant or NVIDIA toolkit is currently recorded, so device
dispatch remains unavailable. TPU dispatch is rejected by this Docker adapter.

Build the NVIDIA image from a clean reviewed source checkout (build only; no
device allocation or host installation):

```sh
bash scripts/dev/accelerator_worker_image.sh .carbon-artifacts/accelerator-worker-image.json
```

The script invokes the ordinary C03 clean-source builder, extends its immutable
image with the hash-locked CUDA environment, and emits the ordinary image
identity manifest. The Dockerfile verifies its installed profile/lock and retains
the original source/wheel/entrypoint identities. No numerical initialization
occurs during the image build. The build checks manifest and environment-lock
readability under the actual nonroot worker identity and discards installer
caches. Building/importing the image does not establish NVIDIA runtime acceptance.

The operator-owned grant location is `/var/lib/carbon/accelerators/grant.json`;
its closed schema is implemented in `worker/accelerator_runtime.py`. It requires
a private canonical file and directory, an existing recorded approval, a
dedicated device with display disabled, and no other compute. Installing or
approving that record is outside these scripts. Never copy a fixture grant into
the host configuration.

All clients share the existing numerical-supervisor lock at that fixed root.
An exact allocation intent is written before Docker create and persists across
controller loss. The existing watchdog removes only the exact launch-labelled
container and checks device release. An active intent or uncertain release
blocks subsequent admission across restarts and new output directories. Recovery
uses the existing controller reconciliation/watchdog for its exact launch; an
operator must investigate retained allocation/quarantine records before clearing
them. No automatic reset, unrelated container removal, or grant extension occurs.
The initial release condition is deliberately strict: no compute processes and
zero reported used device memory. If the driver cannot report/reach that state,
acceptance stays blocked pending an explicitly reviewed release contract.
