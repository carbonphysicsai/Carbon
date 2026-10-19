# Trusted child interpreters preserve exact candidate source

Start from the actual R7 runtime source
8e986717b42850204d390b44c70833f5c1256332 on the isolated
`codex/cr04-retention-repair-01` branch. Platform owns the source change; Product
owns the finite VM, originals, admission and cleanup. The separate physical-kit
candidate is not included. No original R7 model or task is rerun by this change.

Original CR05 stderr identifies `LiveChecks.revision` source acceptance refusal;
its nested reason was suppressed. Original CR04 normal retain returned only
`direct_receiver_unavailable`; the original-context observer did not run before
VM deletion. Both original causal diagnoses remain incomplete. Plain R7 source
reuse checks omit the ignored-runtime scan and private candidate-pin validation
that the maintained exact-source guard correctly performs. Do not weaken that
guard, rebind stale state, or call an invented-file fixture proof of R7's cause.

A real-process regression independently proves a concrete defect: host compile,
deadline-watchdog and liveness-reaper launchers start Python without `-B`.
A parent interpreter's `-B` does not propagate. The reaper environment scrub also
deliberately drops `PYTHONDONTWRITEBYTECODE`. Running each actual launcher against
a tracked import-only fixture module creates ignored bytecode: ordinary Git
status stays clean while the real candidate verifier refuses the second case.
Before the repair, these three real-child regressions fail. Add an explicit
`-B` to each child command. All four focused tests then pass, including continued
refusal of a deliberately introduced ignored runtime file. No Docker/model is
used by these tests; subprocess ownership and cleanup are bounded.

KEEP environment scrubbing, subprocess isolation, deadlines, reaper ownership,
accepted-source/HEAD/tree/archive checks and public error disclosure unchanged.
The source fix prevents future cache creation; it neither deletes existing
ignored files nor authorizes their acceptance. A pinned old checkout with drift
must be handled by an explicitly scoped, stopped-child operational recovery or a
new truthful source/image candidate, never image relabelling or blanket cleanup.

Native results are diagnostics. Linux/canonical process and profile/restarted
retention checks, exact source/image VM verification and normal bank retention
remain required evidence. Existing real `serve` restart coverage includes
`test_real_loopback_bootstrap_stages_and_admits_same_owner_without_model_dispatch`
(including one-shot reopen/refusal); it is not a successful retained-model bank
proof. Original CR04 byte preservation is not semantic bank acknowledgement.
This patch earns no model, score, reproducibility, scientific or LIVE claim.
The Hub stays frozen. Any future actual failure must retain sanitized original
source exception frames before cleanup, within the owned finite deadline.
