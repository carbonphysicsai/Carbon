CARBON CORE PLATFORM V2
JAX + GPU + TPU + NATIVE JULIA + MCP + WORKBENCH

Repository: carbonphysicsai/Carbon
Programme: issue #209
MCP workstream: issue #210
Starting draft: PR #211, agent/core-platform-01-backend-probe
Repository plan: .agent/plans/CARBON_CORE_PLATFORM_EXECUTION.md

OWNER DIRECTION AND SUPERSESSION

Execute the integrated programme now. Julia is a required Carbon-native
capability for miner research, validator physics/reference checks, and
Workbench challenge design. This supersedes earlier instructions that made
Julia optional, research-only, or a prototype that could be deferred wholesale.
Individual packages and methods still require evidence of suitability.

JAX remains the model construction, training, prediction and independent
reconstruction framework, with GPU AND TPU support for miners AND validators.
Julia provides native scientific analysis, numerical-reference and design
services through a Python-facing bridge. Python remains the control plane.
No PyTorch replacement or Julia ML migration is requested.

The user has selected the architecture and implementation scope. Do not ask
again whether to integrate Julia into validator or Workbench code. This does
not itself qualify a reference method, change a score, authorize protected
processing, approve cloud spending, or deploy a public service.

Read this prompt and retrieve supporting repository context yourself. Do not
ask the owner to move more documents or combine previous prompts.

1. ORIENT, REUSE AND COORDINATE

Inspect current main, PR #211, issues #209/#210, open branches/worktrees and
current owner/technical-lead directions. Follow AGENTS.md, CONSTITUTION.md,
INVARIANTS, DELIVERY_PROTOCOL, DELEGATED_DECISION_PROTOCOL, CODE_AUTHORITY and
applicable domain/Hub maintenance contracts.

PR #207 merged as 0afbb9d98338353732ba2fce6716dbefd0af9bbc. Verify current
state and reuse its admission, accounting, task ownership, controls and
reconciliation. Preserve separately owned #206/#208 campaigns and grants.

PR #211 originally added a backend-observation helper and 53 passing native
diagnostic tests. That does not establish GPU/TPU execution. Its documented
canonical and hardware acceptance gaps remain until evidence resolves them.
The v2 planning amendment adds scope, not runtime or new test evidence.

Inspect actual implementations in carbon/reconstruction, development_session,
research, practice, reference_runtime, measurement_runtime, resource_policy,
registry, orchestration, and scripts/dev/miner_launchpad.

For Julia read Design_Specs/Runtime_Julia_Truth_Oracle.md and the current
B-04/reference, TruthAsset, measurement and reference-failure contracts.
The historical filename is not a universal truth claim. Resolve stale status
text against current implementation and authority rather than reviving old gates.
Inspect exact archived Julia sources through docs/history/LEGACY_CODE_INDEX.md
for deliberate reuse; do not restore its incomplete server wholesale.

For Workbench read Business/Business_Canon.md and current Workbench challenge-
design, case compiler, evidence-plan, rights and handoff contracts. Inspect the
actual implementation under Business/Carbon_Fit/workbench and any current
successor modules. Do not create a second Workbench or confuse the public
homepage chatbot with an authorized challenge-design workspace.

Use one integration owner for shared execution, grant and evidence interfaces.
Parallel contributors may own JAX backends, Julia science services, and MCP/
Workbench adapters on distinct files when the environment supports that.
Otherwise serialize. Do not claim subagents or background jobs that did not run.

KEEP -> WRAP -> REPAIR -> REPLACE. Extend existing domain services. Do not build
another research loop, job ledger, evaluator or universal scheduler.

2. CORE SERVICE DESIGN

Provide a native Python API over versioned scientific tasks, with shared job
admission, artifact transport, cancellation, provenance and domain projections.
Launchpad, operator CLI, Workbench and MCP consume the same services.

Keep framework/language, hardware backend, compute provider, caller identity,
scientific role and evidence use separate. A registered Julia task is not an
alias for a JAX model backend or permission to choose a private grader.

Create a capability registry from actual implementations: supported tasks,
models, languages/backends, input/output contracts, applicability, precision,
resource requirements, scientific-use eligibility and current availability.
Use current domain types where possible. Avoid inventing duplicate authority.

The planner may select a suitable registered Julia method for an eligible task
within existing rights, grants and policy. Record the reason and exact method.
Do not require an extra manual toggle for each covered task. Do not run Julia
on every request merely to demonstrate use or silently replace a frozen method.

3. PYTHON-TO-JULIA BRIDGE

Implement function invocation and typed data conversion, not a general
Julia-to-Python source translator. Preserve reviewed Julia source and method
identity; do not rewrite scripts with an LLM before validator execution.

Use a supervised process/service boundary for Julia scientific execution.
Evaluate JuliaCall/PythonCall for invocation and conversion INSIDE a dedicated
worker. A Julia subprocess using a closed task protocol is also acceptable.
Choose one working transport first; keep the external Python API stable.
Do not embed an unrestricted Julia interpreter in the trusted controller.

Pin Julia, Python bridge versions, Project.toml, Manifest.toml, package artifacts,
source and worker image. Prebuild dependencies. JuliaCall defaults can install
Julia/packages: disable that runtime behavior with tested pinned configuration.
Disable user startup hooks and uncontrolled LOAD_PATH/depot resolution.

For trusted validator requests, resolve a registry task/method ID to a fixed
script and configuration. No caller-supplied executable path, URL, expression,
package name, shell argument or tolerance override. Different rule-bound
configuration requires its own permitted immutable identity.

Define and test cross-language conversion of units, coordinate frames, axes,
array order, shapes, dtypes, complex values, time coordinates, indexing and
scalar conventions. Reject ambiguity, missing required metadata, silent unit
conversion and unsupported precision. Synchronize JAX device work before host
transfer. Do not claim zero-copy GPU/TPU sharing or cross-language gradients.

Return bounded typed results plus authorized large-artifact references. Retain
runtime/method/input identities, solver status, diagnostics, observed numerical
error/convergence, applicability, resource use and limitations. A process exit
or solver-success return code does not establish physical correctness.

4. NATIVE JULIA SCIENCE TASKS

Implement real, reusable tasks for the first supported physics family:
- equation/units and structural-consistency checks;
- boundary/initial-condition compatibility checks within defined scope;
- public numerical solves and parameter sweeps;
- conservation, residual and stability diagnostics;
- convergence/refinement and method-comparison checks;
- sensitivity/identifiability analysis where supported;
- reference realization and evidence production under ReferencePolicy.

Select maintained SciML/Symbolics/ModelingToolkit/solver packages per task.
Pin compatible versions; do not install the entire ecosystem by default.
Use Julia where its methods fit. Preserve JAX for model training/reconstruction.

Start with one complete supported Burgers workflow rather than advertising
arbitrary physics. A second small supported template may test reusable design,
but must not replace the Carbon-relevant PDE acceptance.

For nonlinear PDEs, structural/unit checks do not prove well-posedness.
Keep numerical solver tolerances separate from engineering acceptance thresholds.
Keep inferred assumptions, measured diagnostics and qualified claims distinct.

5. VALIDATOR JULIA INTEGRATION

Connect actual validator-side code to Julia through the native Python API.
Support registered primary, corroborating/witness and diagnostic reference
roles where the current ReferencePolicy permits them. Julia validator support
is a required implementation deliverable, not another investigation-only item.

The evaluator selects the pinned method before candidate outcomes. Execute
with evaluator-owned canonical cases, role permissions and resource policy.
Miners cannot upload the validator script, select hidden cases, alter solver
settings or fetch protected outputs.

Reuse current reference request/run/result/TruthAsset and measurement owners.
Do not create a second score, Boolean truth authority or synthetic receipt.
Map disagreement, non-convergence, unsupported scope, bad provenance,
infrastructure failure and candidate physics failure to distinct existing
outcomes. Reference failure must not become candidate failure.

Verify algorithms with analytic/manufactured cases, refinement, error and
sensitivity studies, and methodologically distinct checks where feasible.
State correlated failure modes. Two languages agreeing is not independent truth.
A convergence indicator or configured solver tolerance is not a certified error
bound or population confidence interval.

Implement prospective DEVELOPMENT integration and a complete qualification
harness/dossier. Use the actual qualified route for score-affecting evidence
only when its challenge-specific prerequisites exist. If a scientific value
is missing, block that promotion while continuing runtime integration and
permitted verification. Do not request architecture approval again.

An existing accepted reference remains authoritative until the prospective
replacement/augmentation completes its required validation. Never rewrite
historical results or change a method/threshold after viewing the candidate.

Separate validator workers, caches, files and credentials from research and
Workbench even when all use the same service implementation. Protected data
must never reach ordinary research rental hosts, public MCP, Workbench design
views or provider-model prompts.

6. NATIVE WORKBENCH CHALLENGE DESIGN

Integrate Julia into the existing Workbench workflow, not an external notebook
that the user must operate separately.

For a supported structured challenge draft, the Workbench should:
- check required physical definitions and units;
- identify contradictory or missing initial/boundary conditions;
- run admitted draft-domain solves, parameter and sensitivity probes;
- inspect conservation/residual behavior and numerical conditioning;
- test reference options, convergence and approximate compute requirements;
- assemble measured design evidence, uncertainties, assumptions and gaps;
- persist those artifacts in the existing design/evidence-plan/handoff model.

Bind every task and result to the exact draft revision, physical definition,
method configuration and environment. If the user edits equations, domain,
units, conditions or relevant parameters, mark prior results stale or require
explicit valid reuse. Never attach a late result to a newer draft by accident.

Provide run/status/cancel/results controls, scoped artifact access, useful
plots of actual outputs, cost visibility and restart-safe saved workspaces.
Empty, failed and unsupported states must work on desktop and mobile.
Do not execute Julia in the browser or expose arbitrary server-side scripts.

Keep customer/team workspaces, data rights and public research separate.
Customer-derived design data cannot become public training/evaluation material
without explicit permitted lineage and release. Treat model-generated equations,
symbolic expressions and uploaded files as untrusted inputs.

Preserve UNASSESSED/NOT_QUALIFIED and request-only handoff semantics where
current Workbench contracts require them. A successful design check does not
activate a challenge, establish customer feasibility, qualify an exam or approve
production thresholds. Clearly show confirmed definitions, test observations,
proposed settings and unresolved human/scientific decisions.

7. MINER JULIA AND CONTROLLED SCRIPT EVOLUTION

Expose registered Julia tasks through the existing research workspace and MCP.
Retain hypotheses, artifacts, costs and capability requests in current records.

Support miner-authored or agent-authored Julia scripts in an appropriately
isolated research scope after containment tests. Such scripts cannot alter the
registered validator catalogue or inherit Workbench/customer data access.

Use a distinct development path to propose, inspect, test and version reusable
scripts before registration. No request-time package installation, direct eval
of symbolic output, or automatic promotion of generated code to trusted methods.

Julia research may inform a JAX-reconstructable strategy. Generated training
data must meet TrainingSupportContract and provenance rules. Julia checkpoints
cannot substitute for a registered JAX reconstruction.

8. RETAIN COMPLETE JAX GPU/TPU DELIVERY

Extend the existing JAX models and execution profiles; do not restore archived
PyTorch code. Audit and migrate active numerical Torch dependencies with tests.
Preserve archives, licenses and legitimate isolated comparison fixtures.
External LLM/agent internals and non-numerical SDKs are outside this migration.

Trace all CPU-only restrictions through profiles, locks, entrypoints, worker
protocol and effective-control checks. Pin compatible GPU and TPU environments;
record exact device visibility, runtime, precision and topology. Reject silent
CPU fallback. Test the actual FNO/DeepONet forward, gradients, optimizers,
Fourier operations, physical losses, prediction, export and reconstruction.

Deliver single-device GPU AND TPU miner research and independent validator
reconstruction. Then complete permitted parallel experiments/replicas and
supported sharded workloads. Neither role nor TPU can disappear from the scope.

Keep same-backend repeatability, cross-backend agreement and score comparability
as separate properties. Use a common declared comparison profile or a valid
heterogeneous-backend policy; do not invent comparability or bitwise equality.

Audit reference/measurement operations by numerical requirements. Preserve
specific justified CPU/GPU routes where TPU precision/operation limits apply.
No silent downcast. Julia GPU/TPU compatibility is package-specific: Reactant,
CUDA.jl and DiffEqGPU are not interchangeable and do not automatically make
all Julia scripts accelerator portable. Record actual supported paths.

9. STANDARD MCP AND PRODUCT ACCESS

Use a maintained official SDK after verifying current published specification
and SDK/client compatibility. Do not trust a prior prompt's claimed latest
version without checking. Provide stdio and authenticated Streamable HTTP.

Wrap the same core services with typed tools/results, capabilities, versioned
guidance and permitted resource/artifact access. External clients need no
repository access or knowledge of internal base64/JSON-string envelopes.
Keep Carbon's exact scientific validation authoritative across SDK mappings.

Expose miner and Workbench Julia capabilities with their own authorization.
Keep protected validator operations internal or on a separate operator-only
surface. Hiding a tool from a list is not access control. Never publish hidden
reference results through generic resource, export, log or error endpoints.

Map supported MCP durable-task semantics and ordinary start/status/result tools
to the same job ledger. Request/session identifiers are not business-operation
identity. Retries and disconnects cannot duplicate work, grants or submission.

Enforce issuer/audience/expiry/scopes and ownership on every task/artifact read.
No token passthrough to compute providers or caller-selected principal. Bind
MCP identity to existing Carbon identity and grants. Test actual supported
clients, version negotiation, errors, cancellation and task recovery.

10. RESOURCES, SECURITY AND EXECUTION AUTHORITY

Reuse managed grants, accounting, ownership, durable intents and fencing.
Bind the caller, role, workspace/campaign/draft, task/method, backend, account,
resource limits, concurrency, expiry and cleanup authority. Account for CPU,
GPU/TPU allocation, Julia compilation, warm idle, transfer, storage and final
work. Reserve final reconstruction/reference and cleanup before exploration.

Do not multiply allowances with retries, new roots, parallel workers or a new
language. Preserve uncertain consumption and RECONCILIATION_REQUIRED.

Use admitted deadline-supervised workers. Pin dependencies and inspect effective
filesystem/process/network/device controls. Keep cloud credentials, hotkeys,
controller journals and Docker sockets outside untrusted workers; audit metadata
credentials. Memory tuning and privileged containers are not security isolation.

Keep warm pools and compiled caches separate by role/principal and pinned runtime;
reset mutable state, limit idle duration and verify lifecycle. Evaluators must
not consume miner-writable caches. Cancel must stop new dispatch, reconcile exact
owned work, release managed allocations and verify cleanup. Never delete an
owner-managed machine outside its explicit authority.

Discover existing authorized configuration without requesting secrets in chat.
Prepare one consolidated REQUESTED_NOT_GRANTED validation request when needed,
with bounded GPU, TPU, Julia/reference, Workbench and reasoning line items,
accounts, expiry and aggregate cap. Existing grants apply only to their scope.
No new paid calls, cloud/IAM changes, public deployment, registration or protected
processing follow from this prompt alone. Continue permitted work when a paid
or scientifically reserved operation is blocked.

11. DELIVERY SEQUENCE

First reconcile current draft acceptance and record the v2 scope in the actual
programme/ticket/Hub sources. Avoid repeated documentation-only delivery.

In parallel where supported, implement:
A. A JAX GPU research-to-independent-reconstruction workflow, preparing TPU early.
B. The native Python-Julia worker and one real registered physics task, consumed
   by validator diagnostics AND Workbench challenge design, plus miner access.
C. Standard MCP over existing services, exercising real jobs on the available
   baseline instead of waiting for every accelerator/provider.

Then complete TPU research and validator reconstruction, native Julia reference
and Workbench evidence flows, remote authorization/provider provisioning, and
parallel/multi-device operation. Integrate one consumer at a time through shared
interfaces; do not create one enormous overlapping pull request.

Benchmark methods to choose good defaults, not to reconsider the owner's
requirement that Julia be native. An unsuitable package or check may be replaced;
Julia as a whole is no longer a defer/adopt investigation.

Do not block GPU work on Julia completion or vice versa. Do not call the whole
programme done while either mandatory track remains unimplemented.

12. ACCEPTANCE AND REPORTING

Maintain an explicit role x task x language/backend x interface matrix with
versions and evidence. Separate implemented, canonical tests, real-runtime/
hardware validation, external-client validation and scientific qualification.

Required evidence includes:
- Python invoking a real pinned Julia script and receiving validated results;
- conversion tests, including axes/units/dtypes and malformed/nonfinite data;
- validator Julia checks with correct policy binding, analytic/manufactured
  controls, convergence, deliberate bad candidates and reference failures;
- a real Workbench draft through Julia design checks, saved evidence/reopen,
  cancellation, stale-result rejection after edits and request-only handoff;
- miner Julia tasks and a legal JAX strategy, without authority/data leakage;
- GPU and TPU adaptive research, frozen strategy, fresh independent reconstruction,
  truthful DEVELOPMENT result, recovery and accounted resource cleanup;
- actual SDK and agent-host MCP interoperability across permitted roles.

Fixtures must not stand in for Julia/hardware execution. No fabricated failing
trial to populate a screen. Do not require a better model to validate a correctly
executed workflow. Report the outcome and any incomplete acceptance honestly.

Measure synchronized cold/warm execution, compilation, conversion/transfer,
training, reference/measurement, idle and cleanup. Keep fixed-workload benchmarks
separate from adaptive research usefulness. Retain method failures and uncertainty.

Follow DELIVERY_PROTOCOL and applicable canonical, import, package, worker,
scientific-boundary and Hub checks. No blanket CI exemption, test suppression,
extra routine approval ceremony or mandatory bot subscription. Merge the tested
head through the normal gate. An admission-disabled engineering merge may precede
accepted-revision runtime validation; keep empirical tasks open until performed.

Continue through dependency-ready implementation, not just another plan or probe.
Return one report of delivered code/PRs, working user workflows, the capability
matrix, real evidence, resources/cleanup, remaining blockers and the smallest
next concrete action. Do not claim a background agent or deployment without
actually starting it through an authorized mechanism.

PRIMARY REFERENCES TO RECHECK

https://juliapy.github.io/PythonCall.jl/stable/juliacall/
https://docs.sciml.ai/ModelingToolkit/stable/
https://docs.sciml.ai/ModelingToolkit/stable/basics/Validation/
https://docs.sciml.ai/SciMLBase/stable/interfaces/Solutions/
https://docs.sciml.ai/SciMLSensitivity/stable/
https://docs.sciml.ai/DiffEqGPU/stable/manual/backends/
https://enzymead.github.io/Reactant.jl/stable/
https://docs.kidger.site/diffrax/
https://docs.jax.dev/en/latest/installation.html
https://docs.jax.dev/en/latest/benchmarking.html
https://docs.jax.dev/en/latest/501/compilation-cache.html
https://modelcontextprotocol.io/specification/latest
https://py.sdk.modelcontextprotocol.io/
https://docs.cloud.google.com/tpu/docs/tpus-in-compute-engine
https://docs.lium.io/developers/agents
