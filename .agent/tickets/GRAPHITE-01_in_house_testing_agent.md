# GRAPHITE-01: Carbon's in-house research and testing agent

**Owner decision:** OWNER-GRAPHITE-01 (`.agent/DECISIONS.md`, 2026-10-02).
**Plan:** `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md`.
**Status:** planned. This ticket covers phase 1 (the harness, with no spend).
Later phases each need an owner spending grant.

## Scope of phase 1

- A `GraphiteProvider` behind the #475 campaign controller. It drives the
  existing research loop (`carbon/development_session/research_loop.py`),
  with inference through `model_provider.py` (Engy first).
- Four roles (Planner, Constructor, Attacker, Optimizer researcher), plus
  the Reader and Writer roles for literature and delivery. Each role has:
  - its own prompt, recorded by digest;
  - a tool manifest;
  - a starting rung on the owner's ladder.
- Session records: provider, model, settings, prompt digest, tool manifest,
  literature snapshot, checkout commit, and the reservation and settlement
  of every call.
- A scripted fake model for tests. No live inference in phase 1.

## Definition of done (phase 1)

- Fake-model tests for:
  - the lifecycle, including crash recovery at each boundary;
  - caps and cancellation;
  - injection-as-data;
  - refusal of confirmation material;
  - the escalation rule (one rung, only on a recorded failure).
- Mutation tests show each protection is load-bearing.
- The quality ratchet, diff hygiene and Hub checks pass.

## Out of scope

- Live inference and any spend.
- The Chutes adapter (it belongs to C-MLP-03 §2).
- Confidential compute.
- Any change to the exam rule, EV4 or the frozen verifier.
