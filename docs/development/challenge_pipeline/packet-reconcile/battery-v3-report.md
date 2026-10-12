# battery-v3 buyer-field reconciliation

Reviewed clause bindings only: numeric equality or exact phrase-to-token mappings. Not empirical credibility, semantic entailment, approval, qualification or readiness. Unbound fields need reviewed bindings; do not guess values.

Coverage: {'required_buyer_fields': 13, 'bound_buyer_fields': 4, 'checks_examined': 7, 'consistent': 7}

| Field / check | State | Packet value | Evidence value(s) |
|---|---|---|---|
| hard_limits / charging-temperature | CONSISTENT | 45 | 45 |
| hard_limits / plating | CONSISTENT | 0 | 0 |
| hard_limits / voltage | CONSISTENT | 4.2 | 4.2 |
| hard_limits / retention | CONSISTENT | 0.99 | 0.99 |
| objective / time-is-objective | CONSISTENT | MINIMIZE_SESSION_TIME | MINIMIZE_SESSION_TIME |
| outputs / discharge-scope | CONSISTENT | DISCHARGE_DIAGNOSTIC | DISCHARGE_DIAGNOSTIC |
| w / buyer-mix | CONSISTENT | BUYER_MIX | BUYER_MIX |

Unbound buyer fields: P, Q, buyer, conditions, decision, exclusions, geometry, value, wrong_decision

All source pointers, digests and selectors are retained in JSON. No packet value was changed.
