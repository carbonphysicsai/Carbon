# Optional working plan

Use a plan when it helps finish complex work; do not create one merely because a
task touches multiple modules. Keep it in the existing ticket/PR unless a
separate evolving plan is actually useful. No separate plan commit or approval
stage is required.

A useful plan answers:

- What authorized behavior will work, and what obsolete path will be removed?
- Which existing code/callers can be kept, wrapped or repaired?
- What coherent implementation steps and meaningful checks establish that flow?
- What actual boundary or unresolved reserved value limits the change?

Update the plan when the approach materially changes. Record enduring decisions
once; do not duplicate a decision package or SHA inventory here. Completion uses
[the delivery policy](../.agent/DELIVERY_PROTOCOL.md) and current human/protected
conditions, not a second review/receipt lifecycle. Report what worked, what was
removed, actual tests and remaining limitations.
