# Carbon core platform: consolidated execution instruction

Repository: `carbonphysicsai/Carbon`.
Programme owner record: GitHub issue #209.
Starting main observed: `bf21d2e58544701d45cd5c25033097ea10bc9d7c`.
First draft branch: `agent/core-platform-01-backend-probe`.
Date: 2026-09-17.

## Mission and scope

Implement one JAX numerical platform with NVIDIA GPU and Google Cloud TPU support
for both miner research and validator reconstruction/evaluation. Expose the
existing services through interoperable MCP and the Launchpad. Investigate Julia
as an optional isolated research tool. GPU/TPU and external-agent interoperability
are required outcomes; Julia adoption depends on measured utility.

This instruction consolidates the earlier accelerator, Julia and MCP prompts.
Retrieve repository context yourself. Do not ask the owner to carry more handoffs.
Do not change scientific rules, grant new spend, or claim launch qualification.

## First draft and honest starting point

C-CORE-01 adds `carbon/reconstruction/worker/backend_probe.py` and focused tests.
It explicitly queries cpu/cuda/tpu, checks exact local-device visibility and
optional JAX/jaxlib pins, rejects mismatches and never retries another backend.
It observes an already admitted local runtime; it is not a worker admission gate,
provider adapter, resource grant, hardware attestation or performance test.
Backend initialization may acquire device resources. Invoke inside a supervised
worker under the appropriate grant and deadline, not indiscriminately inside the
trusted controller. The module does not change C-03's current CPU restrictions.

The draft has 53 passing native tests. Actual local JAX 0.9.0.1 CPU observation
passed. CUDA and TPU requests returned unavailable without CPU fallback. Native
Python was 3.13.5, not Carbon's pinned 3.11.16. Canonical formatter/quality,
package/import, regression/invariants, Hub maintenance and CI remain outstanding.
GPU/TPU execution, full numerical validation and MCP/Julia implementation are not
claimed. This draft is the first small component, not completion of the programme.

## 1. Coordinate before editing shared services

Read current main and open PRs/worktrees, AGENTS.md and its required authority
reads, current delivery/delegated-decision protocols, active tickets, source
ownership and Hub maintenance contract. Read issue #209 and current technical
lead/owner directions. Read the actual services, not only historical specs.

Preserve #207's Launchpad admission/lifecycle work and the separately owned
#206/#208 research campaigns. Verify current status rather than trusting these
snapshots. Reuse equivalent accelerator/MCP branches already in progress.

Use one integration owner for shared execution profiles, admission and evidence
projection. Parallel contributors may own numerical backends, external MCP, and
the Julia investigation only when the executor supports that workflow. Otherwise
serialize the work. Do not pretend subagents or background jobs have started.

Prefer KEEP -> WRAP -> REPAIR -> REPLACE. Reuse existing contract/reference types,
CampaignLedger, tasks, source validation and scientific orchestration. Avoid a
new platform hierarchy, second ledger or universal scheduler built before the
first real consumer. Keep research and evaluator permissions separate even where
both reuse construction code. The MCP server does not own the grading loop.

## 2. Delivery sequence and dependencies

Complete coherent slices with tests and normal delivery, rather than a giant PR.
Do not recreate completed tickets or ask for routine approval after each slice.

**A. Baseline and shared boundary.** Finish acceptance of C-CORE-01; preserve the
current research/Launchpad baseline and define only the missing dispatch/profile
mapping required by the first backend. Map existing job, principal, profile,
grant, artifact and evidence identities. Document ownership of shared files.
Prepare hardware/quota/access validation requests now, not at the end.

**B. First GPU vertical.** Extend the actual JAX training and worker implementation
with a pinned single-GPU profile. Run supported FNO/DeepONet research and fresh
independent GPU reconstruction through existing measurement/result handling.
Use an authorized existing host first; a rental provider is not a prerequisite.
Keep the CPU path unchanged as a baseline. Verify control, accounting and cleanup.

**C. First MCP vertical, alongside B.** Wrap current discovery/validation/research
services using a maintained official SDK. Deliver working stdio and SDK-client
coverage against the existing numerical backend while GPU work proceeds. Both
must call the same domain-owned services. Start a real task, reconnect and read
its outcome; do not stop at tools/list or an SDK installation.

**D. TPU vertical.** Prepare the pinned TPU runtime and provider preflight during B.
After the execution boundary works, use it for TPU miner training AND independent
validator reconstruction. Do not defer the validator half into an optional track.
Address actual operation/precision gaps, rather than copying CUDA configuration.

**E. Remote and provider completion.** Add scoped authenticated Streamable HTTP,
real target-client interoperability, owned artifact access and durable jobs. Add
Lium public-research GPU and Google Cloud TPU allocation as separate provider
adapters, with trusted grant admission, expiry and verified release. Validate
through Launchpad and operator CLI. No protected evaluation on an unsuitable host.

**F. Scale and optimize.** Add independent parallel trials/replicas, then tested
multi-device/sharded models when the supported workloads require them. Benchmark
warm/cold behavior, compilation, data transfer and useful throughput. Reconcile
numerical/reference migrations, documentation and remaining capability gaps.

**J. Julia investigation.** Conduct one bounded public-workload prototype alongside
these slices once its shared task/artifact boundary is available. It is not on
the GPU/TPU/MCP critical path. Return an adoption/limited-support/defer decision.

No paid experiment may start from this plan alone. An admission-disabled tested
engineering slice may merge before an accepted-revision real campaign when the
runtime requires that order. Keep empirical completion explicitly outstanding;
do not disable accepted-image checks or close the programme around mocks.

## 3. Shared JAX numerical implementation

Trace CPU restrictions across profile validation, image/lock identities, launch
arguments, worker protocol, device checks and effective resource controls. A
single JAX_PLATFORMS edit is insufficient. Reuse the backend probe where useful
without interpreting a matching device list as full worker eligibility.

Pin compatible Python, JAX/jaxlib, CUDA/PJRT/libtpu and numerical dependencies per
backend. Prefer shared semantics and versions. Version unavoidable differences.
Do not upgrade a live campaign or modify the accepted CPU lock in place.

Audit active Torch/NeuralOperator/PhysicsNeMo imports and dependencies. Migrate
needed numerical functionality and test core numerical execution without Torch.
Preserve history, licenses and isolated comparison fixtures. Distinguish an
external LLM/agent or a non-numerical SDK dependency from Carbon's numerical
runtime; do not rewrite third-party services to claim framework purity.

Cover training, gradients, optimizers, FFT/complex operations, physical losses,
prediction, practice, independent reconstruction, measurements and replica work.
Audit generators/references for prospective JAX migration with numerical controls.
Host serialization and orchestration remain ordinary application code. Do not
compromise a verified reference merely to replace its NumPy/SciPy implementation.

Record backend, hardware class/count, topology, runtime, precision and compiler
policy in execution evidence. The user/agent cannot select a private grading
profile. Compare control/challenger under the common registered evaluator profile.
Test repeated same-backend executions separately from cross-backend agreement.
Do not pool CPU/GPU/TPU scores before policy and evidence establish comparability.
No changed thresholds after seeing results. Preserve actual failure/disposition.

For a backend precision/operation limitation, name the exact calculation, reason,
explicit supported routing and verification task. TPU FP64 limitations cannot
become blanket indefinite CPU-only validator reconstruction. No silent downcasts.
Checkpoint portability is a tested property, not an assumption; warm-starting
from miner weights never substitutes for independent reconstruction from scratch.

## 4. Admission, resources and isolation

Reuse #207's managed grant and existing ledger/lifecycle implementation. Bind
principal, campaign, backend profile, account, device quantity, allocated time,
concurrency, idle allowance, total cost, storage/transfer and expiry. Reserve
final reconstruction and cleanup capacity before exploration. Distinguish actual,
reserved and unknown usage. Repeated calls/directories/workers do not create new
allowances. GPU/TPU rental cannot consume a CPU or unrelated inference grant.

Start with exclusive device assignment. JAX memory settings are not security
isolation or VRAM quotas. Test actual device/host-memory behavior and OOM handling.
Retain host filesystem/process/network controls. No blanket privileged container,
Docker socket, host home mount or unrestricted device access as a shortcut.

Keep wallet/signing/provisioning credentials outside miner workers. Check cloud
metadata-token access. Protect caches by principal/role; evaluator processes must
not consume miner-writable executable caches. Validate all returned artifacts.

Persist allocation and teardown intents, exact resource IDs and owner generation.
Reconcile uncertain creates before retry. Pause between operations first and show
whether compute remains billable. Stop verifies resource release, not just process
exit. Preserve reservations and RECONCILIATION_REQUIRED on uncertain outcomes.
Do not delete owner-managed infrastructure outside explicit cleanup authority.

Collect one consolidated REQUESTED_NOT_GRANTED hardware-validation package with
separate bounded line items for GPU, TPU, reasoning and final work, named account,
expiry and aggregate cap. Discover existing allowed configuration securely. Do
not ask for secrets in chat. Continue code and permitted tests when hardware or
spending is unavailable. Do not invent free credits, invoice caps or quota.

## 5. Standard MCP, not a parallel Carbon protocol

Verify latest published MCP and SDK compatibility before pinning. The official
specification checked on 2026-09-17 was 2026-07-28 with stateless requests,
server/discover and per-request capability behavior; Tasks is an opt-in extension.
Use the maintained official SDK that supports the required version. Test older
client versions explicitly rather than assuming every host supports the latest.
Never claim protocol coverage from a documentation URL alone.

Provide stdio and authenticated Streamable HTTP, typed tools and outputs,
permitted resources/artifact references, versioned research guidance, redacted
errors, limits and tested capability discovery. Generate external schemas from
current contracts where practical without allowing coercion of signed/scientific
inputs. External agents must not build internal base64 envelopes or read the repo.

Cover challenge/model/backend discovery, validation/compilation, resources,
practice launch, results, campaign controls, own history, capability requests,
candidate freeze/submission and actual independent result. Large numerical
artifacts stay behind scoped bounded access rather than flooding model context.
Unavailable priors and uncalibrated forecasts remain explicit.

Map Tasks and ordinary start/status/result tools to the same durable job record.
A MCP connection/request ID is not campaign identity or exactly-once business
execution. Client disconnect, token refresh or protocol downgrade cannot multiply
jobs/spend. Cooperative MCP cancellation still needs Carbon cleanup verification.

Remote authorization must enforce issuer/audience/expiry/scopes and ownership on
each job/resource read. OAuth identity does not replace required miner identity
or grant authority. No token passthrough to compute vendors. Public discovery,
private research and operator/validator controls need separate permission domains.
Do not expose private grading tools merely because services share code.

Use already approved campaign grants for autonomous covered operations; no
permission loops for each experiment. New spend/scope requires real authorization.
No deployment or public listener from this plan alone.

## 6. Bounded Julia research tool

Inspect the exact archived Julia sources through LEGACY_CODE_INDEX before reuse.
Do not restore its old server, trust old result labels or create another grader.
Compare a relevant SciML method/tool against current JAX and Diffrax where suitable.

Run one public smooth periodic Burgers investigation with stated domain, units,
initial/boundary conditions, time queries and grid. Compare observed error with
refinement/manufactured/analytic controls, including shared-method limitations.
A small ODE startup smoke is not evidence about Carbon's PDE workload. Measure
cold startup/precompile, warm runtime, memory, transfer and dependency burden.
One symbolic/sensitivity microtask may accompany it if it answers a concrete need.

Prototype a fixed Julia research task in a separate pinned worker with
Project.toml/Manifest.toml, private depot/cache, bounded files, startup-hook
controls, disabled runtime package installation/network, metering and cleanup.
No arbitrary Julia in the trusted controller. Add miner-script execution only
after suitable isolation testing. No hidden evaluator data or grading authority.

Julia research may inform a legal JAX-reconstructable strategy. Generated data
needs TrainingSupportContract and provenance eligibility; a Julia checkpoint does
not become a JAX submission by renaming it. Generated symbolic code is not trusted.

Reactant documents TPU compilation; that does not prove arbitrary Julia/SciML/
DiffEqGPU TPU compatibility. Investigate exact operations only if useful. Avoid
in-process cross-language AD or hot-loop RPC without a measured requirement.
A negative Julia finding is valid; adopting it in authoritative reference or
validator roles requires a separate decision beyond this investigation.

## 7. Acceptance and release gates

Use a backend x role x workload x interface matrix with exact profiles/versions:
CPU/GPU/TPU; miner/validator; supported models, precision and device count;
CLI/Launchpad/MCP. Separate implemented, canonically tested, hardware validated,
external-client validated and production-qualified states. No averaged percentage
that conceals an untested validator or TPU path.

Required end-to-end evidence: an external client or browser launches at least two
genuine adaptive experiments, retains measured feedback and failures, freezes a
legal strategy, obtains independent reconstruction on the tested backend, reads
the actual result, survives reconnect, and accounts for resources/cleanup.
Exercise the validator without the website. A failed scientific improvement is a
valid observed outcome; scripted jobs do not establish adaptive agent behavior.

Test with the official SDK client plus real target hosts. Name tested versions.
Require a second independent host before claiming broad MCP interoperability.
Test auth isolation, grant expiry/revocation, replay, device/runtime mismatch,
resource exhaustion, cancellation races, server restart, corrupt/changed/revoked
artifacts and provider ambiguity. Protect held-back comparison cases.

Benchmark synchronized cold/warm execution, compilation, transfers, training,
reference/measurement, idle allocation and teardown. Separate fixed-workload
hardware gains from adaptive research usefulness. Report cost per completed
experiment and independent reconstruction, not vendor FLOPS or transcript length.

Follow DELIVERY_PROTOCOL. Run focused tests during development and applicable
canonical acceptance before normal expected-head merge. Do not weaken CPU,
scientific, isolation, import or Hub tests and do not add a broad CI exemption.
Use explicit hardware lanes rather than silently billing default CI. Update locks,
operators, public capabilities, domain docs and Hub with implemented changes.
Stop only an affected reserved action, continue other authorized work, and keep
hardware validation selected after an admission-disabled engineering merge.

## Return one consolidated report

Report delivered PRs/code, actual user workflow, capability matrix, test evidence,
resource/cleanup state, Julia findings, blockers with owner and smallest action,
and the next dependency-ready implementation. Never claim a background agent,
paid deployment, accelerated campaign or production qualification without evidence.

Primary references checked for planning:
https://modelcontextprotocol.io/specification/latest
https://modelcontextprotocol.io/extensions/tasks/overview
https://py.sdk.modelcontextprotocol.io/
https://docs.jax.dev/en/latest/installation.html
https://docs.jax.dev/en/latest/benchmarking.html
https://docs.jax.dev/en/latest/501/compilation-cache.html
https://docs.cloud.google.com/tpu/docs/tpus-in-compute-engine
https://docs.lium.io/developers/agents
https://docs.lium.io/pod-users/security
https://docs.kidger.site/diffrax/
https://docs.sciml.ai/DiffEqGPU/stable/manual/backends/
https://enzymead.github.io/Reactant.jl/stable/
