# Scope record (tested, then removal by attack)

`scripts/dev/graphite_progress/survived.py` builds the Graphite scope record defined in
`SURVIVED_RECORD_DEFINITION_01` (operator share). An item enters scope once it is TESTED (scored and rebuild-proven at
its level); attacks then only subtract. Development evidence only: every `claims` field is false, and nothing here says
secure, qualified or accepted. No balance, account id or spend figure is ever read into a record.

Files:

- `item_families.json`: which attack families defend each item, and which progress-ledger lines tested it. An item with
  no scored ledger line is listed under `not_entered` (today: `l4.graph`).
- `SURVIVED_RECORD_v1.json`: the historical, digest-pinned snapshot from the original producer (no timestamps).
  It is preserved byte-for-byte here; this repair does not refresh private evidence or certify its current status.

## Prospective lifecycle repair (2026-10-15)

Working contract for GR1293-01 through GR1293-04: KEEP the existing read-only reader and append-only output; REPAIR
finding lifecycle interpretation only. New records identify `carbon.graphite.finding-lifecycle.v2`; earlier snapshots
are historical evidence and cannot authorize a removal under the repaired producer. No item/family map, scope-entry
gate, grant, qualification or human removal decision changes. The Hub is retired under OWNER-DX-03.

- Fold controller states in sequence order per root and finding. Only the latest REPAIRED state closes a finding;
  a later RECURRED reopens it, even when a backfill still names an old fix and reattack. Retain repair history.
- Refuse generation before any output append when registered finding evidence is absent, malformed, outside the
  controller or mismatched with its registered SHA-256. An unavailable family cannot disappear from the record.
- A named reattack string remains provenance only. Closure from backfill requires a nonempty `finding_fixes` reference
  and a `reattack` object with matching `fix_ref`, `finding_evidence_digest`, `family`, `report_ref` and `report_digest`.
  The bound report's family must meet the existing clean HELD/k/DONE criteria. This records the operator's post-fix
  linkage, not independent verification of the fix, execution chronology or security adequacy.
- An ORACLE_GAP stays below ATTACKED_HELD without that fix and clean reattack. A resolved REAL_ESCAPE cannot propose
  removal; a fix awaiting reattack cannot be called a recurrence. ESCAPE_RECURS_AFTER_FIX requires an actual RECURRED
  controller row after a recorded repair, with readable, digest-matching evidence for the same family.

Fixture controls cover repair/recurrence ordering, root isolation, evidence loss/tampering, stale or unrelated reattack
links, and accurate removal reasons. OPERATOR forbids local execution; remote canonical CI supplies runtime evidence.

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

## Historical snapshot gaps (2026-10-13)

- Finding `attack-failing-trigger-2a84f968e6ffc6e8-0` (L0, `staged_bytes`) has no triage record; it holds `l0` open.
- Finding `9b718c64...` (recorded L3, derived L0) is triaged ORACLE_GAP in `attack-hunt-2026-10-12.json` (merged in #1292); the snapshot was regenerated after it merged.
- At snapshot generation, no repair attestation existed in the inspected controllers (`finding_states` was empty).
  This is historical source evidence, not a current controller inventory. Future closure uses the lifecycle contract above.
- Level labels are descriptive at the item level; the ledger records sessions, not which item a scored recipe exercised.
