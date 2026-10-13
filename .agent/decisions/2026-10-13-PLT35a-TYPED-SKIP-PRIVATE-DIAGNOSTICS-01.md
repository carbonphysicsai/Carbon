# PLT35a-TYPED-SKIP-PRIVATE-DIAGNOSTICS-01

Ticket: PLT-35a-VALIDATOR-PASS-SURVIVES-INBOX-ORPHANS-01.
Working reversible engineering decision, notified to Root Test Lead/Validator.

KEEP the writer scope, inbox state, submission identity, scoring/retry semantics
and broad pass infrastructure handler. REPAIR only unknown_submission lookup
in the admitted loop, with an orphaned counter and fixed operator event/code.
Other StateError codes and process failures still propagate.

The handoff's raw message/args request conflicts with intake's type/count-only
privacy contract and private-sentinel regressions: DOCUMENTATION_LAG in logging
scope, resolved by Validator direction to use closed reasons/codes and counts.
The pass handler emits known typed StateError codes and a closed fingerprint-key
reason where applicable, never arbitrary strings, detail, paths or identifiers.
An arbitrary exception's spoofed .code is not trusted. Unknown codes stay
exception_details_withheld, with only type and argument count.

Alternatives rejected: catch every StateError; delete/mark orphaned inbox rows;
re-register submissions or infer loss/recovery; raw str/repr/traceback disclosure;
changing private-sentinel tests to permit leaks. All are wider than this ticket.

Locations: carbon/battery/intake.py, carbon/battery/operate.py,
tests/cpu/test_validator_inbox_orphans.py. Supersede these exact changes if the
Validator changes the working engineering recommendation. No DB/schema migration.
Host outage/recovery/deployment authority and real service acceptance remain
reserved. Test fixtures and canonical CI can earn engineering evidence only.
