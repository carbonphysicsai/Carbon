# GOAL-WORKBENCH-04 measurement integration report

## Outcome

The workbench now consumes exact, retained, source-owned C-05 public DEVELOPMENT request/result bytes through a versioned, read-only adapter. One complete result carries four registered measurements and six registered physics defects into the exact job, design revision, requirement trace, and case family. A second retained source-typed `NUMERICAL_FAILURE` fixture proves that non-complete results remain non-execution evidence rather than empty success. The fixture registry now pins the complete manual association as well as the numerical identities, so a valid result cannot be rebound to another compatible-looking design or case family.

This is a newly executed, test-created public fixture retained for exact replay, not the 72-request C-05 campaign and not merely the earlier structural trace. The browser import is a replay of those retained bytes, not a fresh numerical execution. It remains unqualified: every imported scientific limit and uncertainty is `null`, every observation decision is `UNRESOLVED_NO_QUALIFIED_LIMIT`, `score_input` is absent, and qualification, protected execution, score, approval, and launch flags remain false.

## Source and fixture provenance

- Source interface: `carbon.c05.burgers-measurement.v1` → `carbon.c05.burgers-measurement-result.v1`.
- Accepted C-05 identity: PR #157, head `8dbee54dcd5bdea3a76b22812955e31fbe95e8da`, run `34789621325`, merge `e3324691666da6b8987764048d2bfff45e0578b4`.
- Generator: `tools/generate_c05_public_fixture.py`, calling `generate_development_case`, `execute_reference`, `build_measurement_request`, and `execute_measurement` without changing source behavior.
- Exact command: `env PYTHONPATH=. .venv-goal04/bin/python Business/Carbon_Fit/workbench/tools/generate_c05_public_fixture.py`.
- Environment: Python `3.11.11`; NumPy `2.4.6`; macOS `15.6`, arm64; all C-04 runtime dependency identities matched their repository pins.
- Case: public EVAL cell 2, parent 0; 64 output points; seven fixed requested times spanning `0` through `4 t_c`; deterministic test-created `1e-4 sin(x)` candidate perturbation. This scope differs from the frozen C-05 72-request campaign manifest, which requests three early-time samples through `0.25 t_c`.
- Retained numerical identities and the manual workbench association are pinned by `data/c05_fixture_index_v1.json`; exact request/result SHA-256 values are recomputed in the browser before import. `data/c05_evidence_association_v1.json` is the deterministic machine-readable record produced by importing the complete retained bundle. This inspectable manual association is not operator authentication and does not prove honest numerical execution.

The first attempted generation without repository `PYTHONPATH` failed with `ModuleNotFoundError`; the second, before all exact runtime packages were installed, failed on the C-04 dependency identity guard. Both causes were corrected without modifying runtime code.

## What the evidence informs

The result informs whether the bound candidate/reference pair exhibits raw field-phase, maximum-compression, peak-dissipation, energy-half-time, initial-condition, periodicity, mean-conservation, maximum-principle, energy-balance, and weak-PDE discrepancies. It gives exact candidate/reference values, raw errors or defects, and normalization scales for this one public case.

It cannot decide pass/fail, mandatory eligibility, preference rank, dropped-work treatment, below-uncertainty equivalence, unit/floor policy, persistence, memorization, population sufficiency, or a score. Those require qualified D-03/D-04/D-05 scientific limits and uncertainty decisions and, for aggregation behavior, a source-owned ScorePack diagnostic contract.

## Workbench changes and boundaries

The v0.4 workspace adds a closed `measurement_evidence` collection, strict fixture index, exact digest/provenance and association validation, idempotent replay, conflict rejection, typed non-complete handling, revision staleness, safe client/N1 summaries, full Engineering provenance, and an offline browser importer. The UI uses neutral labels and explicitly says “not supplied / unresolved”; it adds no pass/fail color semantics.

Wave C source code, scientific behavior, active selection, C-05 ticket/evidence, C-07 orchestration, reference policy, generator plans, ScorePack behavior, CPES Variant A/B/C, and blockers AT-09/16/19/22/30 were untouched. No Hub primary-map update is required because this is a Business workbench consumer and the existing `WAVE-C/C-05` ownership mapping remains accurate.

## Verification and next decision

Twenty-five focused adapter/workflow tests pass, including rejection of an attempted cross-design manual rebind. The retained inherited workflow tests pass, the source-owned C-05 CPU file passes, and the built `file://` artifact passes 28 Chrome checks including the exact evidence import. Schema, source, build, manifest, and deterministic bundle checks are maintained separately.

Recommendation: **B. COLLECT / QUALIFY MISSING SCIENTIFIC FLOOR FIRST.** Raw C-05 evidence is now readable, but its own contract deliberately supplies no qualified limits or uncertainty. Building a ScorePack diagnostic interface before those scientific decisions would automate comparisons whose interpretation is still undefined.
