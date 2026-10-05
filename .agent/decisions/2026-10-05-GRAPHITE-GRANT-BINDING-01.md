## 2026-10-05 — GRAPHITE-GRANT-BINDING-01: per-Challenge Graphite grants

**Authority.** OWNER-GRAPHITE-TEST-WAVE-05 §2
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-TEST-WAVE-05.md`,
carbonphysicsai/Carbon#593). The owner approved a phase-4 Attacker grant for
cooling ("approve"), with amounts identical to GRAPHITE-GRANT-PHASE4, as a new
file that the runner accepts only when it is the committed blob on main for
the Challenge named by `--challenge`. These are engineering decisions inside
that approval. No amount, price, threshold, scoring or contract is chosen
here; every grant value is the owner's.

**Files:**
- `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4-COOLING.json`;
- `docs/development/graphite/grants/README.md` (a new section);
- `carbon/agent_campaign/graphite/phase4.py` (the grant functions and the CLI
  only);
- `carbon/agent_campaign/graphite/phase4_prelive.py` (the grant check and the
  report);
- `tests/cpu/test_graphite_phase4_grant.py`, `tests/cpu/test_graphite_phase4.py`,
  `tests/cpu/test_graphite_phase4_prelive.py`;
- `carbon/challenge_pipeline/lessons/2026-10-05-phase4-cooling-grant.json`.

### GRANT-BINDING-D1 — The Challenge binding lives in the runner

The grant format (`carbon.agent-campaign.spending-grant.v1`) requires an exact
field set and has no Challenge field. Adding one would change every grant and
the shared validator, so the binding is a runner registry instead:
`phase4.PHASE4_GRANTS` maps each Challenge to its `Phase4Grant` (Challenge,
grant id, grant file).
- `battery-fastcharge-ageing-development-v1` → GRAPHITE-GRANT-PHASE4.
- `chip-cold-plate` → GRAPHITE-GRANT-PHASE4-COOLING.
- No motor entry. Motor's grant is proposed once its scorer exists
  (WAVE-05 §2).

The two grant documents differ only in `grant_id`, so their canonical digests
differ and neither can pass for the other.

The module constants `GRANT_ID` and `GRANT_FILE` are removed rather than kept
as battery aliases. A leftover battery-only name could be used for another
Challenge by mistake; every caller now names a Challenge.

### GRANT-BINDING-D2 — Refusal codes

`check_committed_grant(path, repository, *, challenge)` keeps every earlier
check and adds two, in this order:

1. `no_phase4_grant_for_challenge`: the Challenge has no registered grant
   (`phase4_grant`).
2. `grant_is_for_another_challenge`: the copy names a grant registered for
   another Challenge. `grant_is_not_the_phase4_grant` means an id no
   Challenge registers (`bind_grant_to_challenge`). These are checked before
   git is read, so a wrong pairing is typed rather than a digest difference.
3. Then the earlier checks, now on that Challenge's file:
   `phase4_grant_not_committed`, then
   `grant_differs_from_the_committed_phase4_grant`, then
   `grant_commit_not_pushed`, then `main_grant_unavailable` or
   `grant_differs_from_main`, then
   `grants_directory_has_uncommitted_changes`.

`challenge` is a required keyword on `check_committed_grant`, `live_checks`,
`dry_run_grant`, `dry_run` and `phase4_prelive.prelive`. No caller falls back
to battery.

`live_checks` now checks the provider, then calls `check_committed_grant`. The
grant-id check moved into the binding, so there is only one id guard.

### GRANT-BINDING-D3 — CLI and dry run

- `phase4 run` passes `--challenge` to `live_checks` and to the dry run.
  `--grant` stays required for a live run: the operator names the file.
- `phase4 prelive` has no fixed `--grant` default any more. Without `--grant`
  it uses the file registered for `--challenge`. The adapter and the scoring
  are resolved first, as before, so motor still refuses
  `challenge_scoring_not_registered` today. Once a motor scorer registers, the
  prelive refuses `no_phase4_grant_for_challenge` (tested by stubbing the
  scoring registry).
- `dry_run_grant(challenge)` copies the named Challenge's grant amounts under
  the same synthetic identity. The dry-run report names the grant it copied
  (`grant_copied_from`).

### GRANT-BINDING-D4 — The prelive report is release evidence

WAVE-05 §3 makes `phase4 prelive` output part of a live run's release
evidence, so the report schema moves to `carbon.graphite.phase4-prelive.v2`.
It adds:
- `challenge`;
- `grant`: the accepted grant's `challenge`, `grant_id`, `grant_file` and
  canonical `grant_digest`. It is null when the grant check failed.

The grant step also proves the binding on the real check. Besides the raised
ceiling copy, a copy naming each other registered Challenge's grant must be
refused `grant_is_for_another_challenge`, or the step fails. If the grant
check fails in any way, the gate stops before opening a session.

### GRANT-BINDING-D5 — Before and after merge

The cooling grant is on this branch, not on main. At this branch's pushed
head, `phase4 prelive --challenge chip-cold-plate` therefore refuses
`main_grant_unavailable` on the grant step, as designed. Battery's passes.
`test_a_branch_only_cooling_grant_is_refused_until_it_is_on_main` simulates
the merge in a temporary repository with a bare remote. The same checkout
refuses while the grant is only on a pushed feature branch, and passes once
main carries the same blob.

### Not decided here

- Motor's phase-4 grant: proposed with motor's scorer (WAVE-05 §2).
- Any spend, run or REF. No live run happens in this work.
