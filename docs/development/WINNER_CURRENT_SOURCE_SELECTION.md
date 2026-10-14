# Current winner source selection

WEIGHTS-CURRENT-SOURCE-01 repairs an issue/resolve inconsistency. With no
current battery promotion, issue froze all-burn but resolve selected a last
historical eligible record and refused those same targets indefinitely.
Preview already used the current configured source. Unconfigured sources
also selected stale history despite the registered no-serving-validator burn
contract (OWNER-TESTNET-WEIGHTS-01, VALIDATOR14, policy membership note).

Issue, read-only resolve and preview now share current-source selection.
Absent source or an explicit source None means no current promotion; it does
not delete or invalidate history. A failing/malformed source is unavailable
and refuses with closed WINNER_SOURCE_UNAVAILABLE, never stale-history or
all-burn fallback. A present model selects its corresponding recorded
promotion and original clock, even if unrelated later ledger rows exist.

Only issue appends a new observed promotion. Preview may derive a tentative
record through existing decide and writes nothing. Read-only resolve refuses
an unrecorded or altered promotion; both frozen ledger identities and target
vectors must match, so equal numeric weights cannot hide promotion drift.
Time/halving changes, holder/runtime/policy/authorization changes and shared
integer/no-resend/reconcile checks remain controlling. The drift fixture now
changes the actual source rather than just appending unrelated history.

Per-epoch intent bytes and ledger history are never rewritten to force a
publication. A stale existing intent can remain refused until a new epoch;
terminal historical journal facts keep their original interpretation. No
automatic journal deletion, clock reset, standing renewal or rescore occurs.

The actual scheduled AX42 source was identified by the owner as
/var/lib/carbon-val/etc/testnet-sched.json; old v2 path diagnostics were not
the active-source evidence. Root owns exact reviewed release/host execution
and any next publication. This repair itself reads no host/private rows,
opens no wallet, signs no transaction and changes no economic or scientific
value. Canonical tests use public synthetic fixtures and scripted backend
counters; they do not constitute security or testnet-payment acceptance.
