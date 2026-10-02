# CHALLENGE-PROTOCOL-04 — Phase 1 step 4: battery through Test/iterate with Graphite (Graphite phases 3 and 4)

**Status:** rebuilt on #504 (branch `agent/challenge-protocol-04b`). Nothing
live has run here, and nothing has been spent.

**Re-scope (owner, 2026-10-02).** The Graphite lane's #504 (GRAPHITE-01
phase 3, under OWNER-GRAPHITE-03) builds the same Constructor as this
ticket's reference branch (`agent/challenge-protocol-04`), in files of the
same names. Asked which to keep, the owner answered "yes" to this
recommendation (OWNER-CHALLENGE-STEP4-01, amendment):
- **#504 lands as the Constructor.**
- **This ticket drops its duplicate Constructor slices:** the provider
  repairs, the miner path, Carbon-side scoring and its phase 3 runner.
- **What only this ticket has is rebuilt on top of #504:**
  - the stage profile and Graphite's per-stage enforcement (slice 1);
  - the Attacker with Carbon-side re-verification, findings and suite
    coverage (slice 2);
  - the step 4 grant (slice 3).

This branch merges #504 (`origin/claude/graphite-phase3` at `d7ae8125c`) and
builds on it. The reference branch is kept for history and is not merged.
The live blocks run on #504's Constructor and this ticket's Attacker:
- a fresh Launchpad battery campaign the owner launches with no agent;
- the Engy key in an owner-only file. Only its path is ever passed.

**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`, `HUB_UPDATE_REQUIRED`.
**Affects:** `SYSTEM/AGENT-EXECUTION`.
**Authority:**
- OWNER-CHALLENGE-ROADMAP-01 and -02;
- OWNER-CHALLENGE-STEP4-01 and its amendment;
- OWNER-GRAPHITE-01, -02 and -03;
- OWNER-CHALLENGE-ADMISSION-01;
- OWNER-DX-03.

**Spec:** `Design_Specs/Challenge_Roadmap.md` §01 step 4, §02 and §03; the
protocol draft; `docs/development/GRAPHITE_TESTING_AGENT_PLAN.md` §5 and §7.

## Outcome

The roadmap's step 4 is "Run battery through Test/iterate with Graphite.
Attack, fix, re-score; tune construction and scoring until results stop
improving or the iteration budget runs out." Its output is an iteration log.
It is Graphite's phase 3 and phase 4:
- **Phase 3, Constructor at Level 0: #504.** Live sessions propose battery
  recipes through the real miner path, inside the recorded construction
  contract. Carbon admits each through its reconstruction gate, runs it on a
  pod, checks the pod's build, scores it by the frozen rule against the
  session's baseline, and rebuilds the best one cleanly from its bundle.
- **Phase 4, Attacker: this ticket.** Live sessions probe suite v1's eight
  vectors through the same miner path and, under OWNER-CHALLENGE-STEP4-01,
  run code in the sandbox. Carbon re-verifies every claimed fail-open
  outside the agent before anything is a finding. A coverage report merges
  the attacker's results with the suite's checks, bound to the suite digest.

**Budget.**
- The Constructor block of 3 sessions runs on #504's runner under
  `GRAPHITE-GRANT-PHASE3` (USD 15.00 including pods, 3 runs at USD 4.91).
- The Attacker block of 3 sessions runs under `GRAPHITE-GRANT-STEP4`:
  USD 5.00 of Engy, 3 runs at a USD 1.66 worst case each, 34 model calls a
  session on `glm-5.2` (PROTO4-D4).
- Derivations: `docs/development/graphite/grants/README.md`.

## Slices (on #504)

1. **Stage.** The stage profile (`carbon/agent_campaign/graphite/stage.py`).
   Its digest is the campaign's profile in the controller. #504's provider
   takes `stage_profile=` and refuses a role outside its stage's row of
   Graphite's permission ledger, a task with another profile, a changed
   ledger, and a resumed session whose stage changed.
2. **Attacker v1.** `graphite/attack.py`: brief, attempts, Carbon-side
   re-verification, findings, coverage. `graphite/phase4.py`: the Attacker's
   provider and runner beside #504's Constructor runner.
3. **Grant and records.** `GRAPHITE-GRANT-STEP4.json` and its derivation;
   OWNER-CHALLENGE-STEP4-01 and its amendment; this ticket; the Hub event.
4. **The live blocks** (owner-run, pending). #504's 3 Constructor sessions
   and this ticket's 3 Attacker sessions. Then the coverage report and the
   iteration logs are committed, and step 4 closes.

## What is built

| Slice | Code | Tests |
| --- | --- | --- |
| 1 Stage | `graphite/stage.py`; `GraphiteProvider(stage_profile=...)` in #504's provider | `test_graphite_stage.py` |
| 2 Attacker v1 | `graphite/attack.py`: brief, attempts, `reverify`, `analyse`, `coverage`. `graphite/phase4.py`: `AttackerProvider`, `AttackerTools`, `run_session`, the `run`, `coverage` and `log` commands, dry run | `test_graphite_attack.py` |
| 3 Grant and records | `GRAPHITE-GRANT-STEP4.json`; grants README section; OWNER-CHALLENGE-STEP4-01; Hub event `CHALLENGE-PROTOCOL-04` | `test_graphite_step4_grant.py` |

**Dry run, no spend.** `phase4 run --dry-run` runs one Attacker session with
a scripted model, a synthetic grant and no miner path. Its recipe attempt is
held by Graphite's own harness (no path attached), so it is counted apart
from the path's defense. No finding. The coverage report merges with suite
v1's report under its digest.

**Dropped from the reference branch.**
- `graphite/score.py`, the reference's `phase3.py` and `miner_path.py`, and
  `ResearchToolAdapter.in_process_sdk`: #504's Constructor runner, its
  `experiment` and `delivery`, and its `miner_path.attach` replace them.
- The reference's provider repairs that #504 already covers, or that the
  Attacker does not need (below).
- The reference's tests of those (`test_graphite_live.py`,
  `test_graphite_score.py`, `test_graphite_phase3_runner.py`,
  `tests/service/test_graphite_battery_path.py`).

**Live-session repairs.** Of the reference's five:
- **Ported for the Attacker: the trial cap**, as a per-session code-run cap
  in `phase4.AttackerTools` (PROTO4-D6). #504's toolbox passes miner tool
  calls straight to the path, so the research loop's own trial limit never
  counts them.
- **Already in #504, used as is: per-role call caps.** #504's
  `max_provider_calls` (GRAPHITE-D26) and the run ledger's
  `provider_attempts` carry the Attacker's cap of 34.
- **Already in #504: run-namespaced identities.** `miner_path.MinerPathTools`
  prefixes every operation id with the session.
- **Not needed: the async run.** #504 attaches the miner path inside the
  session's own event loop (`_epoch`), and so does `AttackerProvider`.
- **Not ported: the model view.** Full results reach the model, as they do
  for #504's Constructor. Spend is bounded by the per-call reservation and
  the run cap either way. A session whose history outgrows the request
  ceiling stops, typed, with nothing discarded. If the first live session
  stops that way early, the view is the follow-up.

## Working decisions

- **PROTO4-D1. The stage enters through the campaign profile.** A stage
  profile binds the stage, the permission ledger's bytes and battery's
  permission inventory (`study.permission_inventory`). Its digest is the
  campaign's registered profile, so the controller's `profile_not_in_force`
  check needs no change. The provider, which alone knows the Graphite role,
  checks the role against the stage's row.
- **PROTO4-D2. Step 4 runs at `test_iterate`.**
  - Battery's pipeline record is at `protocol` (Phase 1). The ledger's stages
    are the roadmap's stages.
  - Step 4 is the roadmap's Test/iterate stage applied to battery.
  - The ledger is a DRAFT for the process owner to approve at lock.
- **PROTO4-D3. Without a stage profile, a provider behaves as before.**
  Phase 2's literature runner and #504's Constructor runner are unchanged.
  The Attacker's provider refuses to exist without one.
- **PROTO4-D4. The step 4 grant funds the Attacker block only.** #504's
  GRAPHITE-GRANT-PHASE3 already funds the first block of 3 Constructor
  sessions, so the owner's USD 5.00 goes to the 3 Attacker sessions: the
  ceiling less cleanup shared by 3 runs (USD 1.66 each), and the call cap the
  most `glm-5.2` calls that holds (34). This is inside the owner's ceiling;
  it changes no owner value.
- **PROTO4-D5. The Attacker runs beside #504's runner, not inside it.**
  - `graphite/phase4.py` reuses #504's provider, controller, miner path,
    runner helpers and grant loading, and changes none of #504's files
    except the provider's stage hook.
  - Its store is `DIR/attacker`, so one `DIR` can also hold #504's
    Constructor store.
  - The controller binds one grant to the store. A registry outside the
    store binds the grant to one store, so a second store can never enforce
    the same ceiling twice.
  - It accepts only GRAPHITE-GRANT-STEP4, and only the path of an owner-only
    key file, checked by metadata and never read by the runner.
- **PROTO4-D6. An Attacker session starts at most 8 code runs, each bounded
  to 600 s.** The research loop's per-epoch limit (`MAX_RESEARCH_TRIALS`)
  cannot count delegated miner tools, and battery's `run_python` has no
  Carbon wall limit unless the miner sets one. So `AttackerTools` refuses,
  before dispatch, a ninth code run and any `run_python` or `run_julia`
  without a wall allowance of at most battery's practice worker's 600 s.
  Both are counted across resumes. This bounds Graphite's own agent; it is
  not a limit on miners.
- **PROTO4-D7. Carbon re-verifies with #504's reconstruction gate.**
  - A recipe is refused by Carbon when `experiment.admit` refuses it: the
    gate #504 admits Constructor proposals through. A recipe Carbon rebuilds
    but #504's pods do not serve (PyTorch) is admitted.
  - A refusal by Graphite's own harness (manifest, protected material,
    code-run rules, no path attached) never reached the path. It is counted
    apart, never as the path's defense.
  - A result Graphite withheld for naming protected material, and any
    attempt while Carbon's contract record is not current, is
    `UNDETERMINED`: reported, never a finding.
  - A reproduced fail-open is recorded as `FAILING_TRIGGER`: an admission
    check that should have fired did not (OWNER-CHALLENGE-ADMISSION-01
    §3.2).
- **PROTO4-D8. The stage is not wired into #504's Constructor runner.**
  #504 registers its Level-0 permission profile (`phase3.permission_profile`)
  as the campaign profile and every task's profile. A staged provider needs
  the task's profile to be the stage profile's digest. Wiring it in means
  replacing #504's registered profile or composing the two, which changes
  #504's records and tests. That is not a small change to make before #504
  merges. `Phase3Provider` already forwards `stage_profile=`, and the ledger
  admits the Constructor at `test_iterate`, so the Constructor block's
  behavior would not change. Composing the profiles is a follow-up after
  #504 merges.

## Live blocks (owner-run)

Under `ROOT`, a private directory outside the repository:

```
python -m carbon.agent_campaign.graphite.phase4 run --root ROOT \
    --grant docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json \
    --credential-file KEY_FILE_PATH \
    --miner-profile PROFILE.json --miner-campaign CAMPAIGN --session N
python -m carbon.agent_campaign.graphite.phase4 coverage --root ROOT
python -m carbon.agent_campaign.graphite.phase4 log --root ROOT
```

The Constructor block runs with #504's `phase3 run` under
GRAPHITE-GRANT-PHASE3.

## Human-reserved, fail closed until set

- **Science owner.** These are reported, not decided, until set:
  - the development scoring set;
  - the incumbent member;
  - any comparison margin;
  - the reconstruction tolerance.
- **Process owner.** The permission ledger and the stage mapping, both DRAFT
  until lock.
- **Owner: the constructor campaign's ceiling.** OWNER-CHALLENGE-STEP4-01
  item 3 set USD 5.00 for the constructor campaign, under the step 4 grant.
  After the re-scope, the Constructor runs on #504 under
  GRAPHITE-GRANT-PHASE3, and #504 registers its campaign at that grant's
  ceiling less cleanup (USD 14.75). This ticket changes nothing of #504's.
  Whether the constructor campaign is held to USD 5.00 is the owner's call.
- **Technical owner.** Grading every finding and every coverage report.
- **Credential.** The Engy key is supplied by the owner in an owner-only
  file. It is never in chat, the repository or logs.

## Maturity ceiling

DEVELOPMENT, internal, never mainnet. Nothing here is scientific or security
qualification. Allowing attacker code in the sandbox is the owner's
development decision, not security acceptance.
