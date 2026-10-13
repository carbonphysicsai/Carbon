# Scope record (tested, then removal by attack)

`scripts/dev/graphite_progress/survived.py` builds the Graphite scope record defined in
`SURVIVED_RECORD_DEFINITION_01` (operator share). An item enters scope once it is TESTED (scored and rebuild-proven at
its level); attacks then only subtract. Development evidence only: every `claims` field is false, and nothing here says
secure, qualified or accepted. No balance, account id or spend figure is ever read into a record.

Files:

- `item_families.json`: which attack families defend each item, and which progress-ledger lines tested it. An item with
  no scored ledger line is listed under `not_entered` (today: `l4.graph`).
- `SURVIVED_RECORD_v1.json`: the deterministic, digest-pinned snapshot for the register (no timestamps). Regenerate it
  whenever a source changes; the `sources` block pins the digest of every input.

Statuses: `NOT_ATTACKED`, `TESTED_ONLY`, `ATTACKED_OPEN_FINDING`, `ATTACKED_HELD`. An untriaged finding or an unfixed
REAL_ESCAPE is open. ORACLE_GAP and FALSE_POSITIVE never open an item and never remove it; an ORACLE_GAP keeps the
item at `TESTED_ONLY` until the oracle is fixed and a clean re-attack is named. `ATTACKED_HELD` needs every mapped
family held at k with a DONE stop. A finding's level is derived from its construction (`derived_level`), never taken
from the session that produced it; a mismatch is kept as `recorded_level` and flagged.

Run (read-only on the attacker roots; appends only to the jsonl):

    python -m scripts.dev.graphite_progress.survived generate \
      --items docs/development/graphite/survived/item_families.json \
      --ledger <progress.jsonl> --backfill docs/development/graphite/progress/backfill \
      --attacker-store <root>/attacker [--attacker-store ...] \
      --out-jsonl <beside progress.jsonl>/survived-record.jsonl \
      --snapshot-out docs/development/graphite/survived/SURVIVED_RECORD_v1.json

`survived-record.jsonl` lives outside the repository; a rerun on unchanged evidence appends nothing, changed evidence
appends a record that supersedes the item's last one. A removal is only ever PROPOSED (`propose_removal`, from a
triaged REAL_ESCAPE in one step); a person decides it.

## Known reds

- **R5 for the attacker role.** `attacker_budget` reserves six verify pods while Carbon's verify-pod rebuild is an open
  seam (`carbon_verify_pod_rebuild`, NOT_RUN) and the live attacker launches no pod. It is expected to pass once the
  rebuild lands; until then it is a known red, not a defect to fix in the budget. The snapshot carries this entry.

## Gaps today

- Finding `attack-failing-trigger-2a84f968e6ffc6e8-0` (L0, `staged_bytes`) has no triage record; it holds `l0` open.
- Finding `9b718c64...` (recorded L3, derived L0) is triaged ORACLE_GAP in `attack-hunt-2026-10-12.json` (merged in #1292); the snapshot was regenerated after it merged.
- No repair attestation exists in any controller (`finding_states` is empty), so closing a finding rests on a recorded
  fix plus a named re-attack.
- Level labels are descriptive at the item level; the ledger records sessions, not which item a scored recipe exercised.
