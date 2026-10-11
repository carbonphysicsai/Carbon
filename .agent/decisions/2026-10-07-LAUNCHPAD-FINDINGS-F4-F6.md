## 2026-10-07 — LAUNCHPAD-FINDINGS-F4-F6: refuse a Graphite launch without both ceilings at the door, check a pre-manifest resume against the launch's provider, and check Docker from the user manager

**Authority.** LAUNCHPAD-ACCEPT-01's acceptance run on a fresh machine,
2026-10-07, found three defects: LA-F4, LA-F5 and LA-F6
(`docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`).
The fixes below are engineering choices within that delegated authority. No
scientific value, threshold, budget, price, gate or tolerance changes. No
ceiling value is supplied or defaulted: the miner sets both. Nothing widens
for miners, and no existing closed code is renamed.

**Decisions.**

1. **LA-F4: one ceilings predicate, read by the doors and the plans.**
   - `carbon/challenge_registry/agent_plan.py` owns `AGENT_BUDGET_KEYS`,
     `finite_ceilings(budget)` and the closed code
     `graphite_ceilings_required`. Battery's campaign imports them rather
     than keeping its own copy, so the door and every Challenge's Graphite
     plan cannot drift.
   - `RunnerAdapter._graphite_choice` refuses a Graphite launch whose budget
     lacks either whole-number ceiling, `graphite_ceilings_required`, field
     `budget`. That method is shared by the replay gate (before the chain is
     read), admission (before the launch is recorded or queued) and the
     rebuild of a recorded launch. The MCP door and the browser's door both
     reach it through `operations.perform`. The refusal is an addition to
     `operations.REFUSAL_FIELDS` and `supervisor.NEXT_ACTIONS`.
   - The next step works for both places the code can appear: a synchronous
     launch refusal, and a campaign's `last_refusal`. It says to launch again
     with both ceilings, and that resuming does not help.
   - A plan that still meets such a budget raises `CeilingsRequired`, a
     `ValueError` with `code`. Existing `except ValueError` handling is
     unchanged, and the run's interruption now records the closed code.
   - The autonomous plan's own refusal is unchanged: that agent is retired
     for new launches (`autonomous_agent_replaced`).

2. **LA-F5: before a manifest exists, a resume checks the launch's provider.**
   - `runner.launch_provider(cfg, row)` reads the admitted launch's record
     (`launchpad_campaigns.launch_request`) with the same rule admission
     uses (`runner.launch_model`, now shared with `_launch_choice`). That is
     the provider the launch named; or the miner's setup choice for a model
     agent that named none; or None.
   - `_frozen_credential(cfg, root, row=None)` uses it only when no manifest
     exists and a record is given. Only the resume admission check in
     `_control` passes the record. That check only validates: the run then
     carries the launch out from its record (`_recorded_launch`), whose own
     selection carries its own key.
   - The miner-operation path (`_operate`) is deliberately not given the
     record. An operation's `prepare` on an unprepared campaign would
     otherwise receive the launch provider's key as `api_key_file` while
     freezing the pinned default selection.
   - It still fails closed: no record, an unreadable one, or one naming no
     provider keeps the pinned default's rule (`foreign_default_key`). A
     named provider with no configured key is refused by name and never
     substituted.

3. **LA-F6: with the service, the user manager itself must reach Docker.**
   - `scripts/install_miner.sh` checks this in step 1, before anything is
     synced, built or written, whenever the service is chosen (`--service`,
     or a unit from an earlier install) and the user manager answers. It
     runs `systemd-run --user --wait --quiet --collect --pipe <docker> info`.
   - A machine without the user manager is still refused at step 6, as
     before. A missing `systemd-run` with a working manager is refused by
     name.
   - On failure it stops with the fix and what that fix stops. On WSL:
     `wsl --terminate <distro>` from Windows, which stops everything in the
     distro. Elsewhere: `sudo systemctl restart user@<uid>.service`, which
     stops the user services, or logging out of every session.

**Not changed, and noted.** Other `prepare`-time ValueErrors were surveyed
for the same invisibility. Each was left alone:
- `research_share_too_small` is already typed, and checking it at the door
  needs the selection's per-call reservation, so it is not as cheap as this
  check.
- The Graphite block's shape errors are already refused at the door by
  `graphite_launch`'s bounds.
- `check_budget`'s priced-ceiling refusal is already checked at launch for a
  named or setup selection.
- Host and profile errors are bare ValueErrors, so their interruptions
  record code null. They are `accepted numerical host unavailable`, runtime
  or image parent differs, subnet context required, and registered miner
  differs. A launch request cannot check them, so typing them is a separate
  follow-up.
