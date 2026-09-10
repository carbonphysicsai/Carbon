# C-EA0 evidence capture contract evidence

**Status:** selected contract candidate; exact documentation contract and
contract-case diagnostics pass; applicable automated acceptance and normal merge
pending.

**Starting main:** `5d3c6cbca14bf3422960d9a7fe3ce7a1bcfa2ed4`
(PR #130).

**Ticket:** `.agent/tickets/C-EA0_evidence_capture_contract.md`.

**Primary Hub map_ref:** `WAVE-C/C-EA0`.

**Decision:** `C-EA0-D1` under `OWNER-EVIDENCE-RESEARCH-01` and
`OWNER-C1-C2-BURGERS-01`.

## Specified boundary

The candidate ratifies version 1 of the evidence-capture documentation contract
and machine-checkable case matrix. It defines immutable per-attempt accounting,
five independent status axes, conditional artifact requirements, explicit
missingness, dependence and unknown semantics, custody-zone boundaries,
retention classes, named-use assessments and positive durability-acknowledgement
conditions.

The contract preserves the source owners for submission, execution, scientific
result, receipt and finalization. Missing required evidence, an unavailable key,
a withdrawn artifact, or any absent approved policy blocks acknowledgement and
required finalization without becoming a candidate physics failure. Retry and
re-execution attempts link to new entries and never overwrite their predecessor.

## Contract-case diagnostics

The C-EA0 A12 invariant suite loads
`Design_Specs/evidence_capture_contract_v1.json` and verifies the exact five
closed axes, all six execution dispositions, fail-closed missing/withdrawn/key
cases, unknown selection/exposure, shared-case and ancestry dependence, positive
acknowledgement predicates, the complete reserved-input register and the
non-universal losslessness boundary.

Focused native Python 3.11.11 result: 5 passed. This is tested documentation,
not archive runtime or durability evidence. Applicable CI acceptance remains
pending for the final candidate.

## Human-reserved inputs and handoff

Durability/correlated-failure coverage, required artifacts, retention/deletion/
legal hold, rights and named use, custody/access/encryption/keys, provider/region/
replication topology, capacity/backpressure, recovery objectives/restore
acceptance and security qualification all remain `HUMAN_INPUT`.

C-EA1 may implement only after C-EA0 acceptance and normal merge, selection, and
approval of its required inputs. No database, object store, key manager, region,
retention duration, archive acknowledgement, scientific qualification, public
network, G2, testnet eligibility, production or LIVE authority is created.
