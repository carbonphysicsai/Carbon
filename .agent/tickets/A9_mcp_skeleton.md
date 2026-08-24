# Ticket A9 — bounded Miner MCP Wave-A control-plane skeleton

**Wave:** A

**Status:** `todo`

**Build Out:** C9 Wave-A control/disclosure surface; deferred C9/C11 mock/light
execution remains Wave B

**Direct contract dependencies:** public A2, A3, A6 model, and A7 APIs

**Decision authority:** A9-R1--A9-R15 become ratified only after the
documentation-only candidate is independently reviewed, explicitly
human-authorized, and merged

**Implementation plan:** `.agent/plans/A9_mcp_skeleton.md`

## Current maturity

```text
A9 EXACT BOUNDED CONTRACT: specified and ratified only after independent
review, explicit human authorization, and merge of the documentation candidate
A9 IMPLEMENTED: NO
A9 TESTED: NO
A9 SCIENTIFICALLY_QUALIFIED: NO
A9 SECURITY_QUALIFIED: NO
A9 NETWORK_QUALIFIED: NO
A9 COMMERCIALLY_VALIDATED: NO
A9 PRODUCTION_QUALIFIED: NO
A9 WAVE STATUS: todo
A10--A12: todo
```

Documentation is not implementation or test evidence. A separate task must be
explicitly authorized after ratification before any source or test work begins.

## Goal

Implement later, but do not implement in the ratification task, the smallest
bounded in-process miner control/disclosure boundary that:

- exposes exact public Challenge information;
- uses public provider seams for coarse priors and declarative scaffolds;
- delegates exact dry validation to A2;
- returns a pure non-executing structural/prior estimate;
- delegates submission intake, status, and published-card retrieval to A7;
- consumes query budget before every result lookup; and
- exposes only positive, bounded, requester-authorized public projections.

## Exact Wave-A tools

Register exactly:

```text
get_challenge_info
get_prior
get_mock_scaffold
dry_validate
estimate
submit
get_submission_result
```

Do not register aliases including `info`, `prior`, `scaffold`,
`validate_strategy`, or `submit_strategy`. `light_compare`, `light_train`, and
`list_my_submissions` are unavailable and excluded from Wave A.

## Exact control/disclosure split

Wave A contains no execution. In particular the structural estimate uses no
MockContext, A8 service, fixture-official context, official or fixture Score
Pack, `ScoreInput`, or `InternalResult`, and exposes no floating-point quality
score, predicted official score, rank, predicted card status, predicted gate
result, weight, or emission value.

The exact future `MockExecutionRequest`, `MockRunOutcome`,
`MockTrainEvalService.run_mock`, mock pack identity, mock resource policy, mock
execution/disclosure, `light_compare`, `light_train`, and adaptive-query
security evidence remain a separately ratified Wave-B contract. A8-R15
continues to block that execution-dependent work. It does not block the
separately ratified pure structural/prior estimate.

## Exact public boundaries

- Calls use exact schema version `"1.0"` and an ordered-field `McpCall`; a raw
  dictionary is not the first untrusted boundary, so duplicate fields remain
  detectable.
- Exact frozen/slotted data nominals, slot-declared exact errors with frozen
  supported public payloads, fields, response schema, provider protocols,
  resource policy, root exports, and handler ordering are defined in
  `.agent/plans/A9_mcp_skeleton.md` and A9-R1--A9-R15.
- Trusted composition supplies the same exact A3 registry instance to A9 and
  the injected A7 service; A9 neither inspects nor repairs A7 private state.
- `McpResourceLimits` is mandatory, immutable, finite, and injected with no
  defaults. No query, fee, quota, concurrency, rate, or retry value is invented.
- Missing prior, scaffold, or estimate provider fails with the stable
  tool-unavailable error. The implementation adds no production provider,
  prior publication, scaffold body, or provider cache.
- RequesterIdentity is supplied out of band by trusted composition. Current
  structural equality/requester binding is not authentication; a future
  network adapter owns authentication.
- A9 retains no request/result/provider cache or history and creates no second
  submission store.

## Challenge, provider, submit, and result behavior

- Challenge information performs exact-key lookup without listing and exposes
  only exact `challenge_key`, `lifecycle_status`, `fixture_origin`,
  `effectively_live`, and `allowed_backbones`, plus the `"1.0"` response
  framing version. Exact draft, fixture, and live records are visible; only A3
  `is_effectively_live` supplies the Boolean and no visibility is an admission
  or qualification claim.
- Priors are coarse, public, versioned, hashed, non-executable, non-binding,
  one-channel, and use only closed `STRUCTURAL_STEER`, `AVOID`, `EXPLORE`, and
  `NOT_INCLUDED` directive kinds. Actual content and closed vocabulary remain
  owner inputs.
- Scaffolds remain separate, exact-ID/version/hash/Challenge-bound,
  declarative, owned, A2-valid, optionally prior-referenced metadata, and
  explicitly execution-deferred. A9 never fills/derives them from priors or
  calls A8.
- Submit calls only exact A7 `submit` followed by exact A7 `get_status` and
  returns a `SubmitReceipt` containing that exact `SubmissionStatusView`.
  It is a lifecycle acknowledgement, not proof of queueing, acceptance,
  payment, provenance, execution, score, validity, rank, weight, or emission.
- Result retrieval consumes query budget before A7 lookup, calls `get_status`
  first, and calls `read_published` only for exact `PUBLISHED`. Other states
  return status and no card. Not-found and wrong requester collapse to one
  stable public error.

## Bounded implementation Definition of Done

- [ ] The implementation branch starts from the reviewed ratification merge
      after a fresh exact main/tree/status/CI/ticket/concurrency check; only A9
      is marked `in_progress` in that separately authorized task.
- [ ] `carbon/mcp/` contains exactly `__init__.py`, `model.py`, `providers.py`,
      and `service.py` for A9, with no server or network adapter.
- [ ] Exact frozen/slotted data nominal types, slot-declared fixed-payload
      errors, and enums implement all fields and closed values ratified by
      A9-R3--A9-R7/A9-R13, rejecting subclasses at public boundaries.
- [ ] Exact `"1.0"` call/response framing is enforced with no normalization,
      default, or version negotiation.
- [ ] Ordered `McpField` tuples preserve and reject duplicate, unknown,
      missing, non-string, and over-limit fields before dictionary conversion;
      exact-string unknown tools remain tool-unavailable rather than acquiring
      a semantic field schema; raw-envelope construction is storage-only and
      all checks occur inside `McpService.call` after required admission.
- [ ] Mandatory injected `McpResourceLimits` bounds exact-built-in iterative
      request capture, response nodes/sequences/strings,
      `max_response_integer_bits`, aggregate bytes, and every exact-top-level
      concurrent call with no default values.
- [ ] Capture accepts only the ratified exact built-ins, creates fresh ownership,
      preserves graph topology for exact A2/A7 delegation, bounds cycles,
      aliases, huge integers, UTF-8, and containers, and never invokes hostile
      `repr`/`str`.
- [ ] The exact seven tools are registered; every otherwise well-formed,
      resource-admissible exact-string alias plus `light_compare`,
      `light_train`, and `list_my_submissions` returns stable tool unavailable
      without downstream calls.
- [ ] Exact A3 delegation performs exact-key projection for draft, fixture,
      and live records, calls only A3 for effective-LIVE truth, and exposes only
      the five allowed Challenge fields.
- [ ] Exact prior/scaffold/estimate provider protocols are injected, absence is
      stably unavailable, and provider exceptions or malformed outputs within
      response meters fail closed as integration errors; a first-detected
      response-meter breach remains a resource error.
- [ ] Prior projections are one-channel, exact-version/hash/Challenge-bound,
      coarse, closed-directive-only, and contain none of the prohibited prior
      fields or canaries.
- [ ] Scaffold projections are exact-version/hash/Challenge-bound, separately
      verified by exactly one canonical A2 call as valid, freshly owned,
      optionally prior-referenced metadata, and always execution-deferred with
      no provider/caller alias; a supplied scaffold selector must equal the
      returned exact scaffold ID.
- [ ] `dry_validate` delegates exactly once to current A2 and returns a fresh
      exact public validation result without adding admission or execution.
- [ ] `estimate` uses exact A2 validation plus provider/public-prior structure
      only, returns an order-preserving directive subset and fixed non-binding
      disclaimer, and fails closed without exact providers.
- [ ] Tests prove estimate performs no execution, MockContext/A8 call,
      fixture/official context or Score Pack use, ScoreInput/InternalResult
      construction, or quality/score/rank/card/gate/weight/emission prediction.
- [ ] `submit` delegates only to exact A7 `submit` then `get_status`, preserves
      exact capacity-permitted `REJECTED`/`RECEIVED` and duplicate-open
      idempotence, preflights the maximum canonical receipt response envelope
      before A7 mutation, and returns the exact status in `SubmitReceipt`.
- [ ] A9 never calls A7 validation, admission, fee-start, retry, cancellation,
      execution, completion, publication, or A6 storage methods and creates no
      duplicate fee/lifecycle effect.
- [ ] Every result poll consumes exact query budget after request validation
      but before any A7 lookup; exhaustion is stable and exposes no retry-after,
      queue position, or completion-time estimate; an exact gate budget error
      becomes a fresh fixed public budget error with chaining suppressed, and
      a non-exact-`None` gate return fails integration before A7 lookup; no
      post-consume outcome refunds the budget.
- [ ] Result retrieval calls A7 `get_status` first, calls A7 `read_published`
      only for exact `PUBLISHED`, returns exact A6 `EvaluationCard` only then,
      and covers every current A7 state.
- [ ] Not-found and wrong-requester retrieval collapse to the same stable
      public error without revealing which condition occurred.
- [ ] Every exact public error is nominal and slot-declared with an immutable
      supported public payload (excluding interpreter-owned exception runtime
      metadata); it has the ratified fixed code/message, suppresses chaining,
      accepts no diagnostic fields, and leaks no values, paths, provider or
      owner exceptions, configured limits, secrets, contexts, packs, or state.
- [ ] RequesterIdentity exists only out of band, is freshly reconstructed for
      downstream calls, and is documented/tested as structural binding rather
      than authentication.
- [ ] Responses expose no private A6/A7 store/record, InternalResult,
      StrategyHash, ChallengeKey from submission storage, attempt/fee/retry/
      handle/pin history, context, seed, pack, path, private cause, fine score,
      margin, stress breakdown, private/free-form diagnostic, or
      owner-unsupplied timestamp; exact A6 `public_diagnostics` stays empty.
- [ ] A9 retains zero request, response, provider, or result history/cache and
      creates no second submission store; provider publications remain
      provider-owned and A7 retains its existing process-local state.
- [ ] Source/dependency tests enforce use of only public A2/A3/A6-model/A7 APIs
      and exclude A4/A5/A6-store/A7-store/A8/A10+, legacy, PoC, neurons, MCP/
      HTTP SDKs, Bittensor, Torch, JAX, NumPy, chain, weight, and emission code.
- [ ] `carbon.mcp.__all__` is exactly the ratified surface with no owner-type
      re-export or compatibility alias.
- [ ] Canonical focused coverage exists only at
      `tests/cpu/test_mcp_skeleton.py`, including optional-dependency isolation
      and installed-wheel/outside-tree import.
- [ ] Full default CPU regression passes without changing A0--A8 behavior,
      tests, fixtures, dependencies, lockfiles, packaging, CI, quality baseline,
      business/publication files, or A10+ implementation.
- [ ] Ruff, Black, and repository no-new-debt checks pass with every changed
      Python file clean; evidence remains bounded engineering evidence and
      creates no scientific, security, network, commercial, production,
      leaderboard, frontier, treasury, chain, weight, or emission claim.

## Exclusions

Do not add production provider content/policy, a scaffold body, a mock pack,
mock/light execution, real training, a network server, authentication, default
limits/fees/quotas/rates, A10+, or any scientific/security/network/commercial/
production qualification claim. The documentation ratification task must not
check any criterion above.

**Canonical future test:** `pytest tests/cpu/test_mcp_skeleton.py -q`
