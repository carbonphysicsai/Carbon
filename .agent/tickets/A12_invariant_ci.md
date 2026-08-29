# Ticket A12 — Wave-A invariant suite in CI

**Wave:** A
**Status:** `todo`
**Contract status:** documentation-only candidate; ratified only after independent exact-head review, explicit human authorization, and normal merge
**Build_Out:** v1.4 section 2 invariants and section 12 Wave-A acceptance, interpreted through `Design_Specs/Build_Out_Constitutional_Overlay.md`
**Depends on:** A4, A5, A6, A7, A8, A9, A10, A11
**Plan:** `.agent/plans/A12_invariant_ci.md`

## Goal

After separate implementation authorization, add one dedicated CI entrypoint
that fails when any currently enforceable cross-cutting Wave-A invariant
regresses. The exact denominator is the twelve numbered invariants in
`Design_Specs/Build_Out.md` section 2.

This ticket aggregates owner behavior; it does not become a new owner of
seeding, qualification, scoring, cards, lifecycle, execution, MCP,
leaderboards, observability, science, security, or economics.

## Exact manifest candidate

Every implementation criterion remains unchecked. This documentation-only
candidate implements and tests nothing.

### Exact twelve invariants

- [ ] **A12-R1 — No seed leakage.** Preserve exactly: official seeds, derived
      seeds, draw IDs, or reversible identifiers never appear in
      EvaluationCard, leaderboard, MCP outputs, or miner-visible logs. Include
      A11 positive-construction redaction as R1/R4 evidence, not a thirteenth
      A12 invariant.
- [ ] **A12-R2 — Practice isolation.** Preserve exactly: nominal
      practice/research execution never accesses official packs, official
      entropy/seeds, or protected exam data. Current unavailable practice
      execution proves only a fail-closed boundary.
- [ ] **A12-R3 — Pinned evaluation.** Preserve exactly: every scored
      submission is bound to immutable challenge / generator / Score Pack /
      backend (container digest) versions.
- [ ] **A12-R4 — Disclosure allow-list.** Preserve exactly: InternalResult /
      Model Card fields are never returned on miner-facing APIs unless
      explicitly allow-listed for the disclosure tier. Include A11 redaction
      without counting it as a thirteenth invariant.
- [ ] **A12-R5 — LIVE requires qualification.** Preserve exactly: LIVE
      challenges require a complete signed human qualification manifest for
      that exact challenge version, not merely non-null YAML. Do not claim
      signer, scientific, or LIVE qualification from tests.
- [ ] **A12-R6 — Execution isolation.** Preserve exactly: miner-supplied
      strategies run under enforced compute, network, filesystem, and
      wall-clock limits. Strategy execution isolation is a P0 security
      invariant; implementation may live in ops docs, but the requirement is
      here. Current Wave A proves only the negative fail-closed boundary; it
      does not claim a sandbox or security qualification.
- [ ] **A12-R7 — Infra ≠ science.** Preserve exactly:
      infrastructure failures (OOM policy kill, node death, queue loss) are
      never scored as scientific / physics failures and never grant emissions.
      Preserve typed A7 retry/refund/`FAILED_INFRA` evidence.
- [ ] **A12-R8 — Determinism.** Preserve exactly: re-running an identical
      official evaluation under identical versions, seeds, and limits is
      deterministic within documented tolerances. Current executable proof is
      limited to exact pinned fixture reproducibility.
- [ ] **A12-R9 — No placeholder LIVE.** Preserve exactly: placeholder,
      fixture, or mock values never enter LIVE configuration or emission
      weights. A8 non-production/non-emission and future-authority absence are
      bounded evidence, not an expansion of the invariant.
- [ ] **A12-R10 — No silent rescore.** Preserve exactly: historical
      evaluation records are never silently reinterpreted under newer packs;
      new pack ⇒ new scoring_version for future runs only.
- [ ] **A12-R11 — Forbidden score inputs.** Preserve exactly: prior
      similarity/alignment, `estimate`, resource forecasts,
      practice/`light_*` metrics, research information value, exam fee, and
      mock metrics never enter `S_combined` / Yuma weights. Fee/payment
      isolation is a required subcase, not a separate row.
- [ ] **A12-R12 — Practice is useful without revealing the realized exam.**
      Preserve exactly: Carbon measures leakage as incremental ability to infer
      protected official cases, realized stress composition, exact margins, or
      unresolved ordering after controlling for physics performance on
      evaluator-held shadow cases sampled from the declared distribution.
      Transferable rank improvement can reflect better physics and is not
      itself a leak. Practice remains declared-incomplete and outside official
      lifecycle, score, and scheduling authority. Current Wave A does not claim
      practice usefulness or leakage qualification.

### Dedicated suite and CI

- [ ] Add dedicated tests only under `tests/invariants/` and mark every A12
      invariant module/test with the already registered `invariant` marker.
- [ ] Provide a machine-auditable A12-R1 through A12-R12 crosswalk from each
      row to dedicated assertions and supporting A3–A11 owner tests.
- [ ] Exercise public owner surfaces and explicit source/dependency guards;
      do not copy owner logic, construct success through private state, import
      legacy authority, or import existing test functions as the aggregate
      proof.
- [ ] Add a dedicated Python 3.11 CI entrypoint running exactly:
      `python -m pytest tests/invariants -m invariant -q`
      The explicit directory is mandatory because current `pyproject.toml`
      roots default pytest discovery at `tests/cpu`; no dedicated tests, a
      missing or empty `tests/invariants/`, zero `invariant` marker matches,
      or complete deselection must fail rather than green the job.
- [ ] Retain the complete default CPU job and repository no-new-debt quality
      gate without regenerating `.ci/quality-baseline.json`.
- [ ] Pass the dedicated invariant lane, the ten supporting owner suites, the
      full CPU suite, the quality ratchet, `git diff --check`, and the exact
      repository-governance audit on the same final head.

### Failure and closeout governance

- [ ] If an invariant exposes an owner implementation defect, preserve the
      failure and stop A12 closeout until a separate owner repair is reviewed
      and merged; do not weaken, skip, xfail, deselect, catch, or bypass it.
- [ ] If an invariant requires a new scientific, security, protocol, or
      economic decision, stop and request the smallest named owner decision;
      do not invent a value or future type.
- [ ] Record exact command/results and the twelve-row evidence crosswalk in
      `.agent/WAVE_A_REPORT.md` only during separately authorized A12
      implementation/closeout.
- [ ] Update `.agent/WAVE.md` only after the exact implementation head passes
      review, explicit human authorization, and normal merge; do not mark A12
      done from contract-ratification evidence.
- [ ] Preserve `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`,
      `NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, and
      `PRODUCTION_QUALIFIED` as `NO` unless separately earned.
- [ ] Leave Wave B inactive. Do not alter its board, contract, handoff,
      activation hashes/gates, or begin B-01.

## Must not

Do not implement A12 in this documentation task. Do not add or mark tests,
change source, modify CI/workflows, change dependencies or packaging,
regenerate the quality baseline, modify `.agent/WAVE.md`, create the Wave-A
report, check a criterion, mark A12 `in_progress`/`done`, close Wave A,
activate Wave B, claim launch readiness, or greenwash an invariant failure.

## Contract-ratification validation

The ratification candidate must pass the existing ten-suite focused owner
regression, full default CPU suite, no-new-debt quality gate against exact base
`37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1`, `git diff --check`, exact
six-document manifest audit, protected-blob audit, and exact-head remote/PR
topology check.

The `12/12` feasibility audit is contract evidence only. Because current main
has no marked invariant test,
`python -m pytest tests/invariants -m invariant -q` is the future A12
implementation entrypoint and is not a green ratification result.
