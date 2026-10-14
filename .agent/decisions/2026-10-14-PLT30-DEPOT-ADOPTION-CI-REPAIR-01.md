# PLT30-D2: diagnose and refuse failed CI depot adoption before cold fallback

The finalized 1ab4 Julia job records a failed published-depot adoption taking
46.5 minutes, followed by a verified 6028-second cold build. Cancellation came
before the next service suite finished. WorkerFailure type alone loses the
actual adoption stage/code. The registry's current availability and the lost
failure cause are unproven; successful offline controls do not settle either.

KEEP exact immutable published lock, recipe/input digest, image label/arch,
recomputed tree hash, composition equality and precompiled-package checks;
all nine service suites, isolation and the existing 150-minute job cap.
REPAIR the operational adoption path, outside the depot's identity inputs:
closed phase/status/elapsed/error events; quiet progress within the existing
controller output cap; CI requires successful verified adoption, rather than
continuing into an unbudgeted cold build. Operator `build` and optional `adopt`
remain available explicitly. If the registered depot is unavailable, CI stops
as infrastructure failure; it neither serves a cached impostor nor passes.

The tree reader's prior wait timeout began after tar consumption. Apply that
existing 600-second deadline to streaming itself, reaping its local child and
removing the created never-started container on every result. Hash semantics
(paths/types/modes/links/bytes, sorted) stay identical. A hung-stream control
must discriminate. Published-adoption failures cannot replace a recorded cache;
successful recording still follows inspection, tree reading and binding checks.

Alternatives rejected: raising 150 minutes, dropping suites/verification,
changing image/Julia pins, blindly retrying the registry, or claiming progress
output was the actual lost cause. An output-cap fixture demonstrates a possible
bounded WorkerFailure path only; new diagnostics identify actual CI outcomes.

This is reversible operational CI infrastructure repair, not a new scientific,
security or live authority. Supersede by reverting the service requirement and
diagnostic/deadline changes after an explicitly tested replacement reuse path.
Primary map SYSTEM/AGENT-EXECUTION; Hub retired. Root owns actual acceptance and
merge; the builder performs no pull, publish, key access, spend or platform change.
