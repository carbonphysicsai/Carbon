## 2026-10-08 — OWNER-L4-VALUES-01: the Level 4 values sheet approved as proposed (development and testnet)

**Authority.** The owner, 2026-10-08, verbatim, directly in the Level 4
engineer session: "approve §1–§5 as proposed". It answers the approval form
of `docs/development/graphite/level4/LEVEL4_VALUES_PROPOSAL.md` (#807), the
team-proposed sheet the Test Lead asked for. Recorded by the Level 4
engineer session.

**Scope.** Development and testnet only, as the sheet states. This record
sets values; it accepts no security surface. G5 on mainnet stays
fail-closed under OWNER-L4-G5-COMPILE-ISOLATION-01, and a mainnet security
acceptance for G5 is a separate decision that is not recorded here. Level 4
is still never served to miners: opening it is a locked, released contract
that the owners choose.

**Approved values** (the sheet's recommendations, unchanged):

| Gate | Value | In code |
|---|---|---|
| G0 | manifest 16 KiB · document 1 MiB · submission 4 MiB | `carbon/level4/intake.py` `BOUNDS` |
| G3 | 10 s CPU · 512 MiB address space | `intake.BOUNDS` |
| G4 | document 1 MiB · nodes executed 4,096 · call depth 16 · constants 16 KiB · largest intermediate 256 MiB | `carbon/level4/allowlist.py` `CAPS` |
| G5 | deadline 120 s | `carbon/level4/compile.py` `DEADLINE_SECONDS` |
| G5 | compile memory 8 GiB for the G5 lane | **approved, not yet built** (below) |
| Budget | one budget, no separate Level 4 share; G5's compile counts as setup within the 300 s rebuild target | no code (below) |

**Not yet in code, and why.**
- **8 GiB G5 lane.** The C-03 worker's memory is one global constant,
  `MEMORY_BYTES` (4 GiB, no swap) in `carbon/reconstruction/worker/model.py`,
  enforced and re-checked by the sandbox runtime
  (`worker/docker_runtime.py`). A per-lane limit changes that sandbox code,
  a security-sensitive surface that needs its own review. Until it lands,
  the 4 GiB lane binds G5, and the approved 256 MiB intermediate cap keeps
  every admitted graph within it (the sheet's §4 finding).
- **Budget (§5).** No code changes now. The precondition stands: the
  TRAINING-BUDGET-01 cost calculator must cost development recipes (finding
  M1, accepted as a blocker, owner Test Engineer) before any budget check
  binds Level 4. The #727 admission check stays off.

**Versioned consequence.** Battery's registered Level 4 policy embeds the
caps, so the approved caps are a new variant version, `battery-l4-graph-v2`.
v1 stays pinned in the registry as history; current moves to v2. v2 also
carries G5's accepted status in place of v1's "fail-closed until D3"
(OWNER-L4-G5-COMPILE-ISOLATION-01's documentation lag, closed here).

**Unchanged.**
- Development rebuilds still stop on `level4_submission_documents_not_staged`
  until the staging contract (#807) is wired.
- The inference cost rule stays `HUMAN_INPUT`.
- The validator's transport bound is the validator's.
