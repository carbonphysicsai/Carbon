## 2026-10-15 — BATTERY-PROFILE-GUIDANCE-01: preserve the accepted private task

Ticket: BATTERY-PROFILE-GUIDANCE-01. Status: IMPLEMENTED_WORKING_DECISION.
Authority: Root bounded assignment; C-MLP-02-D6/issue #223; current Constitution,
invariants and OWNER-DX-03 source-only delivery rules. IMPLEMENTATION_LAG.

Battery prepare silently discards a profile field already validated, reviewed,
persisted before dispatch and supplied by Launchpad. Reuse research_guidance
bind/verify and the research loop's existing observation/user-role/effective-input
path. Freeze the task in a new Battery manifest and verify persisted/supplied
identity on resume before external operations. Add its private context and the
existing lower-priority trust label to the public-discovery observation. The
existing driver sends that observation independently to the Constructor; do not
infer consumption from profile storage or Planner visibility. Existing live
owner Conversation and miner-guidance v2 delivery remain separate and unchanged.

Alternatives rejected: editing trusted role prompts; translating frozen guidance
into a fabricated live-message journal entry; new launch field/runner/prompt store;
silently ignoring an accepted field; changing old manifests. The small additive
repair is reversible by removing the optional field plumbing; old unguided runs
retain their bytes and semantics. No evaluator/score/hidden context reads or new
execution permission. No human-reserved value is selected or unresolved.

Affected files: Battery campaign preparation/observation, dedicated regression,
this decision and ticket. Product independently reviews exact diff and real
Constructor-input evidence; Root alone owns runtime/canonical validation/merge.
If a lead disagrees, remove this prospective plumbing and reject the unsupported
field explicitly at its existing admission seam; never reinterpret frozen runs.
