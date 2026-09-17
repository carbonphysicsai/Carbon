# C-CORE-03: prospective GPU and TPU reconstruction profiles

Programme: #209; owner authority: integrated v3 execution mandate in
`.agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md`. Status: implementation in
progress, dispatch disabled, hardware acceptance open. Dependencies: C-CORE-01
backend observation and C-CORE-02 CPU scientific service. Separate delivery from
C-CORE-02; preserve its candidate and all unrelated work/campaign grants.

Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Affected owners: WAVE-C/C-02 and C-03. Root integration owner batches Hub changes
before this ticket's acceptance. This ticket grants no spending or infrastructure
installation; `.agent/plans/CORE_PLATFORM_RESOURCE_REQUEST.md` tracks missing
runtime/account authority as REQUESTED_NOT_GRANTED.

## Working contract and C-CORE-03-D1

KEEP the existing construction plan, execution-attempt identity, resource
admission, controller, watchdog, validation and ledger. WRAP fixed numerical
operations and extend existing profile compilation prospectively. No scheduler,
evaluator, ledger, research loop or automatic cloud allocation is introduced.

The named GPU target is the self-hosted NVIDIA GeForce RTX 3060 Laptop GPU,
UUID GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81, recorded host driver 581.95,
6 GiB onboard memory. NVIDIA container support and exclusive allocation evidence
are absent. The proposed TPU is Google v5e, eight chips, one host, 2x4 topology;
account/access and the selected provisioning SKU remain unverified. Configuration
does not establish hardware, isolation, numerical or reconstruction acceptance.

Pin separate Linux x86_64 Python 3.11.16/JAX 0.10.2 worker environments using
resolved hash-locked dependencies. NVIDIA uses CUDA 13 plugin/PJRT 0.10.2; TPU
uses libtpu 0.0.42, consistent with exact JAX release metadata. Neither changes the
control-plane dependency environment. No runtime package installation. Retain
CPU default profile/artifact interpretation and version accelerator identities.

Profiles bind language/backend, exact device expectation, local/global counts,
process count, precision and prospective allocation/cache rules. Reject silent
CPU fallback, topology mismatch and implicit BF16/TF32 precision. Disable shared
persistent compiled caches; a validator cannot consume miner-writable executable
state. A host-memory cap or allocator setting is not a device-memory cap.

The acceptance instrument reuses actual FNO training, gradients, optimizer,
Fourier derivatives, physical loss, prediction and logical checkpoints. CPU-only
fixtures demonstrate harness implementation, not accelerator work. Checkpoint
reload is not fresh reconstruction: miner and validator attempts must train the
submitted recipe independently using their separately bound inputs and existing
controller dispatch. No scientific threshold or qualification is selected here.

Prospective profile/service/worker migration is owner-authorized. It must bind
the new environment at the construction/attempt contract rather than quietly
executing a CPU-pinned plan on an accelerator. Admission remains disabled until
the existing controller can enforce the named allocation/containment contract;
device access and actual runtime acceptance stay open until observed.

Owned implementation: `carbon/reconstruction/accelerators.py`,
`scripts/dev/accelerator_acceptance.py`, `.devcontainer/accelerators/`, and
`tests/cpu/test_accelerator_profiles.py`. Following this contract, prospective
migration may extend `carbon/reconstruction/profile.py`, `service.py`, `model.py`
and `worker/protocol.py`, preserving old defaults and schema interpretation.
The next integrated slice also owns `worker/model.py`, `worker/controller.py`,
`worker/docker_runtime.py`, new `worker/accelerator_runtime.py`,
`tests/cpu/test_accelerator_worker.py` and `scripts/dev/accelerator_worker_image.sh`.
Root remains shared integration owner. Do not modify the active reference
controller, campaign state or C-CORE-02 consumer files in this ticket.

Alternatives rejected: overriding CPU environment checks, caller-set admission
Booleans, arbitrary scripts as trusted reconstruction, claiming matrix multiply
or checkpoint reload as independent reconstruction, shared writable caches and
runtime dependency installation. Reversal removes prospective registrations;
historical attempt/artifact identities remain valid.

## C-CORE-03-D2: host ownership and prospective dispatch

The existing C03 controller reads a canonical private operator record at the
fixed `/var/lib/carbon/accelerators/grant.json`, never a request-selected path.
Its exact image/profile, principal, controller root, resource policy/class,
role, expiry and dedicated no-display/no-other-compute allocation must match.
The implementation does not create APPROVED grants; the programme request is
still REQUESTED_NOT_GRANTED. A granted attempt must fit its full existing
600-second productive deadline before dispatch. Revocation/expiry is checked
during supervised waits and before result association.

Reuse the existing numerical-supervisor flock at that one private host root.
Persist an exact container/launch allocation intent before Docker create;
reconnect, new output directories and controller death do not create another
slot. The existing watchdog and normal exact-container cleanup both verify
release and clear only that exact intent. Missing release telemetry or residual
GPU use remains unreconciled, with a shared quarantine marker. This prospective
strict release check requires no compute process and zero reported device memory
use; its behavior on the named device remains untested and is not a qualified
memory partition. It performs no device reset or unrelated process termination.

CPU worker requests/profile identities stay v1. GPU requests use the separate
v2 schema and bind a fixed typed role/profile/grant digest. Actual existing FNO
training executes inside the same admitted image, with strict CUDA backend,
device/topology/plugin and Float32/Complex64 precision expectations; accelerator
artifacts use v4 and ACCELERATOR_DEVELOPMENT_DIAGNOSTIC eligibility. Native output
validation remains CPU and never consumes worker compiled caches. GPU execution
requires the exact newly built hash-locked image and NVIDIA daemon runtime.
The image builder extends the normal clean-source C03 build and preserves wheel,
entrypoint and source identities while updating parent/environment/recipe pins.
Provenance and environment-lock files must remain readable by the numeric
nonroot worker; the Docker build checks that identity directly. Installer caches
are transient and permission freezing stays in the dependency-install layer,
avoiding a duplicate CUDA library layer.
TPU's profile/lock is prepared; this Docker device adapter rejects TPU dispatch.

## Acceptance and limitations

### Prepared accelerator candidate

The prospective controller/profile implementation is implemented and locally
tested. The exact isolated Python3.10-target Ruff and Black checks passed for
all changed Python modules. Focused grant, lease, protocol and CPU regression
checks passed; canonical delivery acceptance remains required. The ordinary CPU
profile/schema interpretation is unchanged.

The corrected CUDA image was built from source commit
`12025a9b7736d18c6a9726552e9d7a12ce3b9224` with source archive digest
`sha256:2ccdd991c17063547885090cbc6fecffcac0070e65d3b4810faa093fdd7ce874`.
Its immutable image identity is
`sha256:014693768c5bb5da745efffb206b9f63aacfc85adad0c574827893fb3c51b48d`.
Nonroot, read-only, network-disabled package verification checked all 34 pinned
distributions, exact lock/profile identities, installed service/protocol imports,
readable provenance and absent installer cache without importing JAX or Torch.
This evidence does not establish GPU execution. Image size was 6,036,044,575
bytes after repairing root-only provenance permissions and removing the
installer cache and duplicate library layer from the initial 12,468,651,488-byte
build. The initial failed-validation image remains historical evidence.

The later CPU foundation merge changed no accelerator execution or image-build
input. This image retains its original source identity; no newer source/image
identity is implied by navigation or programme reconciliation. The base container
doctor passed; the separate accelerator gate rejected unavailable NVIDIA runtime.
The named diagnostic container was removed and absence verified. No GPU/TPU
allocation, host maintenance, campaign execution or cloud spend occurred.

Require focused profile/protocol rejection tests, actual CPU harness diagnostics,
CPU profile regression/golden identities, and applicable canonical full CPU,
invariant, quality, package, worker-service and Hub checks under current delivery
classification. Do not weaken classification to avoid dependency/worker checks.

Actual GPU and TPU miner research plus fresh validator reconstruction, device
memory/OOM, cancellation/crash/lease/restart cleanup, cross-backend comparison and
eligible sharding remain unearned until run. No shared comparison class or score
pooling is authorized by this implementation. Completion is conditional on
applicable checks and normal expected-head merge under OWNER-DX-03; partial
implementation may merge with admission disabled and runtime acceptance open.

### CPU probe regression repair

The accelerator profile selection exposed an obsolete backend-probe test stub:
returning five `None` values from request decoding left no staged request for the
new typed worker-profile read. The test therefore stopped before its intended
probe, and the neighbouring rejection tests could pass without probing at all.
Reuse the existing C03 bounded fixture to stage and decode a real CPU request,
assert that reconstruction receives its exact CPU profile, and require each
backend-rejection case to observe one explicit CPU probe before stopping.
The decode/probe/reconstruction ordering and no-publication assertions remain.
This repair changes tests only; CPU runtime selection, accelerator admission and
the recorded image/hardware acceptance limits remain unchanged.
