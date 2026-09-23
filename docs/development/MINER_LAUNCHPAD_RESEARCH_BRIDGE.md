# Launchpad DEVELOPMENT research bridge

Ticket: `.agent/tickets/C-MLP-02_development_research_bridge.md`.
Status: accepted engineering bridge; one browser-launched practice/freeze/independent-final path observed. Multi-iteration campaign acceptance remains incomplete.

## Existing receipt attachment

The local operator can attach a source handoff created by Carbon's existing
DEVELOPMENT pipeline. Use the Linux environment with the locked `chain`, `archive`
and `science-jax` groups installed. Carbon's secure registry/source fixtures do
not run on native Windows; the rehearsal controls remain host-portable.

```sh
uv run --locked --group chain --group archive --group science-jax python \
  scripts/dev/miner_launchpad/controller.py \
  --state-dir /absolute/private/launchpad \
  --development-source /absolute/private/session/source-SUBMISSION.json
```

Supply the actual existing handoff filename. No wallet is opened, transaction
issued, inference requested or numerical work launched by attachment. Keep the
listener on loopback. The source handoff and all its source-owner journals and
exports must remain available in their existing layout.

Attachments persist in the controller database across browser and controller
restarts. Repeating the same attachment returns its original opaque identity.
A changed source cannot silently replace an existing attachment. The HTTP API
does not accept source paths or attachment requests. The local session token
authorizes access to the operator's attached public projections only.

Each read resolves the existing handoff, bounded export, C-06 signature and
current receipt lifecycle, and C-08 authenticated submission association. The
display and JSON export contain exactly C-07's existing public projection plus
Launchpad attachment metadata. No private source directory, seed, case manifest,
measurement array, transport context, verification key or signing material is
served. Export rechecks the source rather than downloading stale browser state.
Invalid, revoked, missing or changed sources become `READBACK_UNAVAILABLE`; the
UI hides their receipt. This is a readback failure, not a new scientific result.

An attached receipt is explicitly labelled `OPERATOR_ATTACHED_EXISTING_SOURCE`.
It does not count as a Launchpad campaign, practice iteration or improvement.
`COMPLETE_UNRESOLVED` remains Carbon's unresolved DEVELOPMENT disposition.
This slice does not derive a comparison, rank candidates or create a receipt.

## Real campaign integration dependency

The accepted PR #206 C-W1-D4 `research_campaign` is the reused runner.
It owns public practice, the adaptive research loop, retained hypotheses and
capability requests, exact recipe freeze, independent final reconstruction and
existing report artifacts. Its accepted implementation is now integrated.
Its CLI currently exposes run/resume/status/report; that is not evidence of a
Launchpad-safe pause/stop contract. Its D4 resource grant cannot authorize a new
Launchpad campaign. No unrelated checkout or in-flight campaign is modified.

The bridge validates an accepted runtime, a campaign-specific
resource envelope, exact identity and worker ownership, durable dispatch and
cleanup/reconciliation before enabling launch. Only allow-listed existing report
projections may cross into the browser. A stopped process alone cannot establish
that owned compute stopped. Unknown cleanup must remain visible.

The real acceptance predicate remains at least two genuine research iterations,
retained unsuccessful attempts and measured usage, exact candidate freeze,
Carbon submission and independent reconstruction, actual receipt/disposition,
browser reconnect and verified stop of owned work. Engineering source fixtures
and browser readback fixtures do not satisfy that predicate.

## Trusted runner adapter

> **Superseded for new launches by C-MLP-02-D11 (23 September 2026).**
> Registration is the only product admission gate. `--research-profile` now
> takes a `carbon.launchpad.runner-profile.v2` record: `schema`, `profile_id`,
> `principal`, `enabled`, `paths` (the same seven inputs), `accepted_revision`,
> `campaigns_root` and `runtime` (the composition the grant used to declare),
> plus the optional `research_guidance` and `disabled_reason`. There is no
> `grant_file` and no `account_ref`. A launch reads the chain for the miner's
> hotkey **before anything is recorded** and admits a
> `carbon.launchpad.campaign.v1` campaign with the resulting registration; the
> launch may carry the miner's own budget (`ceilings`, `elapsed_seconds`,
> `final_reserve`), and with none there is no limit - including no epoch count.
> Each launch key is its own campaign under `campaigns_root`. A v1 profile is
> refused with `PROFILE_V1_RETIRED` and a message naming the change. Campaigns
> launched under a grant stay readable, pausable, stoppable and reconcilable -
> held only as a `RetainedGrant`, which admits no new work - and are never
> resumed. The development grant remains on the development path: the
> development CLI's `--grant-file`, and Carbon's internal Workbench service on
> Carbon's own campaign. The text below records the grant-era contract as it
> was.

`--research-profile /absolute/private/profile.json` installs an operator-only
`carbon.launchpad.runner-profile.v1` record. Without it, research admission is
disabled. The record has exactly `schema`, `profile_id`, `principal`, `grant_file`,
`account_ref`, `enabled`, `paths` and `accepted_revision`. `paths` contains the
existing runner's seven file inputs: image_manifest, analysis_image_manifest,
operator_config, api_key_file, miner_public, miner_password_file and
quarantine_journal. Files must be absolute private operator inputs; browser
requests cannot install or replace them. The existing registered subnet-567 miner
is verified through the original trusted signing boundary before research.

New Launchpad campaigns select the accepted C-W1-D5 v2 continuation policy. The
runner freezes its prompt/tool identity; this does not transfer D5's separate
program grant. Legacy command defaults and existing campaign manifests remain
unchanged. Own-research records expose concise hypothesis history, decisions and
epoch stop reasons separately from verified independent DEVELOPMENT results.
Raw transcripts and internal accounting payloads are not browser projections.

The separate `carbon.launchpad.research-grant.v1` must explicitly be APPROVED,
with exact principal, miner, campaign/root, runtime/image identities, provider and
account reference, all resource dimensions, original lifetime and absolute expiry.
Only one campaign per grant is supported. The grant-derived run identity and
canonical root survive different browser retry keys and controller databases.
All operations remain charged by CampaignLedger; no Launchpad consumption ledger
exists. D4 v1 manifests are neither migrated nor assigned another allowance.
The approved limits may narrow the existing envelope but cannot exceed it or
remove its final reconstruction/cleanup reserve. Unknown usage stops new paid
dispatch. The runtime remains exact-clean-accepted and images source-matched.

The HTTP namespace `/api/v1/research` lists preflight and safe records; POST
accepts only `{ "profile": "operator-configured-opaque-id" }` plus an idempotency
key. `/api/v1/research/ID` re-resolves export; the pause, resume, stop and reconcile
subroutes accept only empty objects. The loopback session authorizes this local
operator's configured records. This is not a multi-user hosted authorization model.

Pause is a durable request and blocks new ledger admission, tool selection and
final submissions at cooperative boundaries. An in-flight bounded operation may
finish; PAUSED is not a training checkpoint. Stop persists first, requests
supported research-worker cancellation and resolves original cleanup journals.
Fixed final/reference calls can settle to their existing deadline. Unknown
provider, final or worker outcomes keep reservations and remain actionable as
RECONCILIATION_REQUIRED; operator reconciliation never retries them. A campaign
OS lock and durable generation prevent a second/stale controller dispatch.

The browser projects actual attempted operations, completed practice, own concise
hypotheses/capability requests, usage and frozen candidates. It never serves the
private owner HTML/JSON report. Final comparisons are resolved through existing
C-10/C-06/C-08 authority on every view/export, preserving every real disposition.
Current execution is labelled LIVE PRACTICE/RESEARCH, explicitly not qualified
LIVE. Historical attached evidence retains its separate label.

## Outstanding empirical acceptance

`MINER_LAUNCHPAD_VALIDATION_REQUEST.json` preserves the original REQUESTED_NOT_GRANTED
request. The owner subsequently approved it explicitly; approval was installed
only in its private operator grant. Its USD0.50 / four
trial envelope includes the existing minimum final reserve of twelve replicas,
8,640,000 numerical milliseconds and eight selection/report calls. That headroom
does not guarantee successful reconstruction or sufficient total work. Actual
provider invoice limits are not inferred from token-cost estimates.

The admission-disabled engineering slice was accepted before empirical execution;
both browser campaigns used exact source-matched images and separate private
grants. C-MLP-02's multi-iteration acceptance remains selected. Controller tests,
fixed jobs and D4's separately owned campaigns do not close it.

### First browser campaign: retained stop, acceptance incomplete

The fresh `cmlp02-browser-validation-01` campaign ran from accepted implementation
`3b6d2d9b5947b139c396f755fef8077d6885fbe8` (PR #207), tree
`e05d615693b2c6e592d0cfd52106c750dd6f91d4`, with exact source-matched worker images.
The browser clicked Launch; this was not attached historical readback. Its agent
was Carbon autoresearch policy v2, using `gpt-5-mini-2025-08-07` through the existing
OpenAI Responses account route and bounded local CPU workers. No identity or
registration transaction was created.

It fetched the legitimate public TRAIN/practice data, then submitted one malformed
numerical proposal: `kind=practice`, `action=run_python`, `strategy_json=null`.
The SDK correctly rejected that branch mismatch before task dispatch. The model
subsequently chose `no_feasible_action`. This is a retained model decision, not
proof that no feasible intervention exists. Its structured outcome reported
`used_feedback=false`. No training completed, candidate froze, submission occurred,
or independent DEVELOPMENT disposition was produced. Controller `COMPLETED`
only means execution ended; the research epoch outcome is `STOPPED`.

| Recorded dimension | Used | Reserved / uncertain at close |
| --- | ---: | ---: |
| Reasoning calls | 4 | 0 |
| Token-based reported cost | USD0.00632685 | USD0 |
| Attempted / completed experiments | 1 / 0 | 0 |
| Numerical worker time | 309,660 ms | 0 |
| Public reference trajectories / invocations | 96 / 96 | 0 |
| Retained bytes charged | 1,704,496 | 0 |
| Final replicas | 0 | 0 |

Cost is the existing ledger's published-rate calculation from provider token usage,
not an independently reconciled invoice. All four calls and the rejected proposal
remain charged. The one-campaign allowance is used; unused dollars do not create
another campaign grant. No D4/D5 consumption or private evidence transfers.

Actual Chromium connected at desktop 1440px and mobile 390px, launched the fresh
campaign, reconnected to the same opaque run, requested pause, observed `PAUSED`
after the active bounded operation settled with zero reservations, then resumed
with unchanged deadline and accumulated consumption. After terminal completion,
the controller restarted with a new session token; browser readback preserved
the exact campaign and accounting without replay. Cleanup verification found
zero reserved operations, zero cleanup targets and no containers using the two
exact campaign images. The controller was then closed. No live crash or training
cancellation was injected into this campaign; those remain engineering-fixture
evidence. No hosted service was deployed.

The approved-envelope display overflowed both viewports. The existing fixture
omitted envelope values; adding them reproduced the failure. Wrapping that text
repairs the display. Two stale UI notices claiming no provider calls were possible
are corrected. The SDK now gives an allow-listed practice/workspace correction
for the observed invalid request, without automatic conversion or new authority.
The existing capability log retains the contract rejection and intended benefit;
this observation supports clearer guidance, not a wider execution surface.

**IMPLEMENTED / CANONICALLY TESTED** describes the accepted bridge. This real
browser/model attempt validates bounded launch, pause, resume, reconnect, terminal
restart and accounting for its observed path. **REAL CAMPAIGN VALIDATED** for the
required multi-iteration/freeze/independent-final path remains incomplete.
**PRIVATE HOSTED VALIDATED** remains unavailable. The following separately
approved continuation preserves this terminal record and original grant.

### Second browser campaign: real final result, one practice iteration

The owner explicitly approved the exact remaining-allowance grant for
`cmlp02-browser-validation-02`. It was bound to accepted #212 implementation
`68948008c2ff921ad62484739a62e0e4042ef90b`, tree
`5e5d2607dfc39c458a5b2edbe9fe153b79e388c7`, with exact source-matched trusted and
analysis images. The first grant remained terminal and immutable. A private
operator allocation checked its settled consumption and assigned only the
unconsumed original dimensions, including one remaining epoch and the original
absolute expiry. CampaignLedger remained the sole consumption authority. No D4/D5
grant, identity registration or core-upgrade runtime was substituted.

The real browser launched opaque run `7a2ddd1046a4ba5624717e9839cb0d24` using the
same existing model/provider/CPU route. One genuine JAX practice experiment
completed 256 updates in 10.667 worker seconds, after public reference preparation.
Its descriptive practice score was `0.7117244846428699`; sampled EVAL and STRESS
`energy_path_max` gates failed. The complete learning curve and practice record
remain in the existing research workspace/report. The browser receives the
existing uniformly sampled curve, not protected numerical assets.

The agent consumed that practice response and selected the practiced recipe,
with `used_feedback=true` and a rationale referencing its returned measurements
and gate failures. It chose to stop exploring after one trial despite two trial
slots remaining. This shows feedback-informed selection, **not** a second
feedback-driven research iteration. Do not force another trial or describe the
agent's budget rationale as a controller-measured impossibility.

The frozen Strategy uses FNO depth 3, width 32, 16 modes, batch size 8, 256 steps,
learning rate 0.002, EMA inference, hard initial condition and conserved mean.
Its exact strategy hash is
`sha256:4c835a67f9e75bc33b6c5af8ccceea18f73e0ac34a208c539b3ae91729632886`;
construction-plan digest is
`sha256:f81b1390c99a0d337d0e12461d2ce5f0ed4e6620bffdc957009eb1f4b5c03eaa`.
The existing authenticated submission path independently reconstructed three
baseline and three challenger replicas, then completed registered measurements,
reference refinement and the existing signed comparison.

Actual disposition: **REJECTED_MANDATORY**.
`accepted_development_improvement=false`; official, protected, network and paying
eligibility remain false. Baseline mandatory failures were EVAL/STRESS
`energy_path_max` and STRESS `maximum_principle`; challenger failures were
EVAL/STRESS `energy_path_max`. Descriptive scores were baseline
`0.7523084606246769` and challenger `0.7160141828612655`. Neither score overrides
admissibility, proves physical validity or makes this a qualified comparison.

The existing final comparison binds registration
`sha256:b70212d9dd9c5025312cd78ea2f9ee4fcd33ce12ceafb164aee979107e2baa24`
and report `sha256:56f01a8a1f364652824b12ae62edcbcdb79ff70dd42686606c4af57388c1cdaf`.
The authenticated run view/export resolves that source again. Detailed private
reports remain with the existing runner; private directories are not browser routes.

| Recorded dimension | Second campaign | Both browser campaigns |
| --- | ---: | ---: |
| Reasoning calls | 4 | 8 |
| Token-based recorded cost | USD0.00589815 | USD0.01222500 |
| Attempted / completed practice | 1 / 1 | 2 / 1 |
| Numerical worker time | 988,043 ms | 1,297,703 ms |
| Reference trajectories / invocations | 168 / 168 | 264 / 264 |
| Retained bytes charged | 33,321,635 | 35,026,131 |
| Final replicas | 6 | 6 |
| Epochs charged | 1 | 2 |
| Reserved / uncertain consumption at stop | 0 / 0 | 0 / 0 |

The second campaign logged no new capability requests or rejected practice
proposals. The first campaign's rejected request stays retained and charged.
Costs are the existing ledger's token-based estimates, not invoice verification.
All cumulative dimensions stayed within the original cycle envelope. Both epoch
slots are now consumed; unused calls, dollars or trial slots do not authorize a
third campaign, reset the terminal records or renew the expiry.

After the final result, the current fixed two-epoch loop prepared an epoch-2 plan
under the one-epoch grant and ended `INTERRUPTED`. No epoch-2 reservation or
provider operation was admitted. The browser then requested STOP and reconciliation;
state became `STOPPED`. Verification found zero reserved operations, zero cleanup
targets in the two owned worker journals and no containers for either exact image.
The accepted runtime remained clean and unchanged. Record this finite-completion
seam for a coordinated successor repair; do not patch the frozen experiment or
increase its grant to hide it.

Desktop 1440px and mobile 390px browser reconnects retained both identities and
the first campaign's exact projection. The browser downloaded the freshly
verified second record. After terminal controller shutdown/restart with a new
session token, its projection matched that export exactly, including final
result, deadline, candidate and accounting. No operation replay occurred. The
controller was then closed after verified cleanup; no background execution is
promised or pending.

**REAL SINGLE-ITERATION PATH OBSERVED** now covers browser launch, genuine
practice, feedback-informed selection, exact freeze, authenticated submission,
independent reconstruction, actual rejected disposition and verified cleanup.
**REAL CAMPAIGN VALIDATED** for C-MLP-02's required multi-iteration behavior remains
incomplete. No GPU, TPU, Julia, hosted or scientific qualification is inferred.

### Observation dashboard and core coordination

The successor dashboard presents the existing allow-listed cost categories,
hypothesis, active reservations, practice gate failures and independent disposition.
Its line plot joins only measured training-data-loss samples by optimizer update;
it is neither a Burgers spatial/time field nor an independent quality result.
Missing or malformed curves produce no plot. The complete projected values remain
available in the expandable record, which now stays open across polling.

Core programme [#209](https://github.com/carbonphysicsai/Carbon/issues/209) and
MCP workstream [#210](https://github.com/carbonphysicsai/Carbon/issues/210) own the
prospective shared service interfaces. Their executor reserved research SDK
transport identity, reconstruction catalogue and Julia reference changes, and
requested coordination before ownership/cleanup changes. This UI slice changes
none of those interfaces. The finite-completion repair and future external-agent
integration must coordinate with that owner and ship as tested successors. Current
CPU observations cannot establish unexecuted accelerator or Julia capabilities.

### Prospective finite-completion repair

After coordination, the core #209 executor assigned the narrowly scoped existing
campaign-orchestrator repair to the Launchpad workstream. The successor iterates
the epoch identities in the already validated frozen manifest instead of always
attempting epochs 1 and 2. The immutable v1 envelope remains exactly two epochs;
v2 can stop at its narrower one- or zero-epoch ceiling without preparing an
inadmissible next epoch. All existing per-operation admission, final reserve,
deadline, authentication, failure and cleanup checks remain authoritative.

This is a prospective code repair. It does not migrate the observed campaign,
erase its INTERRUPTED transition, change its eventual STOPPED state, extend its
grant or reinterpret REJECTED_MANDATORY. A completed finite controller path is
independent of accepted scientific improvement. A failed final operation still
prevents the completion marker and retains its unresolved reservation.

The non-spending regression runs the real orchestrator and CampaignLedger with
explicit fixture boundaries for provider, authentication and numerical work.
The unmodified loop reproduces resource-admission failures at zero and one
epochs. Tests also cover the original two-epoch v1 envelope, two-epoch v2 grants,
rejected final dispositions, unchanged terminal resume, early stop and failed
final reservations. These fixtures are engineering evidence only; multi-iteration
model-driven validation still requires a new explicitly admitted experiment.

## Focused verification

### Prelaunch inspection and the pause switch

Issue #223's immutable guidance repair is merged in #227. Its engineering
acceptance is complete; real multi-iteration campaign acceptance remains open.
Campaign 03 has not launched.

**The owner experiment pause was lifted in full on 22 September 2026.** No class
of campaign is withheld by it and no current configuration asserts it. It is not
a reason to stop before a campaign runs.

The switch itself stays, because lifting a pause is not a reason to delete the
means of pausing. The existing private runner profile can carry the optional
explanatory field `"disabled_reason": "OWNER_EXPERIMENT_PAUSE"` only with
`"enabled": false`.
Launch and resume reject on the server, including direct HTTP calls. Status,
authorized export, stop and supported reconciliation remain available. The profile
is not a global cancellation mechanism: an already-dispatched operation must use
the existing durable pause/stop control and retain any unresolved consumption.

For new guided launches, the opaque review token binds the referenced grant
digest as well as the operator configuration. A grant changed after browser
review requires a fresh review. Historical profile-only tokens only recover
already-recorded runs whose original configuration and grant pins still match;
they never admit a fresh campaign after this change.

An authenticated disabled review retains guidance, configured runtime/image
identities, catalogue/training controls, expected dependencies, grant expiry and
the existing final reserve. Configured maxima and reserve requirements are not a
new reservation transaction or an assertion of remaining budget. CampaignLedger
remains the source of actual consumption. No host probe runs during a review;
installed dependencies, visible devices and runtime evidence stay explicitly
unobserved/unattached. GPU runtime extensions remain unavailable to the existing
CPU campaign adapter until the core-owned campaign composition is accepted.

Start the private loopback control surface with a disabled operator profile:

```sh
python scripts/dev/miner_launchpad/controller.py --port 8788 \
  --state-dir /absolute/private/launchpad-state \
  --research-profile /absolute/private/disabled-runner-profile.json
```

Open `http://127.0.0.1:8788` and enter the locally printed session token. For a
no-profile controller preview, omit `--research-profile`; research is unavailable.
Do not reuse another campaign's state directory or enable an old grant. A new
owner resumption decision and exact matching runtime/resource authority are still
required; completion of core engineering never starts a campaign automatically.

The core integration owner confirmed that C-CORE-14 / #233 exposes a public TRAIN
GPU construction diagnostic with `score=None`, not a Launchpad GPU campaign or
final comparison. The named prospective profile is
`carbon_jax_cuda13_nvidia_development_v1`. Core #209 owns the missing
campaign/final-comparison composition. Local RTX 3060 device visibility is a
historical observation; NVIDIA Container Toolkit maintenance approval, exclusive
host admission and actual miner/validator hardware and cleanup evidence are still
missing. Reuse `.agent/plans/CORE_PLATFORM_RESOURCE_REQUEST.md`; do not duplicate
its request or infer access from device visibility. A prospective configuration
must leave runtime/image, final-comparison and budget/grant bindings unresolved
until those contracts exist. The existing CPU final reserve is a reference, not
an invented GPU budget. No new campaign or grant is created by preparation.

### Optional private research guidance

Issue #223 adds `research_guidance` to the existing private runner-profile JSON.
The operator supplies nonblank UTF-8 text, at most 4096 bytes; exact whitespace
is retained. Omit the field for historical behavior. Empty/null/invalid/oversized
values fail before campaign admission. Keep actual private objectives out of
checked-in profiles and public reports.

The authenticated browser reviews this configured task alongside the resource
envelope and accepted revision. It is read-only: edit the private operator profile
before launch, then refresh the review. A guidance launch binds an opaque
`review_digest`; changed configuration is rejected. Browser requests still cannot
provide task text, private paths, keys, executable commands or endpoints.

The launch transaction persists the exact versioned text/digest in the existing
run record before dispatch. The campaign manifest binds it to runtime and policy;
the epoch plan binds the complete initial observation plus policy identity with
an `effective_input_digest`. The policy's existing digest still pins its immutable
instruction template. Guidance is separate user-role task input and has no
authority over scientific gates, disclosure, construction, permissions, resource
limits, final reserves or independent evaluation. Those remain enforced by the
existing trusted services.

Resume uses the persisted input and verifies digests, including retained epoch
plans even for completed guided campaigns. Changed guidance/configuration fails
closed. Legacy records without the optional field stay absent and retain their
existing interpretation. The owner's readback/export includes frozen guidance and
input digests; it does not expose the private epoch plan or model transcript.

The deterministic test sequence of initial experiment and two revisions is an
engineering information-flow fixture. It does not prove live-agent adaptation.
Real acceptance separately counts completed experiments and measured updates,
tracing previous practice feedback to a hypothesis, allowed strategy change and
new result. Earlier practiced candidates remain selectable. A final mandatory
rejection does not erase workflow evidence or become accepted improvement.

Runtime rebinding for an unlaunched, explicitly authorized campaign is an operator
action after accepted delivery. Preserve the original private grant and install
a distinct successor file using the same existing closed grant schema and grant/
campaign/root identities. Retain the authorizing record and old/new digests; only
the explicitly approved runtime and matching images may change. Existing launch
and manifest pins prohibit doing this to an admitted campaign. No automatic grant
migration, renewal, cap increase or second campaign is implemented here.

### Commands

```sh
CARBON_UV_GROUPS="chain archive science-jax" ./scripts/dev/canonical.sh --focused \
  tests/cpu/test_miner_launchpad_development.py tests/cpu/test_miner_launchpad.py -q
python scripts/dev/miner_launchpad/browser_smoke.py
node --check scripts/dev/miner_launchpad/app.js
```

The browser test uses a real local HTTP server and Chromium. Its deliberately
injected readback records exercise rendering/export/invalidation only. Canonical
Python tests separately resolve signed authenticated engineering sources through
the actual Carbon owners, including revocation and corruption failures.

## Miner-lane research compute and the published exam environment

The owner's direction is that a miner's research compute is their own choice,
and that Carbon's obligation is to tell them what the validator will run the
exam under. This section records how the bridge implements that and what it
deliberately does not change.

### Why the launchpad required a validator's grant, and no longer does

Accelerator admission was built as a single path written to validator
requirements: an owner-signed host grant asserting exclusive use of a dedicated
device. It was applied to both roles because there was only one path. Dispatch
was disabled, so nothing forced the question of whether a miner could satisfy
it; when a real host appeared it could not, because compute-process enumeration
is unavailable under that host's driver model.

C-CORE-19 split the lanes and repaired the controller. `PublicGPUPractice`, the
launchpad's public research consumer, still loaded the strict grant above it and
was deliberately left to this change. It no longer does.

What replaces the grant is not a weaker version of it. The strict claims are
absent, and their absence is recorded on every result through the miner-lane
assurance label: task-owned container identity and exit, pinned image and
environment lock, input and plan content binding, per-run device binding from
the installed record, task-owned removal and bounded deadline, memory and
output - and, explicitly not established, whole-device exclusivity, foreign
compute-process absence, device memory sanitisation between tenants, and
whole-device release after the run.

The reason this is safe is specific to what a miner receives. A miner is given a
public construction plan and public TRAIN material, so device side-channels
defend nothing, and whether the miner computed what they submitted is answered
by content binding and independent validator reconstruction - exactly as it is
for a CPU submission, which has never required a grant, a lease, or proof that
nothing else was using the CPU.

### What still stops a miner-lane launch

Compatibility is an engineering fact, not a grading privilege, and these are
checked before the ledger charges anything:

- an approved campaign grant whose runtime declares this GPU scope;
- an installed host device record compatible with the GPU workload profile,
  read before the reservation and reread under the numerical lease so a record
  swapped underneath a run stops it;
- the pinned GPU worker image and a container device runtime.

A missing strict grant, unknown whole-device telemetry, an empty established
enumeration registry, and a GPU that is driving a display or shared with the
miner's own work are **not** among them.

### Controller storage and request identity

Controller state is resolved from the campaign root that already owns every
other artifact a run writes, rather than from a `controller_root` field inside
an operator-authored grant. The request identity changed with it: the strict
grant digest gave way to the per-run device binding, so it is versioned to
`carbon.public-gpu-reconstruction.request.v2` rather than quietly reshaped.

A record written under v1 cannot be re-derived once the grant it was built from
is gone, and is deliberately not replayed through the callback. The ledger sees
a different request for the same task and refuses - the same answer it gives for
a changed recipe, and the right one for both, because neither is the work the
current request describes. Those records stay readable and recoverable through
the campaign status, report and export projections, which key on the operation
rather than on its request identity. Reading one never re-runs it, re-charges it
or moves it onto the new lane.

The result schema moves to `carbon.public-gpu-reconstruction.result.v2` because
the body now carries the lane label. A v1 result recorded no lane and is not
retrospectively read as though it had.

### Campaign runtime composition

A grant declaring `runtime.gpu_research` previously reached a runner that
refused the key outright, while the prelaunch review displayed a CUDA backend
beside a blocker saying the campaign composition was unavailable. A miner could
not tell which statement to believe. The campaign runner now assembles the
composition, so the two no longer contradict each other.

The declared scope is checked in two clearly separated places, and the names
say which is which:

- `declared_gpu_runtime` checks **shape only**. A campaign must compare the
  runtime it can compose against the runtime it was granted before it may charge
  for generating role material, but the scope binds that very material, so its
  content cannot be recomputed yet.
- `registered_gpu_image` is the **binding** check. It recomputes the scope from
  the operator's image record and this campaign's own public TRAIN cases once
  they exist, and `PublicGPUPractice._authorize` refuses to construct a callback
  whose recomputed scope differs from the frozen manifest.

A grant that passes the first has not yet been believed. A malformed scope now
advertises nothing: the review reports the composition as unavailable and leaves
the described research runtime CPU rather than showing a CUDA backend the runner
would refuse.

### Research runtime and final evaluation stay separate

Choosing a GPU to research with does not choose the evaluator. The independent
DEVELOPMENT comparison keeps its own CPU worker image, reference material and
accounting, and the review states this before launch rather than leaving it to
be discovered afterwards. Julia scientific tasks keep their own CPU route; no
Julia-on-GPU capability is inferred from the JAX GPU selection.

The review reports readiness as distinct states - connection configured,
dependencies inspected, compatible runtime available, consent active, task
admitted, device execution observed, task completed, cleanup verified,
independent evaluation available, official qualification - rather than one
green badge. Personal research does not require official qualification; a
missing runtime really does prevent a managed job from executing.

### The published exam environment

`carbon.public-validator-exam-environment.v1` is served at
`/api/v1/exam-environment` and rendered in the browser. It projects
`docs/development/VALIDATOR_EXAM_ENVIRONMENT.md`, reading every value from the
constants reconstruction actually runs under rather than restating them, so a
change to the real envelope that is not reflected in the disclosure fails a test
instead of leaving miners reading a contract Carbon no longer honours.

It is readable with no grant, research profile, model-provider key or agent
identity: deciding whether to take part should not be gated behind any of them.

It carries the backend profile, pinned dependencies, precision, resource
envelope, containment, the accepted submission object, and the statement that
miner research hardware is unconstrained and no provider is prescribed. It
reports qualification as **declared, not qualified**, names MQ-008 as the owner
of backend support, and discloses the measured CPU instruction-set divergence
rather than omitting it. It contains no seed, draw, case, credential or private
path, and a test asserts that.

### Compute choices

The launchpad offers destinations rather than a provider dropdown: this machine
on CPU, this machine's GPU on the miner lane, a compatible host the miner
already controls, and fully off-platform research followed by submission. No
Carbon-run training job is required to submit a design.

Carbon has no per-provider branch - what differs between a laptop, a
workstation and a rented instance lives in the installed host device record,
which carries the provider as a token - so attaching a remote host is the same
path rather than a separate integration. Provisioning a host *for* a miner is a
different thing, and none is implemented; those remain listed as unavailable
with the reason each is missing, rather than appearing as choices that would
fail when selected. No provider quote, GPU SKU or working provider integration
is claimed anywhere.
