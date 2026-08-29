# Ticket A12 — Wave-A invariant suite in CI

**Wave:** A
**Status:** closeout candidate proposes `done`; authoritative `todo` on current
`main` until this exact closeout head is independently reviewed, explicitly
human-authorized, and normally merged
**Contract status:** A12-R1 through A12-R12 were ratified by PR #50; the
bounded invariant judge and CI lane were implemented by PR #51
**Build_Out:** v1.4 section 2 invariants and section 12 Wave-A acceptance, interpreted through `Design_Specs/Build_Out_Constitutional_Overlay.md`
**Depends on:** A4, A5, A6, A7, A8, A9, A10, A11
**Plan:** `.agent/plans/A12_invariant_ci.md`

## Goal

Close out the already-ratified and merged bounded A12 invariant judge without
changing its implementation. The exact denominator remains the twelve
numbered invariants in `Design_Specs/Build_Out.md` section 2. The canonical
lane is `python -m pytest tests/invariants -m invariant -q`.

This ticket aggregates owner behavior; it does not become a new owner of
seeding, qualification, scoring, cards, lifecycle, execution, MCP,
leaderboards, observability, science, security, or economics.

## Exact audited manifest

The branch-head closeout audit records **24 PASS / 0 FAIL**: the twelve
invariant rows, six dedicated-suite/CI criteria, and six failure/closeout
governance criteria below. Checking these criteria records merged engineering
evidence; it does not create scientific, security, network, commercial, or
production qualification. The proposed `done` state becomes authority only
after exact-head review, explicit human authorization, and normal merge of the
closeout PR.

### Exact twelve invariants

- [x] **A12-R1 — No seed leakage.** Preserve exactly: official seeds, derived
      seeds, draw IDs, or reversible identifiers never appear in
      EvaluationCard, leaderboard, MCP outputs, or miner-visible logs. Include
      A11 positive-construction redaction as R1/R4 evidence, not a thirteenth
      A12 invariant.
- [x] **A12-R2 — Practice isolation.** Preserve exactly: nominal
      practice/research execution never accesses official packs, official
      entropy/seeds, or protected exam data. Current unavailable practice
      execution proves only a fail-closed boundary.
- [x] **A12-R3 — Pinned evaluation.** Preserve exactly: every scored
      submission is bound to immutable challenge / generator / Score Pack /
      backend (container digest) versions.
- [x] **A12-R4 — Disclosure allow-list.** Preserve exactly: InternalResult /
      Model Card fields are never returned on miner-facing APIs unless
      explicitly allow-listed for the disclosure tier. Include A11 redaction
      without counting it as a thirteenth invariant.
- [x] **A12-R5 — LIVE requires qualification.** Preserve exactly: LIVE
      challenges require a complete signed human qualification manifest for
      that exact challenge version, not merely non-null YAML. Do not claim
      signer, scientific, or LIVE qualification from tests.
- [x] **A12-R6 — Execution isolation.** Preserve exactly: miner-supplied
      strategies run under enforced compute, network, filesystem, and
      wall-clock limits. Strategy execution isolation is a P0 security
      invariant; implementation may live in ops docs, but the requirement is
      here. Current Wave A proves only the negative fail-closed boundary; it
      does not claim a sandbox or security qualification.
- [x] **A12-R7 — Infra ≠ science.** Preserve exactly:
      infrastructure failures (OOM policy kill, node death, queue loss) are
      never scored as scientific / physics failures and never grant emissions.
      Preserve typed A7 retry/refund/`FAILED_INFRA` evidence.
- [x] **A12-R8 — Determinism.** Preserve exactly: re-running an identical
      official evaluation under identical versions, seeds, and limits is
      deterministic within documented tolerances. Current executable proof is
      limited to exact pinned fixture reproducibility.
- [x] **A12-R9 — No placeholder LIVE.** Preserve exactly: placeholder,
      fixture, or mock values never enter LIVE configuration or emission
      weights. A8 non-production/non-emission and future-authority absence are
      bounded evidence, not an expansion of the invariant.
- [x] **A12-R10 — No silent rescore.** Preserve exactly: historical
      evaluation records are never silently reinterpreted under newer packs;
      new pack ⇒ new scoring_version for future runs only.
- [x] **A12-R11 — Forbidden score inputs.** Preserve exactly: prior
      similarity/alignment, `estimate`, resource forecasts,
      practice/`light_*` metrics, research information value, exam fee, and
      mock metrics never enter `S_combined` / Yuma weights. Fee/payment
      isolation is a required subcase, not a separate row.
- [x] **A12-R12 — Practice is useful without revealing the realized exam.**
      Preserve exactly: Carbon measures leakage as incremental ability to infer
      protected official cases, realized stress composition, exact margins, or
      unresolved ordering after controlling for physics performance on
      evaluator-held shadow cases sampled from the declared distribution.
      Transferable rank improvement can reflect better physics and is not
      itself a leak. Practice remains declared-incomplete and outside official
      lifecycle, score, and scheduling authority. Current Wave A does not claim
      practice usefulness or leakage qualification.

### Dedicated suite and CI

- [x] Add dedicated tests only under `tests/invariants/` and mark every A12
      invariant module/test with the already registered `invariant` marker.
- [x] Provide a machine-auditable A12-R1 through A12-R12 crosswalk from each
      row to dedicated assertions and supporting A3–A11 owner tests.
- [x] Exercise public owner surfaces and explicit source/dependency guards;
      do not copy owner logic, construct success through private state, import
      legacy authority, or import existing test functions as the aggregate
      proof.
- [x] Add a dedicated Python 3.11 CI entrypoint running exactly:
      `python -m pytest tests/invariants -m invariant -q`
      The explicit directory is mandatory because current `pyproject.toml`
      roots default pytest discovery at `tests/cpu`; no dedicated tests, a
      missing or empty `tests/invariants/`, zero `invariant` marker matches,
      or complete deselection must fail rather than green the job.
- [x] Retain the complete default CPU job and repository no-new-debt quality
      gate without regenerating `.ci/quality-baseline.json`.
- [x] Pass the dedicated invariant lane, the ten supporting owner suites, the
      full CPU suite, the quality ratchet, `git diff --check`, and the exact
      repository-governance audit on the same final head.

### Failure and closeout governance

- [x] If an invariant exposes an owner implementation defect, preserve the
      failure and stop A12 closeout until a separate owner repair is reviewed
      and merged; do not weaken, skip, xfail, deselect, catch, or bypass it.
- [x] If an invariant requires a new scientific, security, protocol, or
      economic decision, stop and request the smallest named owner decision;
      do not invent a value or future type.
- [x] Record exact command/results and the twelve-row evidence crosswalk in
      `.agent/WAVE_A_REPORT.md` only during separately authorized A12
      implementation/closeout.
- [x] Update `.agent/WAVE.md` only after the exact implementation head passes
      review, explicit human authorization, and normal merge; do not mark A12
      done from contract-ratification evidence.
- [x] Preserve `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`,
      `NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, and
      `PRODUCTION_QUALIFIED` as `NO` unless separately earned.
- [x] Leave Wave B inactive. Do not alter its board, contract, handoff,
      activation hashes/gates, or begin B-01.

## Merged evidence and closeout validation

PR #50 ratified the contract: reviewed head
`6695c279728438befd6404fb81c4f7a27e382a67`, normal merge
`746e56e42c412bc8ba2eeb4d85ed83396e1a084c`, and tree
`651c568631465a4902d69036a06c937104660d37`. PR #51 merged the bounded
implementation: reviewed head
`33b4626a1ffe7d0c65336336a870a8f4a73ab92f`, normal merge/current pre-closeout
`main` `2a8b273a1167588efb4a11159da5224264d5b37a`, and tree
`cb7b23d32e3663bbf00704f1e28c16020bfb9226`.

The merged implementation contains 12 unique dedicated row proofs and 16
infrastructure/anti-greenwashing tests, for 28 invariant tests total. The
ten-file supporting-owner regression passes 2052 tests; the complete default
CPU suite passes 2310. Exact-main push run `33250521376` completed
successfully: invariant job `99095290077` recorded `28 passed in 4.22s`; CPU
job `99095290170` recorded `2310 passed in 59.52s`; and Code-quality job
`99095290146` retained `Ruff 757/776`, `Black 62/68`, removed debt `Ruff 19,
Black 6`, all five implementation Python files clean, and no new debt.

The closeout audit is **24/24 PASS** and the Build_Out section 12 Wave-A
acceptance audit is **9/9 PASS**. No owner implementation defect or new owner
decision was exposed. This documentation-only closeout must not change source,
tests, fixtures, dependencies, packaging, workflow/CI, the quality baseline,
the ratified invariant text, or any Wave-B artifact.

## Maturity ceiling

```text
A12 SPECIFIED / RATIFIED: YES on current main
A12 IMPLEMENTED: YES for the bounded invariant judge/CI scope on current main
A12 TESTED: YES for the recorded bounded engineering evidence on current main
A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO

A12 WAVE STATUS: proposed done; todo until the closeout PR normally merges
Wave A: proposed closed in its bounded engineering scope; incomplete until merge
Wave B: inactive
```

Neither the branch, a draft PR, local validation, nor green CI supplies
closeout authority. A12 `done` and bounded Wave-A closure become authoritative
only after independent review of the exact closeout head, explicit human
authorization, and normal merge. Wave-B activation and B-01 remain separate
future gates.
