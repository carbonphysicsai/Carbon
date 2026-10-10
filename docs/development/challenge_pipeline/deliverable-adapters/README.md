# Motor, cooling-cell and f02 development dossier adapters

DELIVERABLE-ADAPTERS-01 extends #966's source reader and renderer, not its
qualification framework. One command per source selection:

```text
python -m scripts.dev.customer_deliverable motor --ref HEAD --output-dir <fresh-motor-directory>
python -m scripts.dev.customer_deliverable cooling-cell --ref HEAD --output-dir <fresh-cooling-directory>
python -m scripts.dev.customer_deliverable f02 --ref HEAD --output-dir <fresh-f02-directory>
```

Use `--standard asme-vv10` for the other rendering profile. `HEAD` resolves to
an exact committed evidence identity; local uncommitted evidence cannot enter
that identity. See [the generator guide](../../../../Business/research/deliverable-generator/README.md)
for historical framework pins and the trusted public-export route. Output
directories must be new. The command reads only individually registered public
documents/aggregate records, not raw cases, hidden banks, solver outputs by
directory discovery, private receipts or AX42.

## What the adapters actually demonstrate

| Selection | Current specification | Recorded evidence and deliberately retained gaps |
| --- | --- | --- |
| motor | Precision robot-joint v2 packet and strongest cheap baseline | Public legacy runtime-readiness states and counted-study scope remain historical. The old #917 aggregate reports HOLD_MISSING_GEOMETRY_AND_FULL_SIGNED_CURVES, UNRESOLVED_NO_MATCHED_CARBON_ARM and 0/20 resolved lookup questions; none qualifies the new packet or proves cheap-method generalization. |
| cooling-cell | Cell-only v3 packet, case-plane limit and cheap-baseline specification | Final buyer lid/inlet/map settings still await owner selection. The old counted CFD study is historical, not validation of those unselected settings. No full cold-plate scope or newly measured V4 result is claimed. |
| f02 | Burst-thermal packet, strongest cheap baseline and proposed round-2 law | Feasibility NOT_DEMONSTRATED, proposed action registry HUMAN_INPUT, bank cost UNMEASURED. The law's 24 specified contexts are not 24 acquired cases. |

JSON extraction is a closed allow-list of scalar pointers with exact expected
schema/family, finite number or bounded state checks. Missing/malformed,
wrong-family, nonfinite or unavailable values become extraction gaps, not
zeros. Unregistered fields never enter the dossier. Exact point reproductions
are SOURCED, not confidence intervals or acceptance criteria. Source ledgers
retain each file's evidence role, commit, Git blob, SHA-256 and immutable link.

As in battery, only **D08 provenance and D11 audit trail** are partially filled.
D01–D07 and D09–D10 still need accepted evidence or human judgment. This adapter
does not automatically select P/Q/w, summarize limits as accepted requirements,
certify scientific independence, decide customer rights or fill a buyer-ready
product record. The standards indexes are topic mappings, not compliance.
Battery-specific NASA fact mappings are not copied to these families: missing
factor evidence is GAP. No source selection activates a runtime Challenge.

## Committed public-source samples

The [motor](generated/motor/sample.md),
[cooling-cell](generated/cooling-cell/sample.md) and
[f02](generated/f02/sample.md) samples use evidence/framework commit
`65ef88660fe02018c26f54d14655fe7b66354aa8` and the reviewed adapter policy in this
ticket. Each directory has the filled JSON, copied framework schema and
generation manifest with individual source identities and fact locators. All
registered sources and extraction anchors were present in this snapshot;
**that is extraction coverage, not scientific completeness**. Every sample is
DEVELOPMENT_SAMPLE, eligible tier UNESTABLISHED, qualification record null.
Generator timing is not model inference or a customer savings measurement.

Focused tests exercise both profiles for all three source selections, adverse
and missing evidence, public projection, schema/family/type mismatches, and the
real pinned public snapshot. Native diagnostics are not canonical acceptance;
GitHub exact-head CI supplies that gate. No physical model is rebuilt or solved.

Data Collection's future accepted public aggregate records need a prospective
policy/pointer update with the new source identity. Do not overwrite historical
samples or silently rescore old dossiers. Accepted requirements, credible
reference findings, completed manual sections and rights remain separate work.
