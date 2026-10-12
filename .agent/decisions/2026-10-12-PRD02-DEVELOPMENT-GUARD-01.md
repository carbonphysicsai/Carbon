# PRD02-DEVELOPMENT-GUARD-01 — deterministic, policy-bound development Guard

Ticket: owner Product queue PRD-02 / ENVELOPE-GUARD-01. Base main:
`3025f3cefcfc7e4546e9da1ed183cb03087761ec`, including PRD-00 and PRD-01.
Status: IMPLEMENTED_WORKING_DECISION only with the companion implementation.

KEEP native `carbon.trust_map` aggregate/schema semantics and
`carbon.challenge_validator.validity` declarations/applicability. WRAP them
in `carbon/product/envelope_guard/`: validate and snapshot configuration once;
return scoped TRUST, VERIFY or REFUSE with reasons, evidence identities,
deterministic probe identity, typed failures and measured elapsed time.
The library has one DEVELOPMENT surface and no production/LIVE mode, loader,
official store, solver invocation, score/qualification or telemetry wiring.
Model callables are trusted host-supplied development adapters, not isolated
execution of hostile participant code. Digests bind content; they do not
authenticate the host's artifact, policy, acceptance or disclosure assertions.

Current main has only draft physics contracts, no PLT-01 runtime checker, and
battery physical applicability remains Undeclared. Add a small Guard-owned
development projection, never a claim that this is the upstream contract API.
Only ADOPTED laws with explicit adoption and image-bound calibration records
can affect verdicts. Initial bounded primitives are bound, initial_condition
and prefix_invariance; unsupported adopted primitives refuse configuration.
Unadopted laws are diagnostic metadata and never create a VERIFY requirement.
Do not parse or execute mathematical expressions or per-Challenge code.
Missing policy/acceptance/applicability remains explicit and fails closed.

Deterministic local probes use a SHA-256 counter construction over the query,
complete policy/version and contract, with explicit steps and call budget.
The receipt records derivation, query/probe digests and exact configuration
identities. No official/private seed or hidden case enters this construction.
Outside surrogate support, VERIFY is available only when the separate pinned
reference route supports the query; otherwise REFUSE. A map is evidence
coverage, not qualification, and never replaces reference verification of
Assistant-selected picks (PRD-03 / PB-INV/ADV).

Public-battery interface tests use synthetic predictions, maps, validity and
policy/calibration records labelled SYNTHETIC_FIXTURE. They cannot establish
battery physical validity, law adoption, MMS acceptance or production TRUST.
Also test main's actual Undeclared battery state, missing/stale/invalid inputs,
boundary bins, diagnostic-only laws, replay, failures and uncertainty gaps.
Measure a toy adapter's full-query overhead in a bounded local benchmark.
The production latency target and all scientific thresholds, probe policy,
map support/limits, uncertainty policy and acceptance remain HUMAN_INPUT.

Alternatives rejected: fork the scientific checker; import archived gates;
read protected panels; default policy values; random retry-dependent probes;
infer adoption from a Boolean or a successful MMS; infer qualification from
map coverage; call a reference solver inline; emit a production trust label.
Reversible: change this decision and the new Guard package/tests/documents;
no scientific/runtime migration or historical rescore is required. PRD-03 may
wrap this development API but must preserve its scope and verify selected picks.

Validation: 36 generator and 29 map/validity baseline tests pass natively;
focused Guard and interaction tests, pinned quality checks, exact-head CI.
The initial native temp cleanup failed and the task-owned-temp run passed.
The existing local canonical wrapper is unavailable; native is diagnostic.
Review route: Carbon Validator, plus Data Collection for reference/data joins;
the Guard code must await that named review before merge. Notify in its PR.
PR Head/owner owns merge; queue stops at handoff. Hub retired, no maintenance.
Shared draft read at SHA-256
`cff7dd9e5b32993ea4dbaa93731fd9e0776b22fd2d5958320a194b9009dc768b`.
