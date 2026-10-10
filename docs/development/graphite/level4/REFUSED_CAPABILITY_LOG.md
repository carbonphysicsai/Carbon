# Level 4 refused-capability log

**Purpose.** This log is the evidence for which Level 5 ops Carbon builds
first (OWNER-LEVEL5-INTERNAL-LANE-01;
`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md` §12.1).

**What goes in.** Every capability Graphite asks for during Level 4 stages
A to C that Level 4 refuses. One row per request:
- a missing op;
- a cap reached;
- a slot or interface that is not admitted;
- a library that cannot be lowered.

**How rows are added.**
- Append only. Never edit or remove a row.
- A later decision about a row becomes a new row that points back to it.

**Columns.**
- **Date.** When the request was made.
- **Stage.** A, B or C.
- **Challenge.**
- **Requested.** The capability, in the requester's words.
- **Refused by.** The gate and its typed code, such as G4
  `op_not_allowed:<op>` or `cap_exceeded:<cap>`.
- **Evidence.** A pointer to the run, record or finding.
- **Class.** One of `math`, `solver`, `kernel` or `library` (§12.1), or
  `unclassified`.
- **Gain claimed.** What the requester expects it to buy, unverified.

| Date | Stage | Challenge | Requested | Refused by | Evidence | Class | Gain claimed |
|---|---|---|---|---|---|---|---|
