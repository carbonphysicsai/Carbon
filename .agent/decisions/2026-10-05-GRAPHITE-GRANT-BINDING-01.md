## 2026-10-05 — GRAPHITE-GRANT-BINDING-01: per-Challenge Graphite grants

**Authority.** OWNER-GRAPHITE-TEST-WAVE-05 §2 for the phase-4 grant, and
OWNER-GRAPHITE-TEST-WAVE-06 §3 for the phase-3 grant (D6 and D7 below).

For phase 4: OWNER-GRAPHITE-TEST-WAVE-05 §2
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
- `carbon/challenge_pipeline/lessons/2026-10-05-phase4-cooling-grant.json`;
- phase 3 (D6, D7): `docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3-COOLING-CPU.json`,
  `carbon/agent_campaign/graphite/grant_binding.py` (new),
  `carbon/agent_campaign/graphite/experiment.py` (`phase3_budget`,
  `_admit_pod`, `_retry_budget`), `carbon/agent_campaign/graphite/phase3.py`
  (one call in `command_run`),
  `tests/cpu/test_graphite_phase3_cooling_cpu_grant.py`,
  `carbon/challenge_pipeline/lessons/2026-10-05-phase3-cooling-cpu-grant.json`.

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

### GRANT-BINDING-D6 — Cooling's CPU-lane Constructor grant (WAVE-06 §3)

**Authority.** OWNER-GRAPHITE-TEST-WAVE-06 §3
(`.agent/decisions/2026-10-05-OWNER-GRAPHITE-TEST-WAVE-06.md`,
carbonphysicsai/Carbon#595). The owner answered "approve". The approved terms
are 3 runs, one at a time; USD 1.95 per run, tokens only; USD 0.25 cleanup;
a USD 6.10 ceiling. The grant file is bound by the runner to `chip-cold-plate`
and to main's committed blob.

GRAPHITE-GRANT-PHASE3-COOLING-CPU carries those amounts.
- `max_runtime_s` was not stated in the approval. It is kept at 39,600 s, the
  elapsed limit of the existing phase-3 Constructor grants. It bounds time,
  never money.
- `max_submissions` (3, one per run), `account`, `expires_at`, `provider` and
  `granted_by` follow the existing phase-3 grants.

**Binding.** The shared committed-blob check moves into a new module,
`graphite/grant_binding.py` (`check_committed_blob`), so phase 3 and phase 4
run one implementation. `phase4.check_committed_grant` keeps its codes by
passing `phase="phase4"`. Phase 3 has its own registry,
`grant_binding.PHASE3_GRANTS`, keyed by grant id, with each grant's Challenge,
file, main-blob flag and pod flag:
- GRAPHITE-GRANT-PHASE3 and GRAPHITE-GRANT-PHASE3-R2 are battery's: no
  main-blob check and pods allowed, exactly as before;
- GRAPHITE-GRANT-PHASE3-COOLING-CPU is `chip-cold-plate`'s: main-blob bound,
  no pods.

`phase3 run` calls `check_phase3_grant` right after the provider check,
before any credential, key or code ref is read:
- a registered grant on another Challenge is `grant_is_for_another_challenge`;
- on a Challenge in `PHASE3_BOUND_CHALLENGES` (cooling), an unregistered grant
  is `grant_is_not_a_phase3_grant_for_challenge`;
- a main-blob grant runs `check_committed_blob` with phase-3 codes
  (`phase3_grant_not_committed`,
  `grant_differs_from_the_committed_phase3_grant`, and the shared
  `grant_commit_not_pushed`, `main_grant_unavailable`,
  `grant_differs_from_main`, `grants_directory_has_uncommitted_changes`).

Battery stays unbound. It keeps accepting any valid Graphite grant, as it
did before this change, because the ticket requires battery's phase-3 grants
to work unchanged. Requiring a registered grant on battery too would be a
behaviour change for its runner. It is left as a follow-up for the lead.
`phase3 reconcile` is not bound: it only cleans up a run's pods and must
never be blocked.

### GRANT-BINDING-D7 — A tokens-only grant refuses every pod

The grant format has no pod field, so the pod budget comes from the registry:
`grant_binding.tokens_only(grant)` is True for a tokens-only grant.
- `experiment.phase3_budget` then sets `max_pods` 0, so the pod allowance is
  0 and the whole USD 1.95 is the token share. The 2-pod minimum applies only
  to a grant with pods.
- `Experiment._admit_pod` refuses `grant_allows_no_pods` when the run's
  budget is tokens-only (`Phase3Budget.tokens_only`, a pod budget of 0).
  That is the one gate in front of every pod launch: the baseline, a
  proposal, a timeout retry and an ablation. The refusal comes before the
  ledger's `pod_reserved` event and before `pods.launch`.
- `_retry_budget` answers the same code, so a baseline retry is never
  decided on.
- The guard is in the experiment, the only caller of `pods.launch` on a
  phase-3 session's path, not in `pods.py`, which other work is changing.

The test drives the real launch path: `Experiment` over `RunPodPods`, with
RunPod in memory (`pods.InMemoryRunPod`) and every request recorded. No pod is
reserved and no create request is ever sent. A mutation gives the same grant
the phase-3 pod count, and the same path then reserves and creates a pod.

**Merging with VALIDATOR-06.** The Carbon Validator's carrier-lane pull
request (VALIDATOR-06, not on main or on any origin branch when this was
pushed) is expected to add this same id to `phase3.TOKENS_ONLY_GRANTS`, which
refuses a RunPod run under it. The two are meant to coexist:
- the refusal here is keyed on the run's pod budget
  (`Phase3Budget.tokens_only`, `max_pods == 0`), not on a hard-coded id
  list;
- `grant_binding.tokens_only(grant)` counts both the registry's
  `tokens_only` entries and `phase3.TOKENS_ONLY_GRANTS` when that exists, so
  either source gives the grant a pod budget of 0. When VALIDATOR-06 lands,
  the registry flag can be dropped in favour of its list, with no change to
  the refusal.

**Consequence.** Until cooling's CPU-lane evaluation path exists, a cooling
Constructor proposal under this grant closes `REFUSED_BUDGET`
`grant_allows_no_pods`. That is the lane work in WAVE-06 §2, not part of this
change. The live phase-3 runner also still asks for a RunPod key file even
when the grant funds no pod.

### Not decided here

- Motor's phase-4 grant: proposed with motor's scorer (WAVE-05 §2).
- A GPU-lane cooling Constructor grant: proposed with a price once the GPU
  lane exists (WAVE-06 §3).
- Any spend, run or REF. No live run happens in this work.
