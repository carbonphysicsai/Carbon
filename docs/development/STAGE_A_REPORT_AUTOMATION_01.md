# Stage A owner one-pager: development intake

Run after Stage A aggregate records land:

```sh
python -m scripts.dev.battery.stage_a_owner_report \
  --alignment-input stage-a-summary.json \
  --refusals refused-capabilities-summary.json \
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

The Graphite Testing Manager's native refused-capability log format is not yet
committed on main. Until its format is supplied, this script accepts a strict
**interim aggregate operator summary**, not a claim to parse its raw log:

```json
{
  "schema": "carbon.graphite.refused-capability-summary.v1",
  "scope": "DEVELOPMENT_SUMMARY_ONLY",
  "source_sha256": "sha256:<digest of source log>",
  "complete": true,
  "levels_covered": [0, 1, 2, 3, 4],
  "records": [
    {"capability_id": "method.example", "level": 2, "refusal_code": "not_rebuildable"}
  ]
}
```

One record means one refused capability occurrence. The producer must include
every refusal in each covered level; `complete` is its assertion, which this
script cannot independently prove. The output ranks `(capability, level,
code)` by event count as **Level 5 investigation candidates**, not Level 5
admission or an accepted expansion. The input accepts no recipes, prompts,
case IDs or arbitrary details. When the Manager's native schema lands, its
owner should provide a read-only projection into this summary or update this
adapter with a versioned native-schema reader.

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
