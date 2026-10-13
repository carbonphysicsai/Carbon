# PLT-35a VALIDATOR-PASS-SURVIVES-INBOX-ORPHANS-01

Owner-created queue item, reassigned by Test Lead to Packets on 2026-10-13.
Starting main: 29fa548c45ad7fe7cf71d871c0c1bddc400497e8.
Reviewer: Carbon Validator via Root Test Lead. DEVELOPMENT engineering only.

## Contract

REPAIR the admitted-inbox processing loop in carbon/battery/intake.py: catch
only pool_store.StateError with code unknown_submission from outcome lookup.
Count/log the skip without an identifier; keep processing later known rows and
run_pending. Keep durable inbox entries unchanged for Validator recovery policy.
Do not swallow process errors, other StateError codes or infrastructure failures.

REPAIR operate.py pass_failed diagnostics with allow-listed typed codes and
argument counts. The literal request for raw message/args is DOCUMENTATION_LAG:
existing privacy authority/tests forbid disclosing paths, cases, recipe material
and arbitrary exception content. No raw args, messages, repr or traceback added.

## Tests and acceptance

Plant a synthetic orphan before/between known rows and prove the pass advances,
run_pending executes, the skip is operator-visible/counted, and inbox state stays
unchanged. Assert non-orphan state/process/infrastructure failures propagate to
the existing retried pass handler. Use private-content and spoofed-code controls
for logging. No real submissions, keys, chain, protected bank or host accessed.

Native isolated tests mock the writer/score-availability boundary; they do not
test real file locking or service deployment. Canonical acceptance is required
on the ready exact head. Root owns engineering merge; host deploy/acceptance and
orphan recovery remain Validator/Claude-side. One PR against main, no stacking.

The outage chronology is attributed handoff evidence, not independently checked
on the AX42. No repaired-live-service or resumed-scoring claim is earned here.
Hub retired. No owner scientific/economic value or recovery decision invented.
