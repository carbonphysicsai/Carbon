# LAUNCHPAD-T05-CELLS-MATRIX-01 — computable acceptance records

Status: implementation. Preparation base: immutable reviewed T06
`215eb6680ac3bccae63cdf7a2ca8ddb36f7e30c8`, tree
`c596d661c9280ebbd78a763c1dbbaa025324ac69`.

## Authority and working contract

Root's explicit sequencing amendment permits static implementation now in an
isolated worktree; actual T06 merge and fresh-main reconciliation precede the
single T05 PR and behavioral CI. Pause T05 if T06 requires an affected repair.
Platform2 acknowledged the exact seven new-file lease and retains full-suite /
T07 ownership. Root alone merges and dispatches hosts, actual tests and spend.

Authority: complete published LAUNCHPAD_E2E_SUITE_HANDOFF at
`57c3e019f7f7de6deb274ffd5283395c91dfaa50`, T-05; current owner
OWNER-LAUNCHPAD-E2E-SUITE-01 D1/D4/D5/D6 and riders; acceptance plan sections
2 and 3. Constitution, invariants and OWNER-DX-03 control. The owner record
and four historical backfill cells are already on main; reuse them after
reconciliation, never copy, rewrite or reinterpret them into this PR.

KEEP T06's single fixed-public-path reader / Cells.status, imported unchanged.
Exact reader blob: `bcc7d245c40bb852efc71f845c6cd500b121c599` at
`scripts/dev/launchpad_acceptance/release_check.py`; package initializer blob
`74abc6cc4f479578cd331bb4da260a7195bec794`. No fallback or duplicate reader.

Add a strict public v1 writer/validator, covering matrix as immutable data, and
`python -m scripts.dev.launchpad_acceptance status`. New records are explicit
operator-supplied observations, not generated tests or automatic PASS decisions.
Constrain public evidence to digest/code/reference/assertion data; reject
credentials, identifiers, addresses, balances/spend and profile contents even
when nested. Retain profile digests. Validate before opening a destination;
fixed public date/cell paths, no symlinks, append-only exclusive create.

Print every defined cell with latest recorded result and original revision.
Evaluate each of the seven section-3.6 predicates separately, identify its
owner and unmet/missing evidence. Add F15 to base flow coverage under D6; include
C10 Torch GPU and C11 device-request driver. Tier-2 compute is nonblocking;
D5 levels stay explicitly BLOCKED; D1 LA-F17 is separately BLOCKED/UNTESTED
without becoming a general launch blocker. Historical PASS never states that
the current checkout was accepted. No scientific/security/launch qualification.

Unknown structured evidence remains unmet: source prose or a caller's success
flag cannot manufacture owner awareness, findings disposition, verified snippets
or a current emitted-door release check. Actual optional door captures use T06's
existing validator; they are not real-run cells. Status reports evidence, never
dispatches, signs, opens keys or promotes a fixture into acceptance.

CLI: `status [--json] [--revision <40-hex>] [--door-capture <public-reference>]
[--completion-evidence <public-reference>]`; `validate` and `write` accept one
prospective JSON cell on stdin and never print rejected values. Completion JSON
has schema `carbon.launchpad.completion-evidence.v1`, matching `source_revision`,
optional `key_blocks` and `findings` maps. A key-block entry requires reason
`OWNER_KEY_UNAVAILABLE` matching the selected cell plus `owner_acknowledgment`;
a finding entry requires disposition `FIXED` or `OWNER_ACCEPTED` and `proof`.
Each proof is exactly `{reference, sha256}` bound to an existing public source
containing that exact cell/finding identity. Owner references are decision
records. Reports expose the checked public proof basis and explicitly state
that declaration content is not independently authenticated. These declarations
are evidence metadata; none can authorize launch or security qualification.

## Exact manifest and plan

1. This ticket and `.agent/decisions/2026-10-15-LAUNCHPAD-T05-CELLS-MATRIX-01.md`.
2. New `scripts/dev/launchpad_acceptance/{cell.py,matrix.py,status.py,__main__.py}`.
3. New `tests/cpu/test_launchpad_acceptance_matrix.py`.

Record contract/decision first; implement data, validator/writer and status as
one coherent bounded change; add temporary-fixture negative controls; run static
format/lint/diff/hygiene checks. No T06/T04 existing path, shared fixture, CI
workflow, historical record, reserved owner record, R6 or ScoreLab changes.

Baseline: base has T06 reader only, no cell writer/matrix/status entry point;
no local application/test/import execution is authorized. Remote canonical CI
after T06 merges supplies behavioral validation, including default status,
all matrix families, F15/C10/C11, exact provenance/history/fail-closed behavior,
nested forbidden evidence, immutable writes, path/symlink refusal, and CLI
negative controls. Root owns review/merge; reviewer Platform2 or Root's peer.
Hub: SYSTEM/DEVELOPMENT-HUB; retired under current delivery policy, no edits.

Completion: one main-based seven-path PR, applicable exact-head checks successful,
concrete findings resolved, truthful queue report and direct Platform2/Root
handoff. Maturity earned is engineering implementation/tests only.
