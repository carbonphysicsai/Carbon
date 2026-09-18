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
