# CHALLENGE-PROTOCOL-04 — Phase 1 step 4: battery through Test/iterate with Graphite (Graphite phases 3 and 4)

**Status:** rebuilt on #504 (branch `agent/challenge-protocol-04b`) and
generalized: the stage profile, the Attacker and its runner take the
Challenge as a parameter, and battery is their first instance (see
Generalization). Nothing live has run here, and nothing has been spent.

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
- OWNER-CHALLENGE-ROADMAP-01, -02 and -03 (rev 2.2: the construction ladder,
  one generalizable protocol, lessons after every execution);
- OWNER-CHALLENGE-STEP4-01 and its two amendments;
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
  `GRAPHITE-GRANT-PHASE3` (USD 15.00 including pods, 3 runs at USD 4.91). Its
  campaign ceiling is the one #504's runner registers, that grant's ceiling
  less cleanup (USD 14.75): the owner's answer "let it use it"
  (OWNER-CHALLENGE-STEP4-01, second amendment).
- The Attacker block of 3 sessions runs under `GRAPHITE-GRANT-STEP4`:
  USD 5.00 of Engy, 3 runs at a USD 1.66 worst case each, 34 model calls a
  session on `glm-5.2` (PROTO4-D4). Its campaign ceiling is USD 5.00
  (OWNER-CHALLENGE-STEP4-01 item 3, which now applies to it only).
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
   OWNER-CHALLENGE-STEP4-01 and its amendments; this ticket; the Hub events.
4. **Generalization** (OWNER-CHALLENGE-ROADMAP-03). Slices 1 and 2 take the
   Challenge as a parameter and read its specifics from its records; the
   stage profile records the construction level. Battery's specifics move to
   its record and adapter, and its behaviour is unchanged (below).
5. **The live blocks** (owner-run, pending). #504's 3 Constructor sessions
   and this ticket's 3 Attacker sessions. Then the coverage report and the
   iteration logs are committed, and step 4 closes.

## What is built

| Slice | Code | Tests |
| --- | --- | --- |
| 1 Stage | `graphite/stage.py`; `GraphiteProvider(stage_profile=...)` in #504's provider | `test_graphite_stage.py` |
| 2 Attacker v1 | `graphite/attack.py`: brief, attempts, `reverify`, `analyse`, `coverage`. `graphite/phase4.py`: `AttackerProvider`, `AttackerTools`, `run_session`, the `run`, `coverage` and `log` commands, dry run | `test_graphite_attack.py` |
| 3 Grant and records | `GRAPHITE-GRANT-STEP4.json`; grants README section; OWNER-CHALLENGE-STEP4-01; Hub event `CHALLENGE-PROTOCOL-04` | `test_graphite_step4_grant.py` |
| 4 Generalization | `graphite/challenge.py`; `graphite/adapters/battery.py`; `graphite/challenges/battery-fastcharge-ageing-development-v1.json`; the stage profile's construction level and its check in #504's provider's stage hook; Hub event `CHALLENGE-PROTOCOL-04-GENERAL` | `test_graphite_second_challenge.py`, and the slices' tests on battery |

**Dry run, no spend.** `phase4 run --dry-run` runs one Attacker session with
a scripted model, a synthetic copy of the Challenge's grant and no miner
path. Its recipe attempt is held by Graphite's own harness (no path
attached), so it is counted apart from the path's defense. No finding. The
coverage report merges with the Challenge's suite v1 report under the suite
and map digests, at Level 0.

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
  profile binds the stage, the permission ledger's bytes and the Challenge's
  permission inventory (battery's: `study.permission_inventory`). Its digest
  is the campaign's registered profile, so the controller's
  `profile_not_in_force` check needs no change. The provider, which alone
  knows the Graphite role, checks the role against the stage's row.
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
  without a wall allowance of at most battery's practice worker's 600 s (for
  any Challenge, its adapter's `code_run_seconds`). Both are counted across
  resumes. This bounds Graphite's own agent; it is not a limit on miners.
- **PROTO4-D7. Carbon re-verifies with #504's reconstruction gate.**
  - A recipe is refused by Carbon when the Challenge's admission gate
    refuses it. Battery's is `experiment.admit`, the gate #504 admits
    Constructor proposals through. A recipe Carbon rebuilds but #504's pods
    do not serve (PyTorch) is admitted.
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
  #504 merges. A proposed revision records it
  (`lessons/2026-10-02-step4-stage-not-in-constructor-runner.json`).
- **PROTO4-D9. The stage profile records the construction level.** Rev 2.2
  makes the construction ladder the spine of Test/iterate.
  - The profile's `construction_level` is the inventory's profile (`level-N`;
    battery's is `level-0`), and it must agree with the level the
    Challenge's pipeline record names (`records/f05.json`, Level 0). If they
    disagree, no profile is made.
  - The provider records the level and the Challenge in the session. It
    refuses, at construction, at start and on resume, a profile whose level
    differs from the inventory's now (`construction_level_mismatch`), or
    whose permissions changed at the same level
    (`stage_permissions_changed`).
  - The Attacker's rows, iteration log and coverage report state the level.
    The coverage refuses sessions at different levels and a suite report
    taken at another level, because evidence stays bound to its level.
  - Levels above it are listed NOT_RUN. A vector's participant-code part
    (the suite's `ladder` block: A1, A2 and A4 from Level 4) is carried
    through from the suite report: NOT_RUN at Level 0, never a pass. A
    report that scopes it otherwise is refused.
- **PROTO4-D10. A Challenge is a record, an adapter and the records the
  pipeline and suite already keep.** The shared modules take the Challenge
  (or its contract token) and read nothing Challenge-specific from code
  constants. Battery's literals moved to its Graphite record and its
  adapter. A record may name only an adapter module under
  `graphite/adapters/`. The runner's `--challenge` defaults to the Challenge
  that defines the protocol in Phase 1 (the record whose family is the
  pipeline's `PROTOCOL_FAMILY`), so the owner's commands are unchanged.
  `study.permission_inventory()` is untouched: the battery adapter calls it
  with no argument.

## Generalization

The owner, 2026-10-02: "Make sure everything we have is a generalizable test
and design protocol that can be adapted to any challenge and improved as we
go."

**Challenge-neutral** (`carbon/agent_campaign/graphite/`):
- `stage.py`: the stage profile for any Challenge and its check (ledger,
  stage, construction level, permissions digest).
- `challenge.py`: what a Challenge is to Graphite, its record schema
  (`carbon.graphite.challenge.v1`), its adapter's functions, and the
  agreement between the inventory's level and the pipeline record's.
- `attack.py`: the suite v1 vectors' shared wording (`ATTACK_GOALS`, which
  names no Challenge's backends), the brief, attempt reading, Carbon-side
  re-verification through the Challenge's gate, findings, and the coverage
  merge bound to the suite digest and the Challenge's suite map digest.
- `phase4.py`: the Attacker's provider, tools, controller campaign, session,
  coverage and dry run, all parameterized by the Challenge; its limits come
  from the Challenge's records.
- #504's provider's stage hook: the level and permissions check.

**The battery adapter** (battery's instance, behaviour unchanged):
- `graphite/challenges/battery-fastcharge-ageing-development-v1.json`:
  family f05, label "battery", the committed suite coverage report, A1's
  wording with its contract's backends "(JAX or PyTorch)", and the Attacker
  campaign: `graphite-step4-attacker`, its workspace and credential
  reference, GRAPHITE-GRANT-STEP4 and its file, the USD 5.00 ceiling and 34
  calls a session.
- `graphite/adapters/battery.py`: the permission inventory
  (`study.permission_inventory()`), the public identity
  (`battery.challenge.CHALLENGE`), the admission gate (#504's
  `experiment.admit`, PROTO4-D7), the code-run wall allowance
  (`battery.research.PRACTICE_SECONDS`, 600 s) and the dry run's
  out-of-contract recipe (the scaffold with `transolver`).
- Its other records, which already existed: the pipeline record
  (`carbon/challenge_pipeline/records/f05.json`, Level 0), the suite map
  (`carbon/challenge_pipeline/suite_maps/battery-fastcharge-ageing-development-v1.json`)
  and the coverage report
  (`docs/development/challenge_pipeline/SUITE_V1_BATTERY_COVERAGE.json`).
- Identity was checked by running the pre-generalization Attacker beside
  the new one: the same brief digest, limits, dry-run grant amounts and
  verdicts (`lessons/2026-10-02-step4-battery-unchanged.json`).

**What a second Challenge must supply** before its Attacker block:
1. A pipeline record with a `construction` block naming its contract token
   and level, reached by the ladder's rules.
2. A suite map, `carbon/challenge_pipeline/suite_maps/<token>.json`, and a
   committed suite v1 coverage report run at that level.
3. A permission inventory whose profile is `level-N`, agreeing with the
   pipeline record.
4. An adapter module under `graphite/adapters/` with
   `permission_inventory`, `public_identity`, `admission_refusals`,
   `code_run_seconds` and `recipe_outside_contract`. Its admission gate is
   Carbon's own reconstruction gate for that contract, returning
   `construction_contract_unrecorded` first when its record is not current.
5. A Graphite record, `graphite/challenges/<token>.json`, naming the above,
   any vector wording specific to it, and its Attacker campaign: identities,
   the grant that funds it (an owner grant, with its derivation), the
   owner's ceiling and the per-session call cap derived from that grant.
6. Graphite's ledger admitting the role at `test_iterate`, as it does today
   for every Challenge.

`tests/cpu/test_graphite_second_challenge.py` runs a synthetic second
Challenge through all of this with battery's adapter and gate made to raise.

**Lessons.** One entry per execution, under
`carbon/challenge_pipeline/lessons/2026-10-02-step4-*.json`. Two propose
protocol revisions, awaiting an owner: compose the stage profile into every
Graphite runner, and list what a Challenge supplies before its first
Graphite campaign.

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

`--challenge` is optional: without it the runner uses battery, the
Challenge that defines the protocol. The Attacker campaign's ceiling is
USD 5.00.

The Constructor block runs with #504's `phase3 run` under
GRAPHITE-GRANT-PHASE3, at the campaign ceiling #504's runner registers
(USD 14.75), as the owner answered ("let it use it").

## Human-reserved, fail closed until set

- **Science owner.** These are reported, not decided, until set:
  - the development scoring set;
  - the incumbent member;
  - any comparison margin;
  - the reconstruction tolerance.
- **Process owner.** The permission ledger and the stage mapping, both DRAFT
  until lock.
- **Answered: the constructor campaign's ceiling.** OWNER-CHALLENGE-STEP4-01
  item 3 set USD 5.00 for the constructor campaign, under the step 4 grant.
  After the re-scope the Constructor runs on #504 under
  GRAPHITE-GRANT-PHASE3, which registers its campaign at that grant's
  ceiling less cleanup (USD 14.75). Asked to keep USD 5.00 or let it use
  #504's grant, the owner answered "let it use it" (2026-10-02, second
  amendment). USD 5.00 now binds the Attacker campaign only. This ticket
  changes nothing of #504's.
- **Any owner: the two proposed protocol revisions** in the lessons log.
- **Technical owner.** Grading every finding and every coverage report.
- **Credential.** The Engy key is supplied by the owner in an owner-only
  file. It is never in chat, the repository or logs.

## Maturity ceiling

DEVELOPMENT, internal, never mainnet. Nothing here is scientific or security
qualification. Allowing attacker code in the sandbox is the owner's
development decision, not security acceptance.
