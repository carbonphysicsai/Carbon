## 2026-10-06 — A4-DEDICATED-ADMISSION-CONTROLLERS-01: a dedicated zero-spend admission controller per Challenge, and readiness item A4 wired to the designation

**Authority.**
- The Test Lead's ruling on readiness item A4, 2026-10-06: battery
  (`battery-fastcharge-ageing-development-v1`), cooling (`chip-cold-plate`)
  and motor (`electric-motor-magnetics`) all use #615's dedicated zero-spend
  admission controller. Battery is included. The pattern is challenge-neutral
  and is not tied to a spent grant root. The executor creates each controller
  root and reports its identity digest, offline and with no spend.
- GRAPHITE-ADMISSION-CONTROLLER-01 (#615), item 6: give admission its own
  controller, bound to a dedicated zero-spend grant rather than a run's grant.
  This decision builds that follow-up and nothing wider.

Everything below is an engineering choice within that delegated authority.
No scientific value, threshold, gate, score or tolerance changes. Nothing
widens for miners. There is no chain write, no live run and no spend.

**The gap.** #615 recorded the dedicated controller but did not build it. On
main 32e79ffb, `phase3 conditions` refuses a root without a controller store
and never creates one, and every committed grant is a run grant: a
`SpendingGrant` needed a positive run cost and at least one run, so a
zero-spend grant could not be expressed.

**Decisions.**

1. **Zero-spend grants (`carbon/agent_campaign/grant.py`).**
   - A grant whose three amounts are all 0 is a zero-spend grant. It must
     also permit 0 runs and 0 submissions, or it is refused. A grant with
     only some amounts at 0 is refused exactly as before.
   - `SpendingGrant.zero_spend` says so. Every path that could spend refuses
     such a grant before anything is reserved, with `grant_is_zero_spend`:
     `CampaignController.register_campaign` and `launch` (before the
     dispatchability check), `LiveModel` and `Phase3Provider`.
   - Every existing grant behaves exactly as before.

2. **Which grant each Challenge's controller binds
   (`grant_binding.ADMISSION_CONTROLLER_GRANTS`).**
   - One file per Challenge under `docs/development/graphite/grants/`:
     `GRAPHITE-GRANT-ADMISSION-CONTROLLER-BATTERY.json`, `-COOLING.json` and
     `-MOTOR.json`, each R2's shape with `monetary_ceiling` "0.00", 0 runs
     and 0 submissions.
   - `admission_grant_refusal` requires the grant to be zero-spend and,
     field for field, the committed file registered for the Challenge.
   - Grant files bind spend, so the owner approves them even at zero. They
     are not on this branch (see Pending). Until they are committed, `init`
     refuses `admission_grant_file_unreadable`, which fails closed.

3. **`phase3 admission-controller init`.**
   - **Usage.**
     `python -m carbon.agent_campaign.graphite.phase3 admission-controller init --root ROOT --challenge TOKEN --grant GRANT`.
   - **What it does.** It creates an empty controller store at
     `ROOT/controller`, bound to the Challenge's zero-spend grant. It opens
     the store with `NoDispatch`, a provider that is never dispatchable and
     refuses every run call. It then prints `CampaignController.identity()`
     and the Challenge's Level 0 designation entry.
   - **Refusals.** It refuses an existing `ROOT/controller`
     (`controller_store_exists`), a root inside the repository, an
     unregistered Challenge and any grant that is not the committed
     zero-spend one. Nothing is created when it refuses.
   - **Challenge-neutral.** A Challenge joins with one registry line and its
     grant file.
   - **Reading it back.** `phase3 conditions --identity` on the same root,
     with the same grant, prints the same identity. `conditions --report`
     consumes into it. A zero-spend grant opens the admission controller
     with `NoDispatch` and no phase-3 provider.

4. **Designations (`carbon/challenge_pipeline/admission_controllers.json`).**
   - **Entries.** One Level 0 entry per Challenge:
     `admission-controller-battery-l0`, `admission-controller-cooling-l0` and
     `admission-controller-motor-l0`.
   - **Status.** Each entry is `PENDING_OPERATOR_IDENTITY` with a null
     identity.
   - **Battery.** Battery's entry now names the dedicated controller, not
     the R2 phase-3 root, per the Test Lead's ruling.

5. **Readiness item A4.**
   - **The check.** A4's check is `admission_controller`, which reads the
     designation for (challenge, level):
     - `DESIGNATED` with a well-formed sha256 passes;
     - `PENDING_OPERATOR_IDENTITY` is NOT_BUILT, with the item's reason and
       owner;
     - a missing entry, a malformed file or a duplicated entry fails.
   - **Stale wording.** The old pending reason, "#615 not on main", is
     replaced with the current state.

**Tests.**
- `tests/cpu/test_a4_dedicated_admission_controllers.py` covers zero-spend
  grants (whole or refused), and checks that any run under one is refused
  before reservation.
- It covers `init`, including identity read-back, a refused second `init`,
  refused grants and roots, no dispatch, and consumption as the designated
  authority.
- Per Challenge, it checks for exactly one pending entry, A4 NOT_BUILT while
  pending, A4 PASS for a DESIGNATED sha256, and A4 FAIL for malformed and
  duplicate entries.
- **Mutations.** It runs five mutations, each switching one guard off.

**Pending.**
- **Grant files.** The three zero-spend grant files are not committed here.
  The approval was relayed by the Test Engineer session, and this session's
  permission check blocked writing the files. They need a commit made with
  the owner's own approval.
- **Executor.** After that, the executor runs `init` per Challenge on the
  operator host and reports each digest.
- **Follow-up PR.** A one-line follow-up then fills each identity.
- **Battery findings.** Battery Level 0 findings recorded on the R2 root
  (#609) must be consumed again into the dedicated controller before any
  battery Level 0 LOCK review.

**Maturity.** Implemented and tested with synthetic grants and temporary
roots. Not scientifically or security qualified. A4 stays NOT_BUILT for all
three Challenges until the identities land.
