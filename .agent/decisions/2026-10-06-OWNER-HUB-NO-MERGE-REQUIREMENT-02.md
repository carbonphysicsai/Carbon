## 2026-10-06 — OWNER-HUB-NO-MERGE-REQUIREMENT-02: the Hub's own tools stop gating merges

**Authority.** The owner, 2026-10-06, to the PR Head session:

> I really want to remove all hub requirements for merging. We don't use it
> anymore

**Amends** OWNER-WORKFLOW-SPEED-01 (2026-10-03) by finishing it. That record
retired the Development Hub as a merge requirement, and `check_merge_gate.py`
already requires no Hub job: the `Development Hub validation` job runs only
when the protected base's gate asks for it, which it no longer does.

**What still gated a merge.** `scripts/dev/select_cpu_profile.py` listed five
Hub tool scripts in `TOOLING_TESTS`:

    docs/development/carbon_hub/tools/validate_hub.py
    docs/development/carbon_hub/tools/test_validator.py
    docs/development/carbon_hub/tools/test_newcomer.py
    docs/development/carbon_hub/tools/test_routes.js
    docs/development/carbon_hub/tools/browser_smoke_test.py

Those run inside the canonical shards, and the canonical shards do gate the
protected `Merge gate`. So a Hub tool could fail a merge although the Hub was
retired. From 2026-10-06 that contradiction is gone: no Hub tool runs in the
tooling suite, and the Hub gates no merge.

**Evidence this was costing merges.** The Hub browser smoke test began failing
on the GitHub hosted runner on 2026-10-06 (`Browser did not expose a DevTools
port within 20.0s`, with `dbus/bus.cc:405 Failed to connect to the bus`). It
failed carbonphysicsai/Carbon#607 three times, #667 twice and #628 once,
about 17 minutes an attempt, each time failing `Merge gate`. No Carbon
behaviour was involved.

**What this record does not do.**
- The Hub's files stay frozen in place. Nothing is deleted.
- The Hub tools still run by hand and in the `Development Hub` workflow on
  `workflow_dispatch`; anyone working on the Hub can still check it.
- It grants nothing about scientific, security or economic authority.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
