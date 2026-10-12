# Registration-input tuple and reuse differences

PANEL-DIFF-GEN-01. KEEP the panel seed, validation and physical digest; export
self-contained tuples and a bounded reuse diff. No registration or dispatch.

```text
python -m carbon.challenge_pipeline.onboarding.panel_diff --brief docs/development/challenge_pipeline/onboarding-runs/generated/f02/brief.json --seed <public-seed-path> --inventory <public-inventory-path>
python scripts/dev/onboarding/panel_diff_example.py --check
```

Paths are explicit public repository documentation, not a solver/operator/
hidden-bank scan. Exit 1 means registration input remains incomplete, 2 is
malformed input; `--report-only` retains findings but returns 0.

Each tuple binds Challenge, coordinates, condition inputs, rung settings and
solver/environment/materials/observer/grammar SHA-256 pins. Named versions
are not immutable pins. No image presence, adequacy or grant is inferred.
Labels do not affect identity. Physical duplicates collapse with every alias
retained. Output snapshots cannot change when the caller edits its seed later.
A changed pin invalidates reuse; historical results are never reinterpreted.

Inventory `carbon.onboarding.public-reuse-inventory.v1` binds family,
PUBLIC_DEVELOPMENT scope, coverage (COMPLETE_FOR_REQUESTED_PINS or PARTIAL),
provenance basis and records with full `tuple`, COMPLETED/SCHEDULED state and
receipt. Identities are recomputed. Receipts are declarations; DC verifies
them. Unmatched cases are NEW only against genuinely complete coverage.
Missing/partial coverage produces UNSEEN_NOT_PROVEN_NEW, never all-new.

Reports separate `new`, `completed`, `scheduled`, `unseen` and `conflicts`.
Completed plus scheduled at one identity needs DC action, not silent
cancellation or duplicate charging. Unused inventory identities are counted.
Full tuples/aliases allow review without reconstructing local labels.

New-only CPU estimates require complete planning/reuse coverage and every
needed rung estimate. They are not measurements or billed wall time. Missing
costs stay unknown; setup, storage, failures, verification/tax need their own
lifecycle budget. Requirement variation never renews exposure.

`registration_input_ready` means structural completeness for DC review only.
`registration_adopted`, `execution_authorized` and `reuse_verified_by_tool`
remain false. Reference/domain/kit support and scientific/spend authority are
independent. This tool is not a dispatcher or new readiness judge.

## Existing-Challenge rehearsal

`f02-existing-public.json` exports the eight **already specified public triage
tuples** from `round1/reference-route-panels.json`, without extra action ×
condition combinations. Standard rung is proposed; image/observer pins and a
complete inventory are not supplied. Every tuple is therefore explicitly
blocked/unseen: no missing image or receipt is invented. Motor fixtures test
completed/scheduled reuse, aliases, changed pins, unknown costs and conflicts.

No hidden/AX42 data, EV5/journal, solver, spend or runtime changes. Hub retired.
Native diagnostics are not canonical acceptance at the submitted head.
