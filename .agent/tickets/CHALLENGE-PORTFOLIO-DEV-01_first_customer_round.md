# CHALLENGE-PORTFOLIO-DEV-01 — first customer-shaped development requirements

**Status:** bounded engineering candidate prepared for PR Lead; not merged or reference-qualified.
**Start:** main `7f4f6936af8e4ebd327a9be92428c916e2185647`.
**Authority:** OWNER-PORTFOLIO-DEV-ROUND-01 (direct owner delegation),
OWNER-LAUNCH-PORTFOLIO-02, Foundation Plan §3/§4/§5, current AGENTS/delivery.
**Dependency:** F1 packet #718; this package uses its ten-section outline but
changes no F1 branch or implementation. Integration follows its merge.

## Working contract

Select and record a concrete first DEVELOPMENT customer decision for each of
f02/f06/f08/f13/f17: synthetic population, geometry/materials, success limits,
observable, numerical verification criteria, strong baselines, evidence
roles and a finite feasibility allowance. Supply a machine-readable numeric
sheet and a small offline analytical screen that reports its limitations.
These are planning labels, not five runtime IDs or a registered exam schema.

KEEP the shared authoring/reference/readiness/scoring owners. WRAP the common
packet for these jobs. Do not create a solver orchestrator or a new evaluator.
Use one PR for this cross-portfolio first-round owner decision, not one PR
that implements five unrelated runtime adapters.

## Definition of done

- Five ten-section packets and an index/reuse map describe actual choices.
- All chosen limits are distinguished from unearned reference adequacy,
  qualification and production values. Missing execution pins fail closed.
- Resource ceilings reconcile to a non-transferable aggregate; all attempts
  count, retries are zero and paid work remains undispatched.
- Offline screens cover thermal resistance/capacitance, optical feature
  support, structural mass/control scaling, acoustic mode cutoff and mixer
  Reynolds/Peclet/pressure/residence estimates. They cannot qualify a solver
  or score a model. Focused tests exercise calculations and caps.
- A lessons entry follows each execution; applicable canonical checks pass.
- Notify science and interface owners; hand one tested PR to PR Lead with
  `Codex is done; PR Lead may take over.` No push after handoff.

## Maturity and follow-up

SPECIFIED requirements; implemented/tested offline screens only. No reference
solve, paid pod, customer experiment, official score or queue transition.
Next engineering slice is f02 case/deck/extraction packaging against the
selected requirements, subject to the existing protocol's stage permissions.
Other solver adapters stay in the authorized dependency order. A numeric
choice is not itself a completed reference or training-budget study.

## Bounded validation

At `d5b70de8b`, the pinned canonical environment ran the offline screen,
`pytest -q tests/cpu/test_portfolio_round1_screen.py tests/cpu/test_challenge_pipeline.py`
(51 passed,1 existing skip), `python -m carbon.challenge_pipeline validate`,
Ruff and Black on the two Python files. The local DrvFS mount's executable-bit
artifact required ignoring EXE002 locally only; Git stores both files100644
and Linux CI retains its usual check. New tests cover independent per-family
resource caps, atomic cooling regimes, RC equilibrium/selection/coverage gaps,
dimensional estimates and the ten-section packet structure.

F1 #718's broad CI found seven assertions in unchanged
`graphite/hidden_score.py:260` (string record passed to `.get`), relayed to PR
Lead/Carbon Validator on #718 and #643; no push or fix to their owned branch.
This package's focused green is not a claim that those broad failures passed.
