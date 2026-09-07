# B-E2 implementation plan — Julia and reference failure boundary

**Starting main:** `c484fd308d866d4b05a2765a984ec014dd96386e`
**Starting tree:** `fadd82c3cfe6d604f7a068a93886d534ea9cd077`
**Ticket:** `.agent/tickets/B-E2_reference_failure.md`
**Delivery:** one branch and pull request under OWNER-DX-03
**Primary Hub map_ref:** `WAVE-B/B-E2`
**Implementation state:** implemented and native-verified; accepted normal merge
remains the conditional completion boundary

## Authority and start state

Fetched `origin/main` is the normal B-E1 merge requested by the owner. Its
second parent is accepted B-E1 head
`831a34598d6779d369f01de3523c3d8ee0385d18`; accepted CI run `34124228848`
passed Delivery preflight, Canonical environment, Development Hub validation,
and Merge gate. B-E1 is therefore bounded `done` in SPECIFIED / IMPLEMENTED /
TESTED scope. The merged board selects B-E2 next as `todo` and unstarted.

The B-E1 plan, evidence, and maturity ledger still described acceptance and
normal merge as pending. That discrepancy is `DOCUMENTATION_LAG`: the
historical candidate evidence is preserved, while stale present-tense
closeout wording is reconciled in this ticket.

The canonical wrapper was invoked once and failed closed because Docker is
unavailable. Native CPython 3.11.16 diagnostics use the locked Carbon tool
versions. GitHub's pinned environment remains the shipping authority.

## KEEP / WRAP / REPAIR / REPLACE audit

- **KEEP:** B-04 `ReferencePolicy`, primary/witness request and one-use grant,
  `ReferenceResolutionRecord`, `ReferenceRunRecord`, exact role/identity/
  provenance records, run terminal precedence, comparison outcomes, positive-
  only admission, fixture assets, protected errors, and curated root surface.
- **WRAP:** add one standard-library, in-process response adapter and TEST_ONLY
  fixture graph under `carbon.evaluation`. The adapter accepts only complete
  exact B-04 bindings and emits only `ReferenceRunRecord`.
- **REPAIR:** reconcile B-E1 documentation lag and extend the B-04 module-seam
  invariant for the two intentional B-E2 files. No B-04 runtime semantics or
  public root exports change.
- **REPLACE:** none. Archived Julia code remains quarantined.

## Working engineering decisions

1. `B-E2-D1` keeps the B-04 one-use attempt authority and wraps it with a
   nominal primary/witness service adapter. The adapter validates every exact
   request, grant, resolution, case, role, policy, implementation, environment,
   method, configuration, precision, hardware, representation, scope,
   applicability, conditioning, uncertainty, provenance, diagnostic, resource,
   and artifact-descriptor binding before accepting a response.
2. `B-E2-D2` represents retry only as an immutable ordered trace of separate
   B-04 attempts. A retry uses a new request/grant/resolution/run identity while
   preserving the original idempotency and scientific execution context. The
   trace never collapses or overwrites the first failure and authorizes no
   production retry policy.
3. `B-E2-D3` keeps all providers and payloads fixture-only. Hostile, partial,
   stale, cross-bound, malformed, exceptional, or duplicate responses fail
   closed through exact B-04 reasons; there is no fallback input or output.
   MMS remains `MANUFACTURED_SOLUTION_VERIFICATION` /
   `VERIFICATION_ANCHOR` and cannot be relabeled into answer-key or validation
   authority.

These are reversible engineering decisions inside B-E2. They select no solver,
scientific method, numerical tolerance, retry/fallback policy, service topology,
qualification, security acceptance, or production behavior.
They were routed together to issue #42 comment `5572204359` for SciML and
technical-owner awareness.

## Ordered implementation

1. [x] Audit current B-04 and archived Julia ownership.
2. [x] Implement exact primary/witness registered-service adapters over B-04's
   one-use request/grant/resolution/run machinery.
3. [x] Implement hostile response validation, fixed exception classification,
   identity/provenance failure, and atomic duplicate rejection.
4. [x] Implement an identity-preserving attempt history and deterministic
   supported, uncertain, conditioning, applicability, unsupported, numerical,
   malformed, provenance, identity, infrastructure, timeout, transport,
   process, disagreement, retry, and MMS fixtures.
5. [x] Add focused CPU and invariant tests for exact bindings, adversarial
   responses, no fallback, no candidate/score/truth authority, and preserved
   B-04 behavior.
6. [ ] Reconcile ticket/board/evidence/maturity and Hub source, run all required
   validation, then ship through applicable acceptance and normal expected-head
   merge.

## Explicit gaps and maturity ceiling

No Julia runtime, SciML package, solver, MMS/analytic implementation, protected
reference service, production cache, network transport, credentials, service
isolation, real retry/fallback policy, reference method qualification, or
scientific value is implemented. B-E2 may earn bounded SPECIFIED, IMPLEMENTED,
and TESTED fixture engineering only. Every scientific, security, network,
commercial, production, qualification, ranking, frontier, settlement, weight,
emission, and LIVE state remains unearned.

## Successor repair B-E2-R1 — 2026-09-08

Historical B-E2 merge `602628d3c62f01524336db888da8fcfc7ed379d7`
is not rewritten. The successor branch starts from current main
`bb22a6a356f7e649fc7060e8c620f1956e4643b7` after inspecting PR #101's
documentation-only integration impact.

The repair keeps the B-04/B-E2 object graph and wraps the existing response
boundary with one pre-comparison reconstruction pass. It rebuilds every exact
response carrier, every `component_bindings` element, and the closed
`observed_reasons` tuple before equality or terminal selection can consume
them. Wrong element types and incomplete carriers become malformed response
failures without invoking their equality behavior. Complete but cross-bound
nested identities retain the existing identity-failure class. A protected
control signal that can still arise during post-provider processing is
normalized through the existing fixed B-04 control-signal pattern after the
attempt is burned.

Runner-level primary and witness tests cover wrong nested element types,
incomplete exact carriers, cross-bound nested identities, repeated invocation,
unchanged valid responses, and unchanged malformed/provenance/identity
classification. B-E4 remains `todo` and unstarted. No adjacent runtime module,
public interface, fixture authority, status vocabulary, fallback, scoring,
truth/candidate authority, production behavior, or LIVE capability changes.
