## LAUNCHPAD-T06-TRUTHFUL-STATUS-01 — acceptance is named evidence

Under Ryan's D4 and the full T06 handoff, attach acceptance metadata separately
from scientific payloads and execution permission. A TESTED label always names
the exact PASS cell's revision and public record; it means that named evidence
only, never implicit acceptance of a newer release. Latest FAIL/BLOCKED or
unusable evidence remains UNTESTED. Defaults apply to unknown/new options too.

Use one read-only public-cell reader/projection for browser and MCP, with a
closed MCP status enum. Keep raw evidence contents private to their existing
public files; project only allowlisted provenance. Existing availability,
registration, signer, replay, reconstruction and submission gates remain owned
by their existing modules. The rehearsal check validates truthful labels before
the existing build sequence; it is not scientific or deployment acceptance.

D5 level deferral and D1 bootstrap-security hold remain explicit UNTESTED /
BLOCKED metadata, separate from unrelated launch readiness. The T07 lane owns
the owner record and historical backfill. No fixture pass substitutes for them.
