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

### GRANT-BINDING-D4b — One prelive schema version for both additions

#605 (GRAPHITE-D35) added an `attacker_model` block to the prelive report
under `phase4-prelive.v1`. This branch adds `challenge` and `grant`. The merge
keeps all three, and the single `v2` covers both changes.

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
file and main-blob flag:
- GRAPHITE-GRANT-PHASE3, GRAPHITE-GRANT-PHASE3-R2 and GRAPHITE-GRANT-PHASE3-R3
  (OWNER-GRAPHITE-PHASE3-R3-01, added on main and registered at the merge)
  are battery's: no
  main-blob check, exactly as before;
- GRAPHITE-GRANT-PHASE3-COOLING-CPU is `chip-cold-plate`'s: main-blob bound.
  Whether a grant is tokens-only is VALIDATOR-06's `phase3.TOKENS_ONLY_GRANTS`
  (D7), not a flag here.

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

### GRANT-BINDING-D7 — A tokens-only grant refuses every paid pod

The grant format has no pod field. Which grants are tokens-only is
VALIDATOR-06's `phase3.TOKENS_ONLY_GRANTS` (#608, on main), the single list;
`grant_binding.tokens_only(grant)` reads it. A tokens-only run's pod money
budget is 0:
- `experiment.phase3_budget` sets `Phase3Budget.tokens_only`. The pod
  allowance is then 0, and the whole USD 1.95 is the token share. The field
  is recorded in the budget record only when set, so every other run's
  record is unchanged.
- `Experiment._admit_pod` refuses `grant_allows_no_pods` for any launch that
  would reserve pod money under that budget (`Phase3Budget.pays_for_pods`):
  every RunPod pod, whether for the baseline, a proposal, a timeout retry or
  an ablation. The refusal comes before the ledger's `pod_reserved` event
  and before `pods.launch`. `_retry_budget` answers the same code.
- A backend that costs no provider money is admitted. That is the CPU
  carrier lane (`carrier_pods.CarrierPods`, `hourly_usd` 0, #608), where
  WAVE-06 §3's "tokens only (no pods on the CPU lane)" runs its proposals.
  Refusing every launch would make the approved grant unusable on the lane
  it was approved for; refusing every paid launch keeps "no pod money"
  exact.
- This is defence in depth behind #608's CLI refusal
  (`grant_is_tokens_only_use_the_carrier_lane` for `--compute runpod`): a
  provider built over RunPod with this grant still cannot reserve or
  create a pod.
- The guard is in the experiment, the only caller of `pods.launch` on a
  phase-3 session's path, not in `pods.py`.

The tests drive the real launch path: `Experiment` over `RunPodPods`, with
RunPod in memory (`pods.InMemoryRunPod`) and every request recorded. No pod is
reserved and no create request is ever sent. On a rate-0 backend the same
grant's baseline and proposal are launched. Mutations:
- the same budget without `tokens_only` reserves and creates a RunPod pod;
- removing the grant from `TOKENS_ONLY_GRANTS` makes its budget refuse
  (`grant_run_cost_cannot_cover_pods_and_tokens`).

**Merged with VALIDATOR-06 (#608).** The first version of this decision
derived a pod count of 0 from a `tokens_only` flag in `PHASE3_GRANTS`, with a
fallback to `TOKENS_ONLY_GRANTS`. When main was merged in (#604, #605, #608,
#610, #620), `TOKENS_ONLY_GRANTS` was on main and #608 runs this grant on the
carrier. So:
- the registry flag is dropped in favour of #608's list;
- the refusal moved from "no pods" to "no paid pods" so the carrier lane
  keeps working.

**Consequence.** The live phase-3 runner still asks for a RunPod key only for
`--compute runpod`, which refuses this grant.

**Addendum (2026-10-05): a backend that reports a charge anyway.** The Test
Lead confirmed "no pod money" and asked that nothing can charge a tokens-only
run a pod rate by mistake. A probe found one way: a carrier-lane backend whose
`charge()` reports money after a USD 0 reservation (0.30 per pod). That charge
was booked with nothing else happening. Under a tokens-only budget, a
non-zero reported charge now:
1. **Is booked truthfully** as the pod's `pod_settled` row, at the amount
   reported. It is never dropped or zeroed: hiding real spend is worse than
   the defect.
2. **Is a typed finding,** `tokens_only_backend_reported_a_charge` (kind
   `TOKENS_ONLY_BACKEND_REPORTED_A_CHARGE`), with the intent, the pod id and
   the amount.
3. **Fails closed through the existing stop** (`Experiment._stop_session`,
   `session-stop.json`, `FAILED_INFRA`, reason
   `tokens_only_backend_reported_a_charge`, no candidate charge):
   - waiting and later proposals are refused;
   - the provider ends the session typed (`_stopped_for`);
   - `_admit_pod` now refuses any pod once the session is stopped
     (`session_stopped:<reason>`). That also covers a retry or relaunch of the
     proposal in flight, which the stop did not reach before.

The real `CarrierPods.charge` returns 0, so none of this fires on the lane as
built. Tests use the 0.30 probe for each of the three, plus the in-flight
retry, with a mutation per guard.

### Not decided here

- Motor's phase-4 grant: proposed with motor's scorer (WAVE-05 §2).
- A GPU-lane cooling Constructor grant: proposed with a price once the GPU
  lane exists (WAVE-06 §3).
- Any spend, run or REF. No live run happens in this work.
