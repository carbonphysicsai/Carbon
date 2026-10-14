# PLT-29 offline coverage integration repair

Root assigned this bounded repair on 2026-10-14 against fixed main
`da340537f7dcbad4ef8e1670cb407bf1e92816ba`, after PR #1348 exposed two
offline-audit controls failing in the integrated tree. Root owns CI, review
and merge; one complete candidate PR, no main chasing or host execution.

## Working contract and decision

Primary map: `WAVE-C/LAUNCHPAD`. Hub is retired under the current delivery
protocol. Classification: IMPLEMENTATION_LAG in audit regression assertions,
not a scientific or runtime-authority conflict. KEEP the actual composition,
graph authentication, rebuild, scoring and execution guards.

The committed 55 measurements, 240 unrun cells and 14 source hashes describe
source `31c6fc76a6f2555183d9f9d7915a1f641ea14415`. Validate those hashes
against that immutable source, never current main, and pin the artifact bytes
so the repair cannot rewrite/relabel the observations. Validate row basis and
commands using the historical declared strategies/operations. A tampered
source identity or source hash must fail the new source validation.

Current S2 composition can statically produce a composed graph record from a
digest marker. That is not graph authentication or execution. Replace the
obsolete unavailable-combination assertion with real-boundary controls:
the marker cannot rebuild without documents or against another submission's
workspace, while the same public workspace and its correct digest build an
untrained graph. Preserve infrastructure failure classification. No training,
reference solver, provider, hidden input, chain, signer or host actions.

## Plan and acceptance

1. Reproduce the two exact failed tests at fixed main (observed: 2 failed).
2. Repair audit tests and explain snapshot/current-probe distinction in the
   audit README. No runtime or MEASURED.json edits.
3. Canonical audit and existing graph-staging regressions; Black/Ruff and
   delivery hygiene for changed files; then one PR to main.
4. Hand Root the exact candidate, clean manifest, unchanged artifact digest
   and actual focused results. Root owns full CI, review and merge.

Historical artifact SHA256:
`9fd6f49b059a6208ba626bfd7ddf19b22ca6c1752a5e562442b38098b93c864d`.
Expected changed paths: this ticket, tests/cpu/test_launchpad_offline_coverage.py,
docs/development/launchpad/offline_coverage/README.md. All open PRs were checked
for these paths; no overlap. Reversible engineering test repair only; no owner
decision or scientific/security/production qualification is supplied.

## Focused evidence

At fixed main, the exact two reported controls failed (2 failed in 5.51s).
After repair, canonical audit plus existing staging/missing-or-tampered
composed-graph controls passed: 13 passed in 21.85s. The audit set includes
both C4/X3 matching positive builds, missing/wrong-document failures, and
tampered historical commit/hash refusals. No runtime source or historical
artifact changed. Commands (CARBON_UV_GROUPS=science-jax):

`./scripts/dev/canonical.sh python -m pytest tests/cpu/test_launchpad_offline_coverage.py tests/cpu/test_level4_staging.py tests/cpu/test_battery_composed_graph.py::test_composed_graph_missing_or_tampered_documents_is_infrastructure -q`

`./scripts/dev/canonical.sh python -m black --check tests/cpu/test_launchpad_offline_coverage.py`

`./scripts/dev/canonical.sh python -m ruff check tests/cpu/test_launchpad_offline_coverage.py`

`./scripts/dev/canonical.sh python scripts/dev/check_delivery_hygiene.py --base origin/main`

Git history is intentionally required for historical source verification;
the canonical CI checkout already uses fetch-depth 0. Missing history fails
validation rather than substituting a current-source hash.
