# C-CORE-14: prospective public GPU reconstruction diagnostic

Status: implemented candidate under programme #209; canonical and delivery gates pending.
Base: `1f261a03f52d6a6cbb042e577aee1a43142e84a6`.
Primary Hub map_ref: `SYSTEM/AGENT-EXECUTION`; impact `map_structural`.
Dependencies: C-CORE-03 GPU controller and C-CORE-13 standard service composition.
Integration owner maintains programme/Hub and downstream delivery.

## Authority and C-CORE-14-D1

Owner's integrated platform mandate authorizes dependency-ready code with
accelerator admission disabled until its external requirements exist. Current
Constitution, invariants, delivery/delegation, Hub maintenance, Build Out and
constitutional overlay apply. Domain owners are Research Resource Policy,
Isolated Reconstruction Worker, Miner MCP and C-CORE-03's prospective grant and
role contract. No qualification, host maintenance, new grant, provider call,
campaign, GPU/TPU execution or network deployment is authorized by this ticket.

KEEP the existing compiler, standard research task, CampaignLedger, durable
execution queue and C03 controller. WRAP a registered recipe as one prospective
GPU-bound construction diagnostic. Compile immutable GPU environment/dependency
pins before execution; never reinterpret a CPU plan. Preserve CPU defaults,
historical catalogue bytes, granted scopes and current scientific combinations.

Require both an exact prospective campaign runtime scope and the operator's
fixed private accelerator host grant, with hardcoded MINER_RESEARCH role. No
request supplies a role, device, image, grant, host path or acceptance tolerance.
Use the existing numerical lease/reservation, durable task identity, single
replica, immutable queue claim and C03 cancellation/cleanup journals. Respect
precharged proposal trials and final headroom. Unknown dispatched work remains
charged; reconnect/retry cannot allocate another worker or invent a refund.

Return a versioned bounded non-score reconstruction result: artifact identity,
completed updates, status, timings and resource observations, with
official_eligible false and no acceptance/improvement/scientific claim. The
existing public-result envelope accepts this JSON; no CPU practice-score field
is reused. Data preparation remains the existing permitted public TRAIN route.
Final/evaluation cohorts and their score/replica budget adapters are not called.

## Implementation and acceptance

Own a prospective GPU callback module, focused tests, narrow compiler/catalog,
resource and standard service composition seams; any CLI wiring is coordinated
with the integration owner. Underlying ledger, queue, controller and host-grant
authority are unchanged. No new scheduler, evaluator or MCP transport.

Owned files: new `carbon/development_session/gpu_research.py` and focused tests;
minimal `research_catalog.py`, `research_service.py`, `research_resources.py`,
`research_tasks.py` and `carbon/miner_mcp/standard_cli.py` seams. The integration
owner approved optional `runtime.gpu_research` with one exact recomputed scope,
fixed private `gpu-worker-image.json` under the campaign root, and the existing
fixed C03 host grant. This is independent of C13 scientific_tasks combinations.
Unknown/empty/duplicate GPU scopes fail closed. No new CLI or client path option.

C-CORE-14-D2: the integration owner approved a narrower consumer admission:
the resolved controller_root in the fixed host grant must be a proper descendant
of this exact campaign root. C03's fixed host lock still prevents another
campaign/output directory from acquiring another device slot. This restriction
keeps storage attribution and Launchpad's existing C03 journal discovery within
one campaign. No issued grant needs migration. Caller-selected paths and symlink
redirects remain forbidden; failed work retains its full unknown reservation.
The controller root and the per-operation input/result directory must be
disjoint, including ancestor relationships, so retained-byte accounting counts
each owned file once. The existing CampaignLedger physical-storage admission
runs before staging and before writing the bounded result. An admission failure
after reservation retains the conservative reservation; it fabricates no refund.

Operator recovery remains the existing C03 tool: read controller_root from the
fixed private `/var/lib/carbon/accelerators/grant.json`, then run
`python -m carbon.reconstruction.worker.operator status <controller_root>` and
`python -m carbon.reconstruction.worker.operator reconcile <controller_root>`.
Use only that exact grant-owned root. This verifies controller cleanup; it does
not automatically refund or reconcile unknown CampaignLedger consumption.
Launchpad discovers the contained journal, while an unresolved numerical charge
continues to prevent new work until existing owner reconciliation establishes
its accounting. No GPU reset, unrelated process termination or new grant occurs.

Tests cover genuine GPU compilation, unchanged CPU contracts, missing/wrong/
expired scopes and host grants, strict trusted callback identity, one admitted
queue/worker attempt, replay/conflict/cancellation, unknown accounting and no
score/private-controller disclosure. Standard research service tests demonstrate
reachability. Fixtures exercise contracts without initializing an accelerator.

## Candidate evidence and use

The existing command remains
`python -m carbon.miner_mcp.standard_cli --configuration <private-profile.json>`.
An operator-bound prospective campaign must already contain the exact recomputed
GPU scope and fixed private image record; the independently authorized fixed
host grant must match. No flag, client argument or CPU grant enables GPU work.
The existing standard research practice-task operation returns non-score GPU
construction observations. Objective/capabilities are persisted under prospective
`gpu-diagnostic-*.json` identities with matching bytes/digests; historical CPU
artifacts remain intact. Combined Julia/scientific capabilities retain their
permitted methods and bind the same scaffold digest as service discovery.

Native WSL diagnostic evidence before the final storage-boundary addition:
`pytest tests/cpu/test_public_gpu_research.py tests/cpu/test_cw1_research_catalog.py
tests/cpu/test_cw1_research_tasks.py tests/cpu/test_accelerator_worker.py -q -x`:
67 passed in 115.93 seconds. Existing standard CLI regression:
`pytest tests/service/test_standard_mcp_cli.py -q -x`: 12 passed in 58.32 seconds.
After the concrete storage repair, the complete focused C14 file passed again:
`pytest tests/cpu/test_public_gpu_research.py -q -x`: 22 passed in 101.64 seconds,
including root equality/overlap, physical storage admission and discovery of the
C03 journal by the existing operator recovery tool.
Existing MCP boundary invariants: 14 passed in 2.51 seconds. Strict isolated Ruff
and Black with target Python 3.10 pass for all seven affected Python files.
These are native diagnostics, not canonical acceptance. The new test lives in
`tests/cpu/test_public_gpu_research.py`, automatically included by the unchanged
full CPU collection; there is no classifier exemption or test suppression.

Concrete integration findings repaired: the existing public-material API returns
a document/file/digest envelope, so projecting only a bare dictionary was wrong;
prospective persisted artifacts now match their advertised digest. Combined
scientific/GPU discovery now uses one scaffold identity. Timing projection uses
the controller's actual `staging` key. Accounting is restricted to this campaign
and disjoint controller/operation directories. A separate read-only source audit
verified the envelope and combined-catalogue repairs; it is not runtime evidence.

No accelerator, container, model/provider call or research campaign was run for
this ticket. Fixture cost is zero provider/allocation spending. Device memory
is explicitly unmeasured; no final GPU score or independently reconstructed
validator hardware result is available. Artifact digests are observations, not
an assertion of cross-backend portability or scientific qualification.

Completion requires the bounded source, affected tests, full applicable
canonical/quality/invariant/package/Hub acceptance and normal delivery. Hardware
execution, exclusive allocation, device-memory behavior, GPU/TPU comparisons,
fresh validator hardware execution and scientific/security qualification remain
open. A passing fixture is not a hardware acceptance result.

## Canonical fixture repair

Canonical run `35294650329`, job `105444628139`, found three failures in the
existing exact-type material allowlist fixture after 6,300 other CPU tests passed.
That fixture deliberately bypasses the executor constructor and had not populated
its non-GPU practice callback. Set `executor.practice = None` in the fixture;
production code and all allowlist/subclass rejection assertions remain unchanged.
The affected advection file plus the two public GPU material/scaffold projection
checks passed 15 tests in 14.49 seconds as native diagnostics. Strict isolated
Python 3.10 Ruff and Black passed for the repaired file. No numerical worker,
accelerator, provider call or campaign was executed. Canonical acceptance remains
required on the resulting delivery head.