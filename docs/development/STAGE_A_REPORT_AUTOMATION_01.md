# Stage A owner one-pager: development intake

Run after Stage A aggregate records land:

```sh
python -m scripts.dev.battery.stage_a_owner_report \
  --alignment-input stage-a-summary.json \
  --refusals docs/development/graphite/ladder-stages/stage-A/refused_capabilities.jsonl \
  --spend spend-summary.json \
  --markdown-out stage-a-owner.md \
  --json-out stage-a-owner.json
```

The alignment input is exactly #942's digest-bound
`carbon.battery.stage-a-alignment-input.v1` manifest. The script calls #942's
analyzer and keeps each cohort's score rule, pool, rebuild device and decision
panel distinct. Its JSON output contains the full #942 alignment analysis,
including descriptive bootstrap bands, v3 term contributions, divergent
members and the practice/exam table. The Markdown is a compact owner view.
Missing v3 inputs remain `V2_ONLY` or `UNMEASURED`, never zero.

The refused-capability intake is #953's post-run Stage A JSONL contract,
committed in `GRAPHITE_LADDER_STAGE_A_CHECKLIST.md` on main. It is built from
the executor's per-run extracts after runs; no real log exists yet. One line
has exactly these fields:

```json
{"stage":"A","level":2,"role":"Constructor","refusal_code":"not_rebuildable","requested":"method.example","count":2,"first_seen":"2026-10-10T12:00:00Z","last_seen":"2026-10-10T12:10:00Z","run_id":"toy-run-1"}
```

One row holds the count for a distinct `(level, role, refusal_code, requested,
run_id)`. The script refuses duplicate identities, non-UTC or reversed times,
unknown fields, and request payloads. It prints aggregate top codes, levels
and requested names, counted by events. These are investigation priorities,
not Level 5 designs or admission. No recipe, prompt, case ID or arbitrary
detail is accepted. The file digest binds the rows read, but cannot prove that
every refusal from the run extracts was logged; missing refusals are not
inferred. #953 leaves the extraction format TBD until a real run exists.

Spend input is a closed list of committed Stage A grants:

```json
{
  "schema": "carbon.graphite.stage-a-spend-summary.v1",
  "scope": "DEVELOPMENT_SUMMARY_ONLY",
  "grants": [{
    "grant_id": "GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR",
    "grant_sha256": "sha256:<digest of committed grant file>",
    "observed_spend_usd": "12.00",
    "source_sha256": "sha256:<digest of reconciliation source>",
    "state": "SETTLED"
  }]
}
```

`state` may be `SETTLED`, `ESTIMATED` or `UNRESOLVED`. An unresolved amount is
`null`, never zero. Cap values come from the digest-verified committed grant
files; a measured overrun is displayed. Source digests bind the producer's
assertions but do not authenticate them. Owner adoption and any Level 5
capability decision remain separate.
