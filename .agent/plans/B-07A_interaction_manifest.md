# B-07A v2 protocol core and discovery delivery plan

**Ticket:** B-07A — v2 protocol core, interaction manifest, and capability discovery
**Branch:** `agent/b-07a-interaction-manifest`
**Starting base:** `a0e6635d9c12743db96b9fd774a2d8b584d8fe0a`
**Starting tree:** `d13530e3f4efc8564f054626d79fd23142d15e9c`
**Primary Hub map:** `WAVE-B/B-07A`

## Eligibility and authority

Fetched `origin/main` is PR #91's normal merge. GitHub records accepted head
`f69a1877430e8ca4c7a5a1e53381d3230151c8b5`, acceptance run `34050224114`,
and successful Delivery preflight, Canonical environment, Development Hub
validation, and Merge gate. The current Wave registers make B-07S `done` only
in `SPECIFIED / RATIFIED` scope and select B-07A `todo` and unstarted.

Authority is root `AGENTS.md`, `CONSTITUTION.md`, `.agent/INVARIANTS.md`, the
Wave registers, the B-07A ticket, OWNER-DX-03 delivery and delegated-decision
protocols, the B-07S normative service protocol, the B-07R research contract,
Build Out and its Constitutional Overlay, the current maturity ledger, and the
Development Hub maintenance contract. Domain code from A2/A3/A7/A9 and
B-02A/B-02B/B-02C/B-05 is inspected as implementation authority.

## Working contract and disposition

| Component | Disposition |
|---|---|
| A3 `ChallengeKey`, A7 `StrategyHash`, A2 exact built-in Strategy document | KEEP; import or validate the existing identities without a v2 lookalike. |
| B-02A authored refs, B-02B construction refs, B-02C resource refs, B-05 measurement ref | KEEP; wire adapters preserve their exact nominal classes, fields, profiles, and digests. |
| A9 `carbon.mcp` service | KEEP unchanged and disjoint as `carbon_protocol_v1`. |
| Missing shared v2 protocol core | IMPLEMENTATION_LAG; add one `carbon.research` owner root. |
| Ticket shorthand `ChallengeInteractionManifest` | DOCUMENTATION_LAG; the sole wire resource is the ratified `InteractionManifest`; retain no second schema or alias. |
| Missing downstream providers/tasks/prior/practice/resource forecasting | KEEP UNAVAILABLE; define shared wire types but return ratified `CAPABILITY_UNAVAILABLE` from the bounded B-07A adapter. |

The B-07A working contract is the unmodified B-07S v2 wire contract. The local
adapter executes only `get_challenge_info` and `get_interaction_manifest`, uses
constructor-injected exact providers, retrieves exact historical Challenge
versions without redirecting to a latest version, verifies every returned ref
and disclosure projection, and returns stable closed errors with no exception
text. The complete twelve-operation vocabulary remains advertised in its
ratified order; unimplemented members are known-but-unavailable, not successful
stubs or unknown operations.

## Delivery slices

1. Add exact shared constants, enums, refs, requests/results, resource
   envelopes, provider protocols, bounds, and canonical codecs in one public
   `carbon.research` package.
2. Add immutable ChallengeInfo/InteractionManifest identity, exact canonical
   round trips, content-address refs, and cross-Challenge/ref validation.
3. Add bounded in-memory historical discovery providers and a local-only
   discovery adapter with namespace/operation/type/bounds/reference/provider/
   disclosure precedence and no listener or credentials.
4. Add positive and adversarial runtime tests, installed-wheel imports, v1 and
   shared-domain regressions, and retain B-07S's nine specification invariants.
5. Record B-07A decisions/evidence, reconcile ticket/Wave/maturity/Hub sources,
   regenerate derived Hub output, inspect the complete candidate, and use one
   ready PR for applicable automated acceptance and expected-head normal merge.

## Validation and maturity

Local canonical execution remains unavailable for the already-recorded B-07S
reason: Docker is absent, so the pinned Linux acceptance image cannot run.
Python 3.11.16 and the pinned development tools were provisioned into an
isolated native macOS environment for diagnostics, focused tests, wheel tests,
and regressions; those results are useful but are not represented as canonical
Linux evidence. GitHub's pinned ready-PR run supplies acceptance.

B-07A may earn bounded `IMPLEMENTED` and `TESTED` only for shared v2 types,
discovery resources, and the local discovery adapter. Full-service conformance,
scientific/security/network/commercial/production qualification, public prior
activation, remote transport, and LIVE remain unearned.
