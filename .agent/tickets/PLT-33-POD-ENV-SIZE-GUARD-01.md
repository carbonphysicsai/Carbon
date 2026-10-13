# PLT-33: Graphite environment CI guard

Authority: Platform2 queue item PLT-33 and Test Lead's owner-authorized priority
dispatch on 2026-10-13; GRAPHITE-POD-ENV-SIZE-01; OWNER-DX-03.
Starting base: main e627c260d326be679d09fddd50540a556f88e790.

KEEP the 90,000 runtime cap, the existing 8,000 CI reserve, the real `_env`
builder, typed pre-dispatch refusal and zero-spend semantics. WRAP the real
builder with offline measurements and a CI assertion for the declared L4
transport budget. No provider, credential, training or protected data access.

Platform's separate PLT-29 owns moving the manifest out of the environment.
This ticket edits neither its transport nor the existing environment test.
Current overlap scan found no open PR on the new guard/test/doc/ticket paths;
#1294 is merged. A red guard caused by the existing transport is a dependency
finding, never grounds for lowering the reserve or weakening the assertion.

Expected manifest: this ticket, one decision, `runpod/environment_guard.py`,
`test_graphite_environment_guard.py`, and `POD_ENVIRONMENT_GUARD.md`.
Tests: unit boundary/diagnostic/non-disclosure controls; real current-head
environment for both JAX and PyTorch with the L4 transport character budget;
frozen-current-recipe history comparison against #991. Existing environment,
pre-dispatch and L4 carry regressions remain required. On this Windows host,
canonical CI is required; native diagnostics are labelled as such.

Completion is conditional on guard success at the exact candidate head and
applicable CI/Merge gate. PR Head owns merge. Host grant/rerun acceptance,
provider capacity measurement and every qualification remain unavailable.
