# C1 dependency-contract materialization evidence

**Decision:** `OWNER-C1-CONTRACTS-01`
**Primary Hub map_ref:** `WAVE-C`
**Scope:** documentation/governance checkpoint only

The checkpoint starts from merged C-EA1 main
`0e0714c8260ca482a0ba2b743b2eaefd50508da1`, tree
`65eee3316e4b018a95d72a81d5530455c898d460`. It materializes C-03, C-08 and
C-09 and records the complete current C1-to-C-W1 dependency graph without
selecting or implementing a runtime ticket.

Authority resolution and every node's status, dependencies and blockers are in
`.agent/plans/C1_DEPENDENCY_GRAPH.md`. Machine-checkable invariants require all
three new tickets to remain `future_reserved`, unselected and unstarted; require
both Wave registers and the Hub to expose no active or next-selected ticket;
preserve C-02's complete external JAX blocker; prevent C-EA1's synthetic
acknowledgement from satisfying C-EA2/C-09/C-W1; and preserve G2's exact
standard-profile localnet ceiling.

No JAX source/interface, scientific value, reference, measurement, archive
retention/durability/custody/topology/recovery/security input, public-network
identity, fee/economic policy or production qualification was supplied or
invented. No public transaction or runtime implementation occurred.
