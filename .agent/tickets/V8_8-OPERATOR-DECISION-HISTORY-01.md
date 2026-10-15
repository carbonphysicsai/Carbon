# V8_8-OPERATOR-DECISION-HISTORY-01

Root assigns this bounded v8.8 packaging repair on 2026-10-14 under Ryan's
active sprint. Base: `5a0c7057dadba068a1392c76555ecfaecaf62893`.
Current OWNER-DX-03 and continuous queue delivery apply; Hub retired.

## Contract and scope

KEEP the existing exposure decision requirement, matching-heading check,
tracked-Git-only public packaging, immutable source/image identity and historical
bundle interpretation. REPAIR the bundle's omission of `.agent/DECISIONS.md`:
`intake.load_config` calls `require_exposure`, which reads that history and the
per-decision files for exposed configurations. The operator delegate supplies
the materialized bundle as repository. Actual published7c3e inventory lacks the
history; a matching per-decision record cannot prevent the missing-file error.

Allowlist only that tracked public history file and require it for prospective
materialization. Do not broaden `.agent/`, skip missing files, alter intake
semantics, change exposure authority, or invent an approval. Historical `verify`
must continue interpreting the manifest's original file set.

Expected paths: this ticket, its decision, `carbon/validator_setup/bundle.py`,
and `tests/cpu/test_validator_setup_bundle.py`. One branch/PR on main, no overlap
with the open PRs observed at start. No broader docs or Hub work.

## Plan, validation and completion

1. Pin the working contract and decision; then repair the exact file selection.
2. Exercise actual intake exposure validation against materialized Git fixtures:
   legacy/per-decision matching headings pass; missing per-decision file and
   mismatched heading still refuse. Missing required history refuses packaging.
3. Keep exclusion and historical-manifest tests. Run the applicable remote CI,
   focused bundle/setup and exposure regressions, pinned style and delivery
   hygiene. Local pytest/canonical/WSL/Docker application runs are prohibited in
   Root's current OPERATOR window; no unexecuted red/green is claimed.

Conditional engineering completion: regression and applicable exact-head CI
pass and Root merges the bounded change. Root owns any local finite validation,
new matched bundle/image, publication, host acceptance and healthy rollback.
Published7c3e/source5a0 remains historical and cannot be relabelled. Rebuilding
the affected artifact does not require repeating unrelated scientific evidence.
This repair confers no exposure, security, scientific, signing or launch authority.
