# PLT-37 — Design-refill tranche identity envelope

**Status:** IN_PROGRESS, 2026-10-14. Assigned by Test Lead/Root as a bounded
repair after the r8.7 owner-side design-refill failure. Starting main:
`c7f40bedc33e5ddda4bcf6920e54cc7cc9ef6dfa`.

## Problem and scope

`DesignBank._write_jobs` emits the public producer envelope
`{"tranche": <tranche-id>, "jobs": [...]}`. `truth_env.solve` runs those jobs
and stamps records, then unconditionally indexes `document["fingerprint"]` to
construct its summary. That raises `KeyError` after solving a tranche whose
records may already be complete. Preserve resumability and avoid repeat solves.

Implement the smallest explicit identity-envelope repair in the truth worker.
Existing batch files identified by `fingerprint` must keep returning that exact
field/value. Design-bank files identified by `tranche` must return that exact
field/value, without synthesizing a batch fingerprint. Reject missing,
ambiguous, empty, or malformed identities before invoking `TruthService.run`.

## Acceptance

- Reproduce the design-bank envelope using public synthetic jobs through the
  real `truth_env.solve` control path; no container, provider, host, protected
  input, solver spend, or private records.
- Add a regression proving tranche identity is returned and records are solved
  once; prove normal fingerprint identity remains unchanged.
- Add fail-closed coverage proving malformed/ambiguous identities do not start
  the truth service or append records.
- Preserve output-version checks, solver provenance, record schema, terminal
  retry/resume behavior, timeout/error classifications, and existing jobs
  contracts. Do not modify historical job/record files or suppress errors.
- Run focused canonical regressions and required hygiene. Submit one PR to
  `main`; Root owns merge. No host deployment or scientific/security/LIVE
  acceptance is claimed.

## Boundaries and completion

Primary map: `WAVE-A/VALIDATOR-23` (existing producer design-bank interface).
Hub maintenance is retired under OWNER-DX-03. Completion means implementation
and tests pass on the exact reviewed head with required CI/Merge gate success;
Root owns review integration and merge. This ticket does not change the
scientific contract, scoring, runtime production policy, or qualification.

## Validation evidence

The focused canonical regression command was:
`CARBON_UV_GROUPS="science-jax" ./scripts/dev/canonical.sh python -m pytest tests/cpu/test_battery_truth_environment.py tests/cpu/test_challenge_validator_design_bank.py tests/cpu/test_design_bank_solve_fails_closed.py -q`.
Baseline: 32 passed. The added tranche/identity controls failed against the
old source; repaired focused suite: 37 passed. Canonical Black and Ruff checks
passed for both changed Python files. The candidate was then fast-forwarded
to current main; both affected Python files were unchanged by that base sync.
Final exact-head CI and Merge gate remain external delivery predicates.

## Exact consumer binding

The existing producer-helper digest test demonstrably refuses the repaired
truth worker while its former digest remains registered. Re-pin that one
helper to the repaired file's exact SHA256; keep the digest-validation guard
and every other helper registration unchanged. This is a prospective binding
update, not permission to bypass an identity check or reinterpret old results.
Validation: `./scripts/dev/canonical.sh python -m pytest tests/cpu/test_campaign_producer_stages.py -q`.
