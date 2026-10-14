# PLT-30 Torch GPU practice: host handoff

The local battery practice route now selects the existing exact-hashed Torch
CUDA worker, its registered program and profile through the same isolated miner
carrier as JAX. Each image serves its own backend. JAX's existing v1 scope is
unchanged; Torch advertises the prospective `v2-torch` scope. Remote Torch
practice remains unsupported. CPU observations never become GPU evidence.

Offline evidence covers real JAX/Torch CPU arithmetic and synthetic image,
device and dispatch controls. It does not establish CUDA execution, an image
build on carbon-fresh, GPU performance, scientific equivalence or qualification.
The existing image recipe/build script is reused; no new image was built or
installed by this lane. Actual image build and paired GPU acceptance are
**HOST_BOUND**. Host execution is owned by the machine operator.

On the authorized host, build the existing workers from the reviewed checkout:

```sh
./scripts/dev/accelerator_worker_image.sh
./scripts/dev/torch_gpu_worker_image.sh
```

Keep the separately pinned environments separate: their CUDA library closures
are not interchangeable. Record each exact image manifest, source tree,
profile/lock digests, device identity and test result. Using the operator's
existing bounded GPU test runner, execute inside the JAX image:

```sh
CARBON_REQUIRE_CUDA=1 CARBON_PARITY_FRAMEWORK=jax python -m pytest -q tests/cpu/test_gpu_backend_arithmetic_parity.py
```

Execute inside the Torch image:

```sh
CARBON_REQUIRE_CUDA=1 CARBON_PARITY_FRAMEWORK=pytorch python -m pytest -q tests/cpu/test_gpu_backend_arithmetic_parity.py
CARBON_REQUIRE_CUDA=1 python -m pytest -q tests/cpu/test_battery_torch_gpu_parity.py
```

The new arithmetic test gives both frameworks identical inputs and parameters
and checks the same float32 answer. All values, products and four-term sums are
dyadic and exactly representable, so its tolerance is zero. A changed output
must fail. This does not choose a production or trained-model tolerance;
those remain HUMAN_INPUT under OWNER-PYTORCH-BACKEND-01. The existing Torch
GPU tests additionally check all three registered families for repeatability
through both in-process and fixed-worker paths. Missing CUDA must fail in
required mode; a skipped or CPU run cannot close GPU acceptance.

Then use Launchpad's existing this-machine-GPU setup with the Torch manifest
and the battery Challenge. Confirm its scope says `pytorch`, run an authorized
public practice recipe, and retain the actual worker/device observations.
Confirm a JAX recipe on that image refuses before dispatch and the existing
JAX image still serves its own scope. This handoff grants no spending, provider
access, deployment, production security acceptance or scientific authority.
