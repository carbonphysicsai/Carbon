# C-W1 — Supervised Burgers DEVELOPMENT continuation

Selected by the owner on 2026-09-15, starting at PR #185 merge
`97ee8d42467e5b3c6542eba2316cb7fe16d3ba7b`. Primary Hub map: `WAVE-C/C-W1`.
This is a continuation of the selected C-W1 DEVELOPMENT ticket. OWNER-DX-03
governs engineering delivery. No new transaction or paid inference is authorized
by this working contract.

## Working decisions and plan

KEEP the C-AUTH1 generator, B-02B compiler, C-02 JAX adapter, C-03 Docker
controls, C-04 reference, C-05 measurements, C-06 ledger, C-07 orchestration,
C-08 authenticated composition, C-10 revocation checks and C-W1 all-burn path.
WRAP these with a supervised data-only miner connection and durable session
controller. Do not import test fixtures into the operator runtime.

The prospective executable subset is `carbon.burgers-supervised-development.v2`
in `carbon/development_session/profile.py`. Freeze its canonical digest and all
realizations before the first inference. It selects ordinal 0, build 0 in every
one of the 12 cells for each of TRAIN, EVAL and STRESS: 12/12/12 parents rather
than the declared full V1 72/48/120. The 64-point, 13-time representation is
explicitly limited; no adequacy, tail, full V1 or independent-reference claim.

The active executable C-04 primary is Cole-Hopf, unlike the authoring proposal's
ETDRK4-primary wording. C-05 emits raw measurements and unresolved decisions;
the proposed quality/CVaR scoring is not active. This session cannot name an
accepted winner. All three reconstructions remain in evidence for every accepted
strategy. Failures and invalid proposals consume their respective budgets.

Implementation order: freeze honest Burgers contracts and data; connect a
restricted miner to authenticated C-08; account and enforce provider/proposal/
worker budgets; execute evaluator-owned reconstruction and measurement; produce
the signed source through domain owners; prepare distinct chain authorizations;
validate and deliver the code; dispatch only with applicable approval.

## Observed setup

The existing WSL Ubuntu 24.04 x86-64 Docker Engine host is eligible for the
accepted 2-CPU, 4-GiB/no-container-swap worker. Existing control and operator
test evidence is retained; installation and full suites are not repeated.

Subnet **567**, publisher UID **0**, owner coldkey
`5D9oP2ZTF1G7pg25EdPjCyy22315c6SvQqwrVzXg2WWF1QMu`, owner/publisher hotkey
`5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR` supersede earlier
unregistered development bindings. Historical receipts are unchanged.
Creation finalized at block **8010852**, transaction
`0x8efc1856f94403ace7e2706e8e309fbd5bcb8fdd86f1c94215bf7486d9c897c5`;
total creation spend **1.003183218 test TAO**.

Read-only observation at finalized block **8011285** found activation absent
(`FirstEmissionBlockNumber = null`), activation delay zero, registration enabled,
one of 256 UIDs occupied. The distinct miner registration observation at block
**8011286** found burn **0.433602189 test TAO** and fee **0.002141781 test TAO**.
The unsigned owner `SubtensorModule.start_call(netuid=567)` fee estimate was
**0.000257187 test TAO**. These are observations, not spend authorizations or
guaranteed future fees. Activation enables subtoken trading/alpha epochs; it
does not grant root-controlled TAO emission. Weight rate eligibility was observed
separately at finalized block 8010955 with no pending commitments.

## Acceptance and boundaries

Require focused contract, role separation, budget, disclosure, replay,
cross-association and source-handoff tests, plus applicable canonical acceptance.
Report code delivery, provider inference, numerical evidence and chain actions
separately. A pending provider credential or transaction approval must not be
reported as a completed run. AWS, Hippius integration, B-E4 campaigns, mainnet,
protected data, treasury and scientific/production qualification are excluded.

## Frozen executable contract and prospective repair

Profile digest: `sha256:689d3cfd5959dc8769bba6c6a7ad45f306696a8c191d7e97dae63586d03c4a9b`.
The authoring package supplies typed physical, candidate-query and training-data
contracts. Its fixture provenance denotes unqualified authoring; it does not
replace PDE reference trajectories or JAX training with deterministic replies.
Fixed task values include domain length 2 pi, velocity scale 1 and time scale 27.
The last value follows the full-population bound `4/(A_min*k_rms_min) < 27`.

The first engineering attempt used time scale 1 and failed the adapter's data
range guard before model initialization or training updates. The v2 amendment
was made before agent inference. Independent generation pins and all 36 cases
were retained byte-for-byte, as were the 36 completed C-04 reference outputs.
No easier cases or outcomes were selected. The original attempt remains in the
private evidence tree. A subsequent C-05 replica-name association repair reused
three completed reconstruction artifacts and the completed first prediction;
no reconstruction was repeated.

Only registered FNO and DeepONet declarative surfaces are available. The agent
may select integer steps 32..64; other task/training values remain fixed by the
compiled catalog. Every accepted evaluation retains three replicas and all
24 held-out parent predictions. TRAIN labels alone enter reconstruction. EVAL
and STRESS queries contain causal inputs; their reference labels remain with
the evaluator. Prediction uses the accepted C-03 Docker carrier controls and a
fixed trusted wrapper with no network or model-supplied executable code.

## Restricted agent and source ownership

The supervised connection exposes the seven A9 tools through authenticated NET-2
and C-08. It creates no listener. The remote model receives only the frozen
description, registered schema/scaffold/prior, structural validation/estimate,
submission identity and permitted result projection. Repository files, evaluator
realizations/labels, host tools, journal paths and credentials are unavailable.
The trusted broker signs NET-2 requests; the remote model cannot access the key.

Distinct miner hotkey: `5HmVzauSQMjErYSAzPFiKXi7uN9vM1TMLLVrjdVDJxYdPTxY`.
It finalized as UID 1 at block 8013851. It shares the owner's coldkey but is distinct from
publisher UID 0; it is not a separately owned participant. Fresh SDK observations
must resolve both parties before inference or authenticated tool use.

An exact digest-pinned DEVELOPMENT service admission allows unqualified discovery
without inventing qualification slots. Existing LIVE assessment is unchanged and
rejects the same record. C-08's fixture-binding rejection remains unchanged.
Actual authenticated execution is prospectively bound as `REAL_PATH_NON_LIVE`,
using the existing `AdmissionKind.PRODUCTION` enum solely as that execution
owner's non-fixture discriminator. This grants no production qualification,
official result or real fee policy. Engineering checks stay
`FIXTURE_DEVELOPMENT` and cannot be converted into real-session sources.

C-07 owns the new DEVELOPMENT feedback projection: complete 12-parent x
3-replica normalized measurement and physics means, grouped by EVAL/STRESS.
Exact frozen membership, plan, request/result identities and all replicas are
checked. No reference value, per-case diagnostic, seed, coordinate or path is
disclosed. Score, uncertainty and accepted improvement remain null. The original
C-07 single-result schema uses the prospectively fixed replica-0/EVAL-cell-0
anchor; the signed dossier digest binds the entire 72-measurement cohort. An
anchor is not an aggregate score.

The source builder resolves C-08 association, C-07 account, active C-06 signature
and bounded explicit export through their owners. Operators never hand-author
receipts or signatures. C-10 quarantine prevents feedback/publication of revoked
sources. After an ambiguous dispatch the session stops; retained journals win.
There is no automatic replacement campaign or resend. The checked C-W1
`status`/`resume` path remains walletless reconciliation only.

## Bounded model-run proposal

Proposed provider/model: OpenAI Responses API, `gpt-5-mini-2025-08-07`.
The exact prompt and closed function definitions are emitted by `plan` before
inference. Limits: 3 distinct proposals (invalid proposals count), 3 accepted
evaluations, 9 reconstruction replicas, at most 576 training updates,
12 provider calls, 65,536 input tokens and 2,048 output tokens per call,
7,200 seconds of worker/controller budget and 10,800 seconds session wall time.
Duplicate accepted submissions return their retained identity rather than
launching another evaluation. Unknown outcomes consume the reserved budget.

Proposed API cap: **USD 0.25**, not yet approved. The conservative priced maximum
is USD 0.24576 using USD 0.25/M input and USD 2/M output tokens. Provider usage,
including output reasoning tokens, is retained. No subscription coverage is
assumed. Owner-only credential access is now verified; the original session
approval is historical and does not authorize the amended proposal. A model/version mismatch,
incomplete response, missing usage, time limit or ambiguous HTTP result stops
the session without retry. This proposal does not claim account access.

## Supported operator sequence

Run inside the existing Ubuntu Docker Engine session at `/absolute/linux/checkout`.
`SESSION` denotes an absolute private directory; the current frozen session is
`/absolute/private/operator/burgers-session-20260915-v2`.
Preparation is resumable from its exact retained reference artifacts.

```bash
uv run --locked --group science-jax --group chain --group archive python -m carbon.development_session prepare --root "$SESSION" --image-manifest .carbon-artifacts/c03-worker-image.json
uv run --locked --group science-jax --group chain --group archive python -m carbon.development_session plan --root "$SESSION" --operator-config /absolute/private/operator/development-testnet.json
uv run --locked --group science-jax --group chain --group archive python -m carbon.development_session status --root "$SESSION"
```

After separate model-run approval and finalized miner registration, the trusted
operator invokes the real agent. Approval binds the emitted proposal digest,
validity interval and exact USD cap. Secrets are local files, never chat inputs.

```bash
uv run --locked --group science-jax --group chain --group archive python -m carbon.development_session run \
  --root "$SESSION" --image-manifest .carbon-artifacts/c03-worker-image.json \
  --operator-config "$SESSION/development-testnet.json" \
  --model-authority /absolute/private/model-authority.json \
  --api-key-file /absolute/private/openai-api-key \
  --miner-public /absolute/private/operator/miner-session-public.json \
  --miner-password-file /absolute/private/operator/secrets/wallet-password
```

Each completed authenticated submission produces `source-<submission-id>.json`
and an explicit export. Use that exact path with the existing C-W1 `status`,
`run` and `resume` commands after the distinct publication approval. `plan`
copies the observed owner/publisher identities and netuid into the session
config, binds its resource/retention policy, and leaves transaction authority
null. Old setup and historical receipt identities are never rewritten.

## Observed numerical engineering result

This is a fixed-scaffold engineering evaluation, **not agent inference or an
authenticated miner submission**. It completed 36 reference trajectories,
three FNO training replicas at 32 updates each, three isolated cohort predictions
and 72 measurements. One earlier worker failed before training updates. Four
retained-artifact verification operations launched no additional training.
Recorded controller wall time: 115.93 s reference preparation + 3.79 s failed
pre-training attempt + 283.48 s completed evaluation/reconciliation = 403.21 s.
This includes worker/validation/cleanup overhead; it is not CPU time or energy.
Software validation and CI are separate from these experiment counts.

| C-05 normalized observation, mean of 36 per role | EVAL | STRESS |
|---|---:|---:|
| Field phase RMS error | 0.562104 | 0.585724 |
| Maximum compression error | 0.231330 | 0.282235 |
| Peak dissipation error | 0.000133442 | 0.0315836 |
| Energy half-time error | 2.766480 | 2.926730 |
| Initial-condition defect | 9.62e-8 | 1.00e-7 |
| Periodicity defect | 8.19e-16 | 6.94e-16 |
| Conserved-mean defect | 0.007731 | 0.008448 |
| Maximum-principle defect | 0.000268 | 0.000993 |
| Energy-dissipation-balance defect | 0 | 0 |
| Weak local PDE defect | 1.470730 | 1.664961 |

Zero for one diagnostic does not establish a physical pass. Censoring, reference
uncertainty and unqualified limits prevent a scientific acceptance claim.
There is one strategy, no comparison baseline and no accepted improvement.
Actual provider calls/tokens/cost and new testnet transactions/spend are all zero
at this checkpoint. The prior subnet creation spent 1.003183218 test TAO.
The private `burgers-operator-observation.json` retains exact means/counts.

## Smallest competition successor

Keep the all-burn profile unchanged. Select a separate DEVELOPMENT comparison
bridge only after this session. Its smallest milestone is two active signed
results from the same frozen Challenge/profile/cohort, a prospectively approved
development comparison rule over C-05 observations, and a C-10 disposition that
rejects revoked, incomplete, disputed or indeterminate sources. Define ties,
missing/censored observations, replica uncertainty and accepted improvement
before evaluating competitors; do not import production qualification thresholds.

The bridge must bind each registered miner hotkey to its observed UID at the
relevant finalized snapshot, retain coldkey/owner distinction and invalidate
stale mappings. It can then adapt the accepted DEVELOPMENT comparison to
C-REWARD's existing takeover, self-improvement and decay state machine with an
explicit development policy and full replay tests. Multiple Challenge allocation
requires separately enabled exact allocation totals and per-Challenge ownership;
it is not inferred from one winning scalar. Protected/official/production
consumers continue to reject every DEVELOPMENT receipt and weight intent.
No treasury path, broad scientific campaign or B-E4 four-arm revival is needed.


## 2026-09-15 real session and prospective tool-framing repair

PR #188 merged as `a5a520166e97268ec32e546b12edcd448e46d210` after canonical
acceptance. The separate miner finalized as UID **1** on subnet **567** at block
**8013851**. The registration spent **0.005426933 test TAO**, including fees;
inner transaction `0x55427ecd694d0cd64a250c8193dafb1590040f9d6ed04865fe115021a4994ed7`.
The prior rejected registration spent zero. Runtime upgraded from 458 to 459;
the private operator preserved the old script and reviewed the official v459
registration/MEV delta before repinning. Activation/publication were not sent.

The first real model session used `gpt-5-mini-2025-08-07` and completed four
responses: challenge discovery, prior, scaffold, then dry validation. It proposed
FNO with 32 steps. The fourth response inserted an unsupported `tool` field
inside `arguments_json`; authenticated MCP correctly rejected it. The process
stopped with one retained proposal, no authenticated submission, no reconstruction,
no numerical evaluation, no signed source and no comparison. Token usage was
5,334 input / 303 output, priced **USD 0.0019395**. All four requests/responses
and the stopped report remain in the original private session. Earlier numerical
engineering evidence remains separate and cannot substitute for this result.

**C-W1-AGENT-TOOLS-01:** REPAIR only the model-facing tool definitions and decoder.
Seven named strict functions replace the generic function's JSON-string argument.
Every object is closed and required fields match the existing MCP contracts;
the scaffold uses its existing default. Unsupported fields still stop before
service dispatch. C-08 authentication, evaluator disclosure, budgets, scientific
profile, three-replica policy and no-restart behavior remain unchanged. This is
a prospective engineering interface amendment, not a relaxation of MCP parsing.
The changed prompt/tools produce a new proposal digest; previous approval cannot
authorize it. No new provider request is permitted until a separate bounded
session is approved. Never delete the old dispatch marker or rewrite its reports.

Plan: replace the model framing, exercise all seven tools against real MCP
decoding, test direct provider routing and the retained malformed stop, update
the board/Hub, then run applicable canonical acceptance and normal merge.
Offline synthetic replies are protocol tests only. The next empirical milestone
is a valid authenticated submission and real evaluation of this same frozen
population; it is not yet the comparison bridge described above.


## 2026-09-15 authenticated submission and worker-scope repair

PR #189 merged as `a191a9f2d7b3d24dc228c045ca5c7468fe52d9a9`. The separately
approved session (23:05:01 UTC to 2026-09-16 05:05:01 UTC; USD 0.25,
12 calls, three proposals) completed six real provider calls for USD 0.00380175.
It discovered the challenge, scaffold and prior, proposed FNO with 48 steps,
passed dry validation/structural estimation, and reached authenticated submission.
C-03 rejected staging before any Docker create because its historical guard
admitted only `FIXTURE_DEVELOPMENT`, whereas C-W1 correctly retained
`REAL_PATH_NON_LIVE`. No training updates, predictions, measurements or signed
source resulted. The attempt, entropy, provider responses and failure remain
retained. This is an infrastructure/composition failure, not scientific failure.

**C-W1-WORKER-SCOPE-01 — IMPLEMENTATION_LAG / prospective migration:** REPAIR
the C-03 staging admission to accept exactly the existing paired scopes:
`FIXTURE / FIXTURE_DEVELOPMENT` and `PRODUCTION / REAL_PATH_NON_LIVE`.
The latter enum is C-01's non-fixture discriminator, not production authority.
KEEP all exact public TRAIN archive, registered development profile, plan,
replica, policy, seed, image and container controls. No LIVE scope, protected
input, arbitrary code, evaluator credential or qualification capability is added.
Preserve source scope in the durable queue; never cast a real submission to fixture.

The old fixture-only rejection test is prospectively superseded only for the
matching real/non-live pair. Both scopes must stage/redecode the same bounded
request; cross-attempt, profile/policy mismatch, malformed scope and mismatched
admission remain rejected. Add a real Docker service test retaining non-live
queue provenance. These protocol tests remain synthetic engineering evidence.

Plan: reproduce the boundary failure with a focused staging test; repair the
closed pair check; exercise actual isolated training and retained queue scope;
run invariant/regression and service acceptance, reconcile board/Hub, then normal
expected-head merge. The stopped agent session is not restarted by this repair.
No new inference or chain transaction is authorized by engineering delivery.

Alternative rejected: relabel the real attempt as a fixture, remove the scope
guard entirely, or replay the stopped campaign. The bounded code migration is
reversible at `carbon/reconstruction/worker/protocol.py`; reverting it restores
fixture-only admission and blocks real C-W1 reconstruction. Affects C-03/C-W1
and C-07/C-08 provenance. No scientific/security qualification decision is made.
